from miniflux import Client  # type: ignore

from .config import FilterConfig, MinifluxConfig
from .exceptions import MinifluxApiError
from .logging import format_log_preview, get_logger
from .models import EntriesResponse, Entry

logger = get_logger(__name__)


class MinifluxClient:
    def __init__(self, config: MinifluxConfig, dry_run: bool = False):
        self.client = Client(base_url=str(config.url), api_key=config.api_key)
        self.dry_run = dry_run

        if dry_run:
            logger.warning("Running in dry run mode; no updates will be made")

    def get_entries(self, filters: FilterConfig) -> list[Entry]:
        params = {
            "status": "unread",
            "direction": "desc",
            "order": "published_at",
            "limit": filters.fetch_limit,
        }

        logger.debug("Fetching entries", parameters=params)
        all_entries = []

        try:
            if filters.feed_ids is None:
                raw_response = self.client.get_entries(**params)
                response = EntriesResponse.model_validate(raw_response)
                all_entries = response.entries

            else:
                for feed_id in filters.feed_ids:
                    raw_response = self.client.get_feed_entries(feed_id=feed_id, **params)
                    response = EntriesResponse.model_validate(raw_response)
                    all_entries.extend(response.entries)

        except Exception as e:
            logger.error("Failed to fetch entries from Miniflux", error=str(e))
            raise MinifluxApiError("Failed to fetch entries") from e

        logger.info("Fetched unread entries", count=len(all_entries))
        return all_entries

    def update_entry(self, entry_id: int, content: str):
        logger.debug(
            "Updating entry",
            entry_id=entry_id,
            content_length=len(content),
            preview=format_log_preview(content),
        )

        if self.dry_run:
            logger.warning("Would update entry; skipping due to dry run", entry_id=entry_id)
            return

        try:
            self.client.update_entry(entry_id=entry_id, content=content)
        except Exception as e:
            logger.error("Failed to update entry", entry_id=entry_id, error=str(e))
            raise MinifluxApiError(f"Failed to update entry ID {entry_id}") from e
