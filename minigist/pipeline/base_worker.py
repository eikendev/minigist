import asyncio
from collections.abc import Callable

from tenacity import RetryCallState

from minigist.constants import MAX_RETRIES_PER_ENTRY
from minigist.logging import get_logger

logger = get_logger(__name__)


class BaseWorker:
    def __init__(self, record_failure: Callable[[], None], abort_event: asyncio.Event) -> None:
        self.record_failure = record_failure
        self.abort_event = abort_event

    def _record_failure(self) -> None:
        self.record_failure()

    def _log_retry_attempt(self, retry_state: RetryCallState, action_name: str, log_context: dict[str, object]) -> None:
        exception = retry_state.outcome.exception() if retry_state.outcome else None
        logger.warning(
            f"Action '{action_name}' failed, retrying...",
            **log_context,
            attempt=retry_state.attempt_number,
            max_retries=MAX_RETRIES_PER_ENTRY,
            error_type=type(exception).__name__ if exception else "N/A",
            error=str(exception) if exception else "N/A",
        )
