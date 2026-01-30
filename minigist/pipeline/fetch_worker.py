import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from minigist.downloader import Downloader
from minigist.exceptions import ArticleFetchError
from minigist.logging import format_log_preview, get_logger
from minigist.models import Entry
from minigist.pipeline.base_worker import BaseWorker
from minigist.pipeline.types import InQueueItem

logger = get_logger(__name__)


class FetchWorker(BaseWorker):
    def __init__(
        self,
        downloader: Downloader,
        total_considered_entries: int,
        use_targets: bool,
        feed_target_map: dict[int, tuple[str, bool]],
        default_prompt_id: str,
        record_failure: Callable[[], None],
        abort_event: asyncio.Event,
    ) -> None:
        super().__init__(record_failure, abort_event)
        self.downloader = downloader
        self.total_considered_entries = total_considered_entries
        self.use_targets = use_targets
        self.feed_target_map = feed_target_map
        self.default_prompt_id = default_prompt_id

    def _resolve_prompt_and_source(self, entry: Entry, log_context: dict[str, object]) -> tuple[str, bool] | None:
        if self.use_targets:
            target = self.feed_target_map.get(entry.feed_id)
            if not target:
                logger.warning(
                    "Entry was fetched without a matching target; skipping",
                    **log_context,
                )
                return None
            return target
        return self.default_prompt_id, False

    async def run(
        self,
        loop: asyncio.AbstractEventLoop,
        entries: list[Entry],
        in_queue: asyncio.Queue[InQueueItem | None],
        fetch_executor: ThreadPoolExecutor,
        llm_concurrency: int,
    ) -> None:
        for entry_count, entry in enumerate(entries, 1):
            if self.abort_event.is_set():
                break

            log_context: dict[str, object] = {
                "miniflux_entry_id": entry.id,
                "miniflux_feed_id": entry.feed_id,
                "processor_id": f"{entry_count}/{self.total_considered_entries}",
            }
            logger.debug("Processing entry", **log_context)

            target = self._resolve_prompt_and_source(entry, log_context)
            if not target:
                self._record_failure()
                continue
            prompt_id, use_pure = target

            try:
                article_text = await loop.run_in_executor(
                    fetch_executor,
                    self.downloader.fetch_content,
                    entry.url,
                    log_context,
                    use_pure,
                )
            except ArticleFetchError as e:
                logger.error(
                    "Action failed after all retries for entry",
                    **log_context,
                    error_type=type(e).__name__,
                    error=str(e),
                )
                self._record_failure()
                continue

            logger.debug(
                "Fetched article text for summarization",
                **log_context,
                text_length=len(article_text),
                preview=format_log_preview(article_text),
            )

            await in_queue.put(
                InQueueItem(
                    entry=entry,
                    prompt_id=prompt_id,
                    article_text=article_text,
                    log_context=log_context,
                )
            )

        for _ in range(llm_concurrency):
            await in_queue.put(None)
