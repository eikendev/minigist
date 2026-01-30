from collections import defaultdict

import markdown
import nh3
from tenacity import RetryCallState, retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from .config import AppConfig
from .constants import (
    FAILED_ENTRIES_ABORT_THRESHOLD,
    MARKDOWN_CONTENT_WITH_WATERMARK,
    MAX_RETRIES_PER_ENTRY,
    RETRY_DELAY_SECONDS,
    WATERMARK_DETECTOR,
)
from .downloader import Downloader
from .exceptions import (
    ArticleFetchError,
    ConfigError,
    LLMServiceError,
    MinifluxApiError,
    TooManyFailuresError,
)
from .logging import format_log_preview, get_logger
from .miniflux_client import MinifluxClient
from .models import Entry, ProcessingStats
from .summarizer import Summarizer

logger = get_logger(__name__)


def _log_retry_attempt(retry_state: RetryCallState, action_name: str, entry_details: dict) -> None:
    """Log a retry attempt."""
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        f"Action '{action_name}' failed, retrying...",
        **entry_details,
        attempt=retry_state.attempt_number,
        max_retries=MAX_RETRIES_PER_ENTRY,
        error_type=type(exception).__name__ if exception else "N/A",
        error=str(exception) if exception else "N/A",
    )


class Processor:
    def __init__(self, config: AppConfig, dry_run: bool = False):
        self.config = config
        self.client = MinifluxClient(config.miniflux, dry_run=dry_run)
        self.summarizer = Summarizer(config.llm)
        self.downloader = Downloader(config.scraping)
        self.dry_run = dry_run
        self.prompt_lookup = {prompt.id: prompt.system_prompt for prompt in config.prompts}
        self.feed_target_map: dict[int, tuple[str, bool]] = {}
        self.use_targets = bool(config.targets)
        default_prompt_id = config.default_prompt_id or (config.prompts[0].id if config.prompts else None)
        if default_prompt_id is None or default_prompt_id not in self.prompt_lookup:
            logger.error(
                "Default prompt ID is not configured or missing from prompts",
                default_prompt_id=default_prompt_id,
            )
            raise ConfigError("A valid default prompt must be configured")
        self.default_prompt_id = default_prompt_id

    def _filter_unsummarized_entries(self, entries: list[Entry]) -> list[Entry]:
        unsummarized = [entry for entry in entries if WATERMARK_DETECTOR not in entry.content]
        logger.debug(
            "Filtered entries for summarization",
            total_entries=len(entries),
            unsummarized_count=len(unsummarized),
            already_summarized_count=len(entries) - len(unsummarized),
        )
        return unsummarized

    def _build_feed_target_map(self) -> dict[int, tuple[str, bool]]:
        try:
            feeds = self.client.get_feeds()
        except MinifluxApiError as e:
            logger.critical("Failed to fetch feeds metadata from Miniflux", error=str(e))
            raise
        except Exception as e:
            logger.critical("Unexpected error while fetching feeds metadata", error=str(e))
            raise

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

    def _process_single_entry(self, entry: Entry, log_context: dict[str, object]) -> bool:
        if self.use_targets:
            target = self.feed_target_map.get(entry.feed_id)
            if not target:
                logger.warning(
                    "Entry was fetched without a matching target; skipping",
                    **log_context,
                )
                return False
            prompt_id, use_pure = target
        else:
            prompt_id, use_pure = self.default_prompt_id, False

        logger.debug("Processing entry", **log_context, url=entry.url, title=entry.title, prompt_id=prompt_id)

        @retry(
            stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
            wait=wait_fixed(RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type(LLMServiceError),
            before_sleep=lambda rs: _log_retry_attempt(rs, "generate_summary", log_context),
            reraise=True,
        )
        def _generate_summary_with_retry(text: str) -> str:
            system_prompt = self.prompt_lookup[prompt_id]
            return self.summarizer.generate_summary(text, system_prompt, log_context=log_context)

        @retry(
            stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
            wait=wait_fixed(RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type(MinifluxApiError),
            before_sleep=lambda rs: _log_retry_attempt(rs, "update_miniflux_entry", log_context),
            reraise=True,
        )
        def _update_entry_with_retry(entry_id: int, content: str) -> None:
            self.client.update_entry(entry_id=entry_id, content=content, log_context=log_context)

        try:
            article_text = self.downloader.fetch_content(
                entry.url,
                force_use_pure=use_pure,
                log_context=log_context,
            )

            logger.debug(
                "Fetched article text for summarization",
                **log_context,
                text_length=len(article_text),
                preview=format_log_preview(article_text),
            )

            summary = _generate_summary_with_retry(article_text)

            logger.debug(
                "Generated summary",
                **log_context,
                summary_length=len(summary),
                preview=format_log_preview(summary),
            )

            formatted_content = MARKDOWN_CONTENT_WITH_WATERMARK.format(
                summary_content=summary, original_article_content=entry.content
            )
            new_html_content_for_miniflux = markdown.markdown(formatted_content)
            sanitized_html_content = nh3.clean(new_html_content_for_miniflux)

            _update_entry_with_retry(entry_id=entry.id, content=sanitized_html_content)

            logger.info("Successfully processed entry", **log_context)
            return True

        except (ArticleFetchError, LLMServiceError, MinifluxApiError) as e:
            logger.error(
                "Action failed after all retries for entry",
                **log_context,
                error_type=type(e).__name__,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "Unhandled error during processing of single entry",
                **log_context,
                error_type=type(e).__name__,
                error=str(e),
            )
            return False

    def run(self) -> ProcessingStats:
        processed_successfully_count = 0
        failed_entries_count = 0

        if self.use_targets:
            try:
                self.feed_target_map = self._build_feed_target_map()
            except (MinifluxApiError, ConfigError) as e:
                logger.critical("Failed to resolve target mapping", error=str(e))
                raise
            except Exception as e:
                logger.critical("Unexpected error while resolving target mapping", error=str(e))
                raise

        effective_feed_ids = list(self.feed_target_map.keys()) if self.use_targets else None

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

        for entry_count, entry in enumerate(considered_entries, 1):
            entry_log_context: dict[str, object] = {
                "miniflux_entry_id": entry.id,
                "miniflux_feed_id": entry.feed_id,
                "processor_id": f"{entry_count}/{total_considered_entries}",
            }
            logger.debug(
                "Processing entry",
                **entry_log_context,
            )

            if self._process_single_entry(entry, entry_log_context):
                processed_successfully_count += 1
            else:
                failed_entries_count += 1

            if failed_entries_count >= FAILED_ENTRIES_ABORT_THRESHOLD:
                logger.critical(
                    "Aborting processing because too many entries failed",
                    failed_count=failed_entries_count,
                    attempted_this_run=entry_count,
                    total_considered=total_considered_entries,
                )
                raise TooManyFailuresError(
                    f"Processing aborted after {entry_count} of {total_considered_entries} "
                    f"entries attempted, due to {failed_entries_count} failures"
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

    def close_downloader(self):
        try:
            self.downloader.close()
            logger.debug("Downloader session closed")
        except Exception as e:
            logger.warning("Failed to close downloader HTTP session cleanly", error=str(e))
