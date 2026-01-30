import asyncio
from collections.abc import Callable

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from minigist.constants import MAX_RETRIES_PER_ENTRY, RETRY_DELAY_SECONDS
from minigist.exceptions import LLMServiceError
from minigist.pipeline.base_worker import BaseWorker
from minigist.pipeline.types import InQueueItem, OutQueueItem
from minigist.summarizer import Summarizer


class LLMWorker(BaseWorker):
    def __init__(
        self,
        summarizer: Summarizer,
        prompt_lookup: dict[str, str],
        record_failure: Callable[[], None],
        abort_event: asyncio.Event,
    ) -> None:
        super().__init__(record_failure, abort_event)
        self.summarizer = summarizer
        self.prompt_lookup = prompt_lookup

    async def _generate_summary_with_retry(self, text: str, prompt_id: str, log_context: dict[str, object]) -> str:
        @retry(
            stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
            wait=wait_fixed(RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type(LLMServiceError),
            before_sleep=lambda rs: self._log_retry_attempt(rs, "generate_summary", log_context),
            reraise=True,
        )
        async def _generate() -> str:
            prompt = self.prompt_lookup[prompt_id]
            return await self.summarizer.generate_summary(text, prompt, log_context=log_context)

        return await _generate()

    async def run(
        self,
        in_queue: asyncio.Queue[InQueueItem | None],
        out_queue: asyncio.Queue[OutQueueItem | None],
    ) -> None:
        while True:
            item = await in_queue.get()
            if item is None:
                in_queue.task_done()
                break

            if self.abort_event.is_set():
                in_queue.task_done()
                continue

            entry = item.entry
            prompt_id = item.prompt_id
            article_text = item.article_text
            log_context = item.log_context

            try:
                summary = await self._generate_summary_with_retry(article_text, prompt_id, log_context)
                await out_queue.put(
                    OutQueueItem(
                        entry=entry,
                        summary=summary,
                        log_context=log_context,
                        error=None,
                    )
                )
            except LLMServiceError as e:
                self._record_failure()
                await out_queue.put(
                    OutQueueItem(
                        entry=entry,
                        summary=None,
                        log_context=log_context,
                        error=e,
                    )
                )
            except Exception as e:
                self._record_failure()
                await out_queue.put(
                    OutQueueItem(
                        entry=entry,
                        summary=None,
                        log_context=log_context,
                        error=e,
                    )
                )
            finally:
                in_queue.task_done()

        await out_queue.put(None)
