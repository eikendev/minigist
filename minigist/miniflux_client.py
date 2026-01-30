from miniflux import Client  # type: ignore

from .config import FetchConfig, MinifluxConfig
from .exceptions import MinifluxApiError
from .logging import format_log_preview, get_logger
from .models import Category, EntriesResponse, Entry, Feed, FeedsResponse

logger = get_logger(__name__)


class MinifluxClient:
    def __init__(self, config: MinifluxConfig, dry_run: bool = False):
        self.client = Client(base_url=str(config.url), api_key=config.api_key)
        self.dry_run = dry_run

        if dry_run:
            logger.warning("Running in dry run mode; no updates will be made")

    def get_entries(self, feed_ids: list[int] | None, fetch_config: FetchConfig) -> list[Entry]:
        params = {
            "status": "unread",
            "direction": "desc",
            "order": "published_at",
            "limit": fetch_config.limit,
        }

        logger.debug("Fetching entries", parameters=params)
        all_entries = []

        try:
            if feed_ids:
                for feed_id in feed_ids:
                    raw_response = self.client.get_feed_entries(feed_id=feed_id, **params)
                    response = EntriesResponse.model_validate(raw_response)
                    all_entries.extend(response.entries)
            else:
                raw_response = self.client.get_entries(**params)
                response = EntriesResponse.model_validate(raw_response)
                all_entries = response.entries

        except Exception as e:
            logger.error("Failed to fetch entries from Miniflux", error=str(e))
            raise MinifluxApiError("Failed to fetch entries") from e

        logger.info("Fetched unread entries", count=len(all_entries))
        return all_entries

    def update_entry(self, entry_id: int, content: str, log_context: dict[str, object]):
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

        try:
            self.client.update_entry(entry_id=entry_id, content=content)
        except Exception as e:
            logger.error(
                "Failed to update entry",
                **log_context,
                error=str(e),
            )
            raise MinifluxApiError(f"Failed to update entry ID {entry_id}") from e

    def get_categories(self) -> list[Category]:
        logger.debug("Fetching categories metadata")

        try:
            raw_response = self.client.get_categories()
            return [Category.model_validate(category) for category in raw_response]
        except Exception as e:
            logger.error("Failed to fetch categories from Miniflux", error=str(e))
            raise MinifluxApiError("Failed to fetch categories") from e

    def get_feeds(self) -> list[Feed]:
        logger.debug("Fetching feeds metadata")

        try:
            raw_response = self.client.get_feeds()
            response = FeedsResponse.model_validate({"feeds": raw_response})
            return response.feeds
        except Exception as e:
            logger.error("Failed to fetch feeds from Miniflux", error=str(e))
            raise MinifluxApiError("Failed to fetch feeds") from e
