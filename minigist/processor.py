import markdown

from .config import AppConfig
from .constants import WATERMARK, WATERMARK_DETECTOR
from .downloader import Downloader
from .logging import format_log_preview, get_logger
from .miniflux_client import MinifluxClient
from .models import Entry
from .summarizer import Summarizer

logger = get_logger(__name__)


class Processor:
    def __init__(self, config: AppConfig, dry_run: bool = False):
        self.config = config
        self.client = MinifluxClient(config.miniflux, dry_run=dry_run)
        self.summarizer = Summarizer(config.llm)
        self.downloader = Downloader(config.scraping)

    def _filter_unsummarized_entries(self, entries: list[Entry]) -> list[Entry]:
        unsummarized = [entry for entry in entries if WATERMARK_DETECTOR not in entry.content]
        logger.debug(
            "Filtered entries for summarization",
            total_entries=len(entries),
            unsummarized_count=len(unsummarized),
            already_summarized_count=len(entries) - len(unsummarized),
        )
        return unsummarized

    def _process_single_entry(self, entry: Entry):
        logger.debug("Processing entry", entry_id=entry.id, url=entry.url, title=entry.title)

        article_text = self.downloader.fetch_content(entry.url)

        if not article_text:
            logger.warning(
                "Failed to fetch or parse content for entry",
                entry_id=entry.id,
                url=entry.url,
            )
            return

        if not article_text.strip():
            logger.warning(
                "Fetched article text is empty, skipping summarization",
                entry_id=entry.id,
                url=entry.url,
            )
            return

        logger.debug(
            "Article text ready for summarization",
            entry_id=entry.id,
            url=entry.url,
            text_length=len(article_text),
            preview=format_log_preview(article_text),
        )

        summary = self.summarizer.generate_summary(article_text)

        if not summary:
            logger.warning(
                "Failed to generate summary or summary was empty",
                entry_id=entry.id,
                url=entry.url,
            )
            return

        logger.debug(
            "Generated summary",
            entry_id=entry.id,
            url=entry.url,
            summary_length=len(summary),
            preview=format_log_preview(summary),
        )

        markdown_content_with_watermark = f"{summary}\n\n{WATERMARK}\n\n---\n\n{entry.content}"
        new_html_content_for_miniflux = markdown.markdown(markdown_content_with_watermark)

        self.client.update_entry(entry_id=entry.id, content=new_html_content_for_miniflux)
        logger.info(
            "Successfully processed and updated entry",
            entry_id=entry.id,
            title=entry.title,
        )
        return

    def run(self) -> None:
        entries_to_process_count = 0

        try:
            all_fetched_entries = self.client.get_entries(self.config.filters)

            if not all_fetched_entries:
                logger.info("No matching unread entries found from Miniflux")
                return

            logger.debug("Fetched entries from Miniflux", count=len(all_fetched_entries))

            unsummarized_entries = self._filter_unsummarized_entries(all_fetched_entries)
            entries_to_process_count = len(unsummarized_entries)

            if not unsummarized_entries:
                logger.info("All fetched entries have already been summarized")
                return

            logger.info(
                "Attempting to process unsummarized entries",
                count=entries_to_process_count,
            )

            for entry_count, entry in enumerate(unsummarized_entries, 1):
                logger.debug(
                    "Processing entry",
                    current_count=entry_count,
                    total_to_process=entries_to_process_count,
                    entry_id=entry.id,
                    url=entry.url,
                )
                try:
                    self._process_single_entry(entry)
                except Exception as e:
                    logger.error(
                        "Unhandled error during processing of single entry, continuing",
                        entry_id=entry.id,
                        url=entry.url,
                        error=str(e),
                    )

        except Exception as e:
            logger.critical("Critical error during processor run", error=str(e))
        finally:
            self.downloader.close()
