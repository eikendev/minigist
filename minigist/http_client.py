"""Shared HTTP client construction and retrying GET requests."""

from collections.abc import Mapping

import httpx2
from tenacity import RetryCallState, Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from .constants import MAX_RETRIES_PER_ENTRY, RETRY_DELAY_SECONDS
from .logging import get_logger

logger = get_logger(__name__)

RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})


def create_http_client(headers: Mapping[str, str], transport: httpx2.BaseTransport | None = None) -> httpx2.Client:
    """Create an HTTP client that follows redirects and sends the given default headers."""
    return httpx2.Client(headers=headers, follow_redirects=True, transport=transport)


def is_retryable_error(exception: BaseException) -> bool:
    """Return whether a request failure is transient and worth retrying."""
    if isinstance(exception, httpx2.TransportError):
        return True

    return isinstance(exception, httpx2.HTTPStatusError) and exception.response.status_code in RETRYABLE_STATUS_CODES


def _log_retry_attempt(retry_state: RetryCallState, url: str, log_context: Mapping[str, object]) -> None:
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "retrying http request",
        **log_context,
        url=url,
        attempt=retry_state.attempt_number,
        max_attempts=MAX_RETRIES_PER_ENTRY,
        error_type=type(exception).__name__ if exception else "N/A",
        error=str(exception) if exception else "N/A",
    )


def get_with_retry(
    client: httpx2.Client,
    url: str,
    timeout: float,
    log_context: Mapping[str, object] | None = None,
) -> httpx2.Response:
    """Perform a GET request and raise for status, retrying transient failures.

    Transport errors and responses with a status code in RETRYABLE_STATUS_CODES are
    retried up to MAX_RETRIES_PER_ENTRY attempts. The final exception is re-raised
    unchanged, so callers can handle httpx2 exceptions as usual.
    """
    retryer = Retrying(
        stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
        wait=wait_fixed(RETRY_DELAY_SECONDS),
        retry=retry_if_exception(is_retryable_error),
        before_sleep=lambda rs: _log_retry_attempt(rs, url, log_context or {}),
        reraise=True,
    )

    def _get() -> httpx2.Response:
        response = client.get(url, timeout=timeout)
        response.raise_for_status()
        return response

    return retryer(_get)
