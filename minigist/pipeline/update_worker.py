"""Worker for updating Miniflux entries with generated summaries."""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import markdown
import nh3

from minigist.constants import MARKDOWN_CONTENT_WITH_WATERMARK
from minigist.exceptions import MinifluxApiError
from minigist.logging import format_log_preview, get_logger
from minigist.miniflux_client import MinifluxClient
from minigist.models import Entry
from minigist.pipeline.base_worker import BaseWorker
from minigist.pipeline.types import OutQueueItem

logger = get_logger(__name__)


class UpdateWorker(BaseWorker):
    """Update Miniflux entries after summarization."""

    def __init__(
        self,
        miniflux_client: MinifluxClient,
        record_failure: Callable[[], None],
        abort_event: asyncio.Event,
    ) -> None:
        """Initialize the update worker."""
        super().__init__(record_failure, abort_event)
        self.miniflux_client = miniflux_client

    def _render_entry_content(self, entry: Entry, summary: str) -> str:
        """Render the updated HTML content for a summarized entry."""
        formatted_content = MARKDOWN_CONTENT_WITH_WATERMARK.format(
            summary_content=summary, original_article_content=entry.content
        )
        new_html_content_for_miniflux = markdown.markdown(formatted_content)
        return nh3.clean(new_html_content_for_miniflux)

    async def run(
        self,
        loop: asyncio.AbstractEventLoop,
        out_queue: asyncio.Queue[OutQueueItem | None],
        update_executor: ThreadPoolExecutor,
        llm_concurrency: int,
        counts: dict[str, int],
    ) -> None:
        """Consume summaries from the queue and update Miniflux entries."""
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
                    self.miniflux_client.update_entry,
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
