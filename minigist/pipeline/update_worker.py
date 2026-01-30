import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import markdown
import nh3
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from minigist.constants import MARKDOWN_CONTENT_WITH_WATERMARK, MAX_RETRIES_PER_ENTRY, RETRY_DELAY_SECONDS
from minigist.exceptions import MinifluxApiError
from minigist.logging import format_log_preview, get_logger
from minigist.miniflux_client import MinifluxClient
from minigist.models import Entry
from minigist.pipeline.base_worker import BaseWorker
from minigist.pipeline.types import OutQueueItem

logger = get_logger(__name__)


class UpdateWorker(BaseWorker):
    def __init__(
        self,
        miniflux_client: MinifluxClient,
        record_failure: Callable[[], None],
        abort_event: asyncio.Event,
    ) -> None:
        super().__init__(record_failure, abort_event)
        self.miniflux_client = miniflux_client

    def _render_entry_content(self, entry: Entry, summary: str) -> str:
        formatted_content = MARKDOWN_CONTENT_WITH_WATERMARK.format(
            summary_content=summary, original_article_content=entry.content
        )
        new_html_content_for_miniflux = markdown.markdown(formatted_content)
        return nh3.clean(new_html_content_for_miniflux)

    def _update_entry_with_retry(self, entry_id: int, content: str, log_context: dict[str, object]) -> None:
        @retry(
            stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
            wait=wait_fixed(RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type(MinifluxApiError),
            before_sleep=lambda rs: self._log_retry_attempt(rs, "update_miniflux_entry", log_context),
            reraise=True,
        )
        def _update() -> None:
            self.miniflux_client.update_entry(entry_id=entry_id, content=content, log_context=log_context)

        _update()

    async def run(
        self,
        loop: asyncio.AbstractEventLoop,
        out_queue: asyncio.Queue[OutQueueItem | None],
        update_executor: ThreadPoolExecutor,
        llm_concurrency: int,
        counts: dict[str, int],
    ) -> None:
        worker_sentinels = 0

        while worker_sentinels < llm_concurrency:
            item = await out_queue.get()
            if item is None:
                worker_sentinels += 1
                out_queue.task_done()
                continue

            if self.abort_event.is_set():
                out_queue.task_done()
                continue

            entry = item.entry
            summary = item.summary
            log_context = item.log_context
            error = item.error

            if error or not summary:
                logger.error(
                    "Action failed after all retries for entry",
                    **log_context,
                    error_type=type(error).__name__ if error else "Unknown",
                    error=str(error) if error else "Unknown error",
                )
                out_queue.task_done()
                continue

            logger.debug(
                "Generated summary",
                **log_context,
                summary_length=len(summary),
                preview=format_log_preview(summary),
            )

            sanitized_html_content = self._render_entry_content(entry, summary)

            try:
                await loop.run_in_executor(
                    update_executor,
                    self._update_entry_with_retry,
                    entry.id,
                    sanitized_html_content,
                    log_context,
                )
                counts["processed"] += 1
                logger.info("Successfully processed entry", **log_context)
            except MinifluxApiError as e:
                logger.error(
                    "Action failed after all retries for entry",
                    **log_context,
                    error_type=type(e).__name__,
                    error=str(e),
                )
                self._record_failure()
            finally:
                out_queue.task_done()
