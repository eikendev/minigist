from typing import List

import markdown

from .config import AppConfig
from .constants import WATERMARK, WATERMARK_DETECTOR
from .downloader import Downloader
from .logging import get_logger
from .miniflux_client import MinifluxClient
from .models import Entry
from .summarizer import Summarizer

logger = get_logger(__name__)


class Processor:
    def __init__(self, config: AppConfig, dry_run: bool = False):
        self.config = config
        self.client = MinifluxClient(config.miniflux, dry_run=dry_run)
        self.summarizer = Summarizer(config.ai)
        self.downloader = Downloader()
        logger.debug("Processor initialized", dry_run=dry_run)

    def _filter_unsummarized_entries(self, entries: List[Entry]) -> List[Entry]:
        unsummarized = [
            entry for entry in entries if WATERMARK_DETECTOR not in entry.content
        ]
        logger.debug(
            "Filtered entries",
            total=len(entries),
            unsummarized=len(unsummarized),
            filtered=len(entries) - len(unsummarized),
        )
        return unsummarized

    def _process_single_entry(self, entry: Entry):
        logger.debug("Processing entry", entry_id=entry.id, title=entry.title)

        html = self.downloader.fetch_html(entry.url)
        if not html:
            logger.warning("Failed to fetch HTML", entry_id=entry.id, url=entry.url)
            return

        article_text = self.summarizer.parse_html(html, entry.url)
        if not article_text:
            logger.warning(
                "No article text extracted", entry_id=entry.id, url=entry.url
            )
            return

        logger.debug(
            "Fetched article text",
            preview=f"{article_text[:100]}..."
            if len(article_text) > 100
            else article_text,
        )

        summary = self.summarizer.generate_summary(article_text)
        logger.debug(
            "Generated summary",
            preview=f"{summary[:100]}..." if len(summary) > 100 else summary,
        )

        markdown_content = f"{summary}\n\n---\n\n{WATERMARK}"
        new_content = markdown.markdown(markdown_content)

        self.client.update_entry(entry_id=entry.id, content=new_content)
        return

    def run(self) -> None:
        logger.debug("Starting minigist processor")

        entries = self.client.get_entries(self.config.filters)

        if not entries:
            logger.info("No matching unread entries found")
            return

        logger.debug("Fetched entries", count=len(entries))

        entries = self._filter_unsummarized_entries(entries)

        if not entries:
            logger.info("All entries have already been summarized")
            return

        logger.info(
            "Processing entries",
            count=len(entries),
            titles=[entry.title for entry in entries],
        )

        for entry in entries:
            self._process_single_entry(entry)

        self.downloader.close()

        logger.info("Successfully processed entries", count=len(entries))
