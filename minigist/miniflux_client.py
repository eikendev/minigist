"""Miniflux API client wrapper with retry handling."""

from collections.abc import Callable
from functools import partial
from typing import TypeVar

from miniflux import Client  # type: ignore
from tenacity import RetryCallState, Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from .config import FetchConfig, MinifluxConfig
from .constants import MAX_RETRIES_PER_ENTRY, RETRY_DELAY_SECONDS
from .exceptions import MinifluxApiError
from .logging import format_log_preview, get_logger
from .models import EntriesResponse, Entry, Feed, FeedsResponse

logger = get_logger(__name__)
T = TypeVar("T")


class MinifluxClient:
    """Wrap Miniflux API calls with retry and error handling."""

    def __init__(self, config: MinifluxConfig, dry_run: bool = False):
        """Initialize the Miniflux client with configuration and dry-run mode."""
        self.client = Client(
            base_url=str(config.url),
            api_key=config.api_key,
            timeout=config.timeout_seconds,
        )
        self.dry_run = dry_run

        if dry_run:
            logger.warning("Running in dry run mode; no updates will be made")

    def _log_retry_attempt(self, retry_state: RetryCallState, action_name: str) -> None:
        """Log a retry attempt for a Miniflux API operation."""
        exception = retry_state.outcome.exception() if retry_state.outcome else None
        logger.warning(
            f"Action '{action_name}' failed, retrying...",
            attempt=retry_state.attempt_number,
            error=str(exception) if exception else "Unknown error",
        )

    def _call_with_retry(self, action: Callable[[], T], action_name: str) -> T:
        """Execute a Miniflux API action with retry behavior."""
        retryer = Retrying(
            stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
            wait=wait_fixed(RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type(MinifluxApiError),
            before_sleep=lambda rs: self._log_retry_attempt(rs, action_name),
            reraise=True,
        )

        return retryer(action)

    def get_entries(self, feed_ids: list[int] | None, fetch_config: FetchConfig) -> list[Entry]:
        """Fetch unread entries from Miniflux with retries."""
        params: dict[str, object] = {
            "status": "unread",
            "direction": "desc",
            "order": "published_at",
            "limit": fetch_config.limit,
        }

        logger.debug("Fetching entries", parameters=params)

        if feed_ids:
            all_entries: list[Entry] = []

            for feed_id in feed_ids:
                entries = self._call_with_retry(
                    partial(self._get_feed_entries, feed_id=feed_id, params=params),
                    "get_miniflux_entries",
                )
                all_entries.extend(entries)
        else:
            all_entries = self._call_with_retry(
                lambda: self._get_entries(params=params),
                "get_miniflux_entries",
            )

        logger.info("Fetched unread entries", count=len(all_entries))
        return all_entries

    def _get_feed_entries(self, feed_id: int, params: dict[str, object]) -> list[Entry]:
        """Fetch entries for a single Miniflux feed without retries."""
        try:
            raw_response = self.client.get_feed_entries(feed_id=feed_id, **params)
            response = EntriesResponse.model_validate(raw_response)
            return response.entries
        except Exception as e:
            logger.error(
                "Failed to fetch entries from Miniflux",
                feed_id=feed_id,
                error=str(e),
            )
            raise MinifluxApiError(f"Failed to fetch entries for feed {feed_id}") from e

    def _get_entries(self, params: dict[str, object]) -> list[Entry]:
        """Fetch entries across all feeds without retries."""
        try:
            raw_response = self.client.get_entries(**params)
            response = EntriesResponse.model_validate(raw_response)
            return response.entries
        except Exception as e:
            logger.error("Failed to fetch entries from Miniflux", error=str(e))
            raise MinifluxApiError("Failed to fetch entries") from e

    def update_entry(self, entry_id: int, content: str, log_context: dict[str, object]) -> None:
        """Update entry content in Miniflux with retries."""
        logger.info(
            "Updating entry",
            **log_context,
            content_length=len(content),
            preview=format_log_preview(content),
        )

        if self.dry_run:
            logger.warning(
                "Would update entry; skipping due to dry run",
                **log_context,
            )
            return

        self._call_with_retry(
            lambda: self._update_entry(entry_id=entry_id, content=content, log_context=log_context),
            "update_miniflux_entry",
        )

    def _update_entry(self, entry_id: int, content: str, log_context: dict[str, object]) -> None:
        """Perform the Miniflux update call without retries."""
        try:
            self.client.update_entry(entry_id=entry_id, content=content)
        except Exception as e:
            logger.error(
                "Failed to update entry",
                **log_context,
                error=str(e),
            )
            raise MinifluxApiError(f"Failed to update entry ID {entry_id}") from e

    def get_feeds(self) -> list[Feed]:
        """Fetch Miniflux feeds metadata with retries."""
        logger.debug("Fetching feeds metadata")
        return self._call_with_retry(self._get_feeds, "get_miniflux_feeds")

    def _get_feeds(self) -> list[Feed]:
        """Perform the Miniflux feeds fetch without retries."""
        try:
            raw_response = self.client.get_feeds()
            response = FeedsResponse.model_validate({"feeds": raw_response})
            return response.feeds
        except Exception as e:
            logger.error("Failed to fetch feeds from Miniflux", error=str(e))
            raise MinifluxApiError("Failed to fetch feeds") from e
