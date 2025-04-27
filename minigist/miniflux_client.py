from typing import List

from miniflux import Client  # type: ignore

from .config import FilterConfig, MinifluxConfig
from .exceptions import MinifluxApiError
from .logging import get_logger
from .models import EntriesResponse, Entry

logger = get_logger(__name__)


class MinifluxClient:
    def __init__(self, config: MinifluxConfig, dry_run: bool = False):
        self.client = Client(base_url=str(config.url), api_key=config.api_key)
        self.dry_run = dry_run

        if dry_run:
            logger.warning("Running in dry run mode; no updates will be made")

    def get_entries(self, filters: FilterConfig) -> List[Entry]:
        params = {
            "status": "unread",
            "direction": "desc",
            "limit": 1,
        }

        logger.debug("Fetching entries", parameters=params)

        try:
            raw_response = self.client.get_entries(**params)
        except Exception as e:
            logger.error("Failed to fetch entries from Miniflux", error=str(e))
            raise MinifluxApiError("Failed to fetch entries") from e

        try:
            response = EntriesResponse.model_validate(raw_response)
        except Exception as e:
            logger.error("Failed to parse entries response", error=str(e))
            raise MinifluxApiError("Failed to parse entries response") from e

        entries = response.entries
        logger.info("Fetched unread entries", count=len(entries))

        return entries

    def update_entry(self, entry_id: int, content: str):
        logger.debug("Updating entry", entry_id=entry_id, content=content)

        if self.dry_run:
            logger.debug(
                "Would update entry; skipping due to dry run", entry_id=entry_id
            )
            return

        try:
            self.client.update_entry(entry_id=entry_id, content=content)
        except Exception as e:
            logger.error("Failed to update entry", entry_id=entry_id, error=str(e))
            raise MinifluxApiError(f"Failed to update entry ID {entry_id}") from e
