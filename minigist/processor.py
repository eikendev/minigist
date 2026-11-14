import asyncio
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from .config import AppConfig, EntryUpdatesMode
from .constants import FAILED_ENTRIES_ABORT_THRESHOLD, WATERMARK_DETECTOR
from .downloader import Downloader
from .exceptions import ConfigError, MinifluxApiError, TooManyFailuresError
from .logging import get_logger
from .miniflux_client import MinifluxClient
from .models import Entry, Feed, ProcessingStats
from .pipeline import FetchWorker, LLMWorker, UpdateWorker
from .processing_counts import ProcessingCounts
from .summarizer import Summarizer

logger = get_logger(__name__)


class Processor:
    def __init__(self, config: AppConfig, dry_run: bool = False):
        self.config = config
        self.client = MinifluxClient(config.miniflux, dry_run=dry_run)
        self.summarizer = Summarizer(config.llm)
        self.downloader = Downloader(config.scraping)
        self.dry_run = dry_run
        self.prompt_lookup = {prompt.id: prompt.prompt for prompt in config.prompts}
        self.feed_target_map: dict[int, tuple[str, bool]] = {}
        self.use_targets = bool(config.targets)
        self.entry_updates_mode = self._resolve_entry_updates_mode()
        default_prompt_id = config.default_prompt_id or (config.prompts[0].id if config.prompts else None)
        if default_prompt_id is None or default_prompt_id not in self.prompt_lookup:
            logger.error(
                "Default prompt ID is not configured or missing from prompts",
                default_prompt_id=default_prompt_id,
            )
            raise ConfigError("A valid default prompt must be configured")
        self.default_prompt_id = default_prompt_id

    def __enter__(self) -> "Processor":
        """Return the processor for context manager usage."""
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> bool:
        """Close managed resources when exiting a context."""
        self.downloader.close()
        return False

    def _filter_unsummarized_entries(self, entries: list[Entry]) -> list[Entry]:
        unsummarized = [entry for entry in entries if WATERMARK_DETECTOR not in entry.content]
        logger.debug(
            "Filtered entries for summarization",
            total_entries=len(entries),
            unsummarized_count=len(unsummarized),
            already_summarized_count=len(entries) - len(unsummarized),
        )
        return unsummarized

    def _resolve_entry_updates_mode(self) -> EntryUpdatesMode:
        """Return the configured entry updates mode, or the default for the targets setup."""
        configured_mode = self.config.miniflux.entry_updates
        if configured_mode is not None:
            return configured_mode
        return EntryUpdatesMode.DISABLE if self.use_targets else EntryUpdatesMode.ALLOW

    def _fetch_feeds(self) -> list[Feed]:
        """Fetch feed metadata from Miniflux, halting on failure."""
        try:
            return self.client.get_feeds()
        except MinifluxApiError as e:
            logger.critical("Failed to fetch feeds metadata from Miniflux", error=str(e))
            raise
        except Exception as e:
            logger.critical("Unexpected error while fetching feeds metadata", error=str(e))
            raise

    def _select_feeds_without_entry_updates(self, feeds: list[Feed]) -> list[Feed]:
        """Return the feeds whose summaries survive refreshes, disabling entry updates if configured.

        Args:
            feeds: Feeds that minigist would summarize.

        Returns:
            Feeds that already keep existing entries, or had entry updates disabled successfully.
        """
        selected_feeds: list[Feed] = []

        for feed in feeds:
            if feed.keeps_existing_entries:
                selected_feeds.append(feed)
                continue

            if self.entry_updates_mode is EntryUpdatesMode.SKIP:
                logger.warning("Skipping feed with entry updates enabled", feed_id=feed.id, feed_title=feed.title)
                continue

            try:
                self.client.disable_entry_updates(feed)
            except MinifluxApiError as e:
                logger.error("Failed to disable entry updates", feed_id=feed.id, error=str(e))
                continue

            selected_feeds.append(feed)

        return selected_feeds

    def _build_feed_target_map(self, feeds: list[Feed]) -> dict[int, tuple[str, bool]]:
        category_to_feed_ids: dict[int, set[int]] = defaultdict(set)
        for feed in feeds:
            if feed.category and feed.category.id is not None:
                category_to_feed_ids[feed.category.id].add(feed.id)

        feed_target_map: dict[int, tuple[str, bool]] = {}

        for index, target in enumerate(self.config.targets, start=1):
            if target.prompt_id not in self.prompt_lookup:
                logger.error(
                    "Validation failed while building target map: unknown prompt ID",
                    prompt_id=target.prompt_id,
                    target_index=index,
                )
                raise ConfigError(f"Target references unknown prompt_id '{target.prompt_id}'")

            resolved_feed_ids: set[int] = set(target.feed_ids or [])

            if target.category_ids:
                for category_id in target.category_ids:
                    if category_id not in category_to_feed_ids:
                        logger.error(
                            "Validation failed while building target map: category does not exist",
                            category_id=category_id,
                            target_index=index,
                        )
                        raise ConfigError(f"Category ID {category_id} does not exist in Miniflux")
                    resolved_feed_ids.update(category_to_feed_ids[category_id])

            if not resolved_feed_ids:
                logger.info(
                    "Target does not match any feeds",
                    target_index=index,
                    prompt_id=target.prompt_id,
                )
                continue

            for feed_id in resolved_feed_ids:
                if feed_id in feed_target_map:
                    logger.error(
                        "Validation failed while building target map: feed assigned to multiple targets",
                        feed_id=feed_id,
                        target_index=index,
                    )
                    raise ConfigError(f"Feed ID {feed_id} is assigned to multiple targets")
                feed_target_map[feed_id] = (target.prompt_id, target.use_pure)

        logger.info(
            "Resolved targets to feeds",
            total_feeds=len(feeds),
            covered_feeds=len(feed_target_map),
            uncovered_feeds=max(len(feeds) - len(feed_target_map), 0),
        )
        return feed_target_map

    def run(self) -> ProcessingStats:
        processed_successfully_count = 0
        failed_entries_count = 0

        manage_entry_updates = self.entry_updates_mode is not EntryUpdatesMode.ALLOW
        feeds = self._fetch_feeds() if self.use_targets or manage_entry_updates else []

        if self.use_targets:
            try:
                self.feed_target_map = self._build_feed_target_map(feeds)
            except (MinifluxApiError, ConfigError) as e:
                logger.critical("Failed to resolve target mapping", error=str(e))
                raise
            except Exception as e:
                logger.critical("Unexpected error while resolving target mapping", error=str(e))
                raise

        effective_feed_ids = list(self.feed_target_map.keys()) if self.use_targets else None

        if manage_entry_updates:
            covered_feeds = [feed for feed in feeds if feed.id in self.feed_target_map] if self.use_targets else feeds
            selected_feeds = self._select_feeds_without_entry_updates(covered_feeds)
            if self.use_targets or len(selected_feeds) < len(covered_feeds):
                effective_feed_ids = [feed.id for feed in selected_feeds]

        if effective_feed_ids == []:
            logger.info("No feeds to summarize")
            return ProcessingStats(total_considered=0, processed_successfully=0, failed_processing=0)

        try:
            all_fetched_entries = self.client.get_entries(effective_feed_ids, self.config.fetch)
        except MinifluxApiError as e:
            logger.critical("Failed to fetch initial entries from Miniflux", error=str(e))
            raise
        except Exception as e:
            logger.critical("Unexpected error during initial Miniflux setup", error=str(e))
            raise

        if not all_fetched_entries:
            logger.info("No matching unread entries found from Miniflux")
            return ProcessingStats(total_considered=0, processed_successfully=0, failed_processing=0)

        unsummarized_entries = self._filter_unsummarized_entries(all_fetched_entries)

        if self.use_targets:
            considered_entries = [entry for entry in unsummarized_entries if entry.feed_id in self.feed_target_map]
        else:
            considered_entries = unsummarized_entries

        total_considered_entries = len(considered_entries)

        skipped_due_to_missing_target = len(unsummarized_entries) - total_considered_entries
        if skipped_due_to_missing_target > 0:
            logger.warning(
                "Skipping entries without a configured target (this may be a bug)",
                skipped=skipped_due_to_missing_target,
            )

        if total_considered_entries == 0:
            logger.info("All considered entries have already been summarized")
            return ProcessingStats(
                total_considered=total_considered_entries,
                processed_successfully=0,
                failed_processing=0,
            )

        logger.info(
            "Attempting to process unsummarized entries",
            total_fetched=len(all_fetched_entries),
            total_unsummarized=len(unsummarized_entries),
            total_considered=total_considered_entries,
        )

        processed_successfully_count, failed_entries_count, aborted = asyncio.run(
            self._run_pipeline(considered_entries, total_considered_entries)
        )

        if aborted:
            logger.critical(
                "Aborting processing because too many entries failed",
                failed_count=failed_entries_count,
                attempted_this_run=processed_successfully_count + failed_entries_count,
                total_considered=total_considered_entries,
            )
            raise TooManyFailuresError(
                f"Processing aborted after {processed_successfully_count + failed_entries_count} "
                f"of {total_considered_entries} entries attempted, due to {failed_entries_count} failures"
            )

        logger.debug(
            "Processing run complete",
            total_considered=total_considered_entries,
            successfully_processed=processed_successfully_count,
            failed_after_retries=failed_entries_count,
        )
        return ProcessingStats(
            total_considered=total_considered_entries,
            processed_successfully=processed_successfully_count,
            failed_processing=failed_entries_count,
        )

    async def _run_pipeline(
        self,
        considered_entries: list[Entry],
        total_considered_entries: int,
    ) -> tuple[int, int, bool]:
        loop = asyncio.get_running_loop()
        in_queue: asyncio.Queue = asyncio.Queue(maxsize=self.config.llm.concurrency * 2)
        out_queue: asyncio.Queue = asyncio.Queue()
        abort_event = asyncio.Event()
        counts = ProcessingCounts()

        def record_failure() -> None:
            counts.increment_failed()
            if counts.failed >= FAILED_ENTRIES_ABORT_THRESHOLD:
                abort_event.set()

        fetch_worker = FetchWorker(
            downloader=self.downloader,
            total_considered_entries=total_considered_entries,
            use_targets=self.use_targets,
            feed_target_map=self.feed_target_map,
            default_prompt_id=self.default_prompt_id,
            record_failure=record_failure,
            abort_event=abort_event,
        )
        llm_worker = LLMWorker(
            summarizer=self.summarizer,
            prompt_lookup=self.prompt_lookup,
            record_failure=record_failure,
            abort_event=abort_event,
        )
        update_worker = UpdateWorker(
            miniflux_client=self.client,
            record_failure=record_failure,
            abort_event=abort_event,
        )

        fetch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="minigist-fetch")
        update_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="minigist-update")

        try:
            producer_task = asyncio.create_task(
                fetch_worker.run(
                    loop,
                    considered_entries,
                    in_queue,
                    fetch_executor,
                    self.config.llm.concurrency,
                )
            )
            worker_tasks = [
                asyncio.create_task(
                    llm_worker.run(
                        in_queue,
                        out_queue,
                    )
                )
                for _ in range(self.config.llm.concurrency)
            ]
            updater_task = asyncio.create_task(
                update_worker.run(
                    loop,
                    out_queue,
                    update_executor,
                    self.config.llm.concurrency,
                    counts,
                )
            )

            await producer_task
            await in_queue.join()
            await asyncio.gather(*worker_tasks)
            await out_queue.join()
            await updater_task
        finally:
            fetch_executor.shutdown(wait=True)
            update_executor.shutdown(wait=True)

        return counts.processed, counts.failed, abort_event.is_set()
