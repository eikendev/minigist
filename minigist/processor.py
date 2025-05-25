import markdown
import nh3
from tenacity import RetryCallState, retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from .config import AppConfig
from .constants import (
    FAILED_ENTRIES_ABORT_THRESHOLD,
    MARKDOWN_CONTENT_WITH_WATERMARK,
    MAX_RETRIES_PER_ENTRY,
    RETRY_DELAY_SECONDS,
    WATERMARK_DETECTOR,
)
from .downloader import Downloader
from .exceptions import (
    ArticleFetchError,
    LLMServiceError,
    MinifluxApiError,
    TooManyFailuresError,
)
from .logging import format_log_preview, get_logger
from .miniflux_client import MinifluxClient
from .models import Entry, ProcessingStats
from .summarizer import Summarizer

logger = get_logger(__name__)


def _log_retry_attempt(retry_state: RetryCallState, action_name: str, entry_details: dict) -> None:
    """Log a retry attempt."""
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        f"Action '{action_name}' failed, retrying...",
        **entry_details,
        attempt=retry_state.attempt_number,
        max_retries=MAX_RETRIES_PER_ENTRY,
        error_type=type(exception).__name__ if exception else "N/A",
        error=str(exception) if exception else "N/A",
    )


class Processor:
    def __init__(self, config: AppConfig, dry_run: bool = False):
        self.config = config
        self.client = MinifluxClient(config.miniflux, dry_run=dry_run)
        self.summarizer = Summarizer(config.llm)
        self.downloader = Downloader(config.scraping)
        self.dry_run = dry_run

    def _filter_unsummarized_entries(self, entries: list[Entry]) -> list[Entry]:
        unsummarized = [entry for entry in entries if WATERMARK_DETECTOR not in entry.content]
        logger.debug(
            "Filtered entries for summarization",
            total_entries=len(entries),
            unsummarized_count=len(unsummarized),
            already_summarized_count=len(entries) - len(unsummarized),
        )
        return unsummarized

    def _process_single_entry(self, entry: Entry) -> bool:
        entry_log_details = {"entry_id": entry.id, "url": entry.url, "title": entry.title}
        logger.debug("Processing entry", **entry_log_details)

        @retry(
            stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
            wait=wait_fixed(RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type((ArticleFetchError, LLMServiceError)),
            before_sleep=lambda rs: _log_retry_attempt(rs, "fetch_content", entry_log_details),
            reraise=True,
        )
        def _fetch_content_with_retry() -> str:
            return self.downloader.fetch_content(entry.url)

        @retry(
            stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
            wait=wait_fixed(RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type((ArticleFetchError, LLMServiceError)),
            before_sleep=lambda rs: _log_retry_attempt(rs, "generate_summary", entry_log_details),
            reraise=True,
        )
        def _generate_summary_with_retry(text: str) -> str:
            return self.summarizer.generate_summary(text)

        @retry(
            stop=stop_after_attempt(MAX_RETRIES_PER_ENTRY),
            wait=wait_fixed(RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type(MinifluxApiError),
            before_sleep=lambda rs: _log_retry_attempt(rs, "update_miniflux_entry", entry_log_details),
            reraise=True,
        )
        def _update_entry_with_retry(entry_id: int, content: str) -> None:
            self.client.update_entry(entry_id=entry_id, content=content)

        try:
            article_text = _fetch_content_with_retry()

            logger.debug(
                "Article text ready for summarization",
                **entry_log_details,
                text_length=len(article_text),
                preview=format_log_preview(article_text),
            )

            summary = _generate_summary_with_retry(article_text)

            logger.debug(
                "Generated summary",
                **entry_log_details,
                summary_length=len(summary),
                preview=format_log_preview(summary),
            )

            formatted_content = MARKDOWN_CONTENT_WITH_WATERMARK.format(
                summary_content=summary, original_article_content=entry.content
            )
            new_html_content_for_miniflux = markdown.markdown(formatted_content)
            sanitized_html_content = nh3.clean(new_html_content_for_miniflux)

            _update_entry_with_retry(entry_id=entry.id, content=sanitized_html_content)

            logger.info("Successfully processed entry", **entry_log_details)
            return True

        except (ArticleFetchError, LLMServiceError, MinifluxApiError) as e:
            logger.error(
                "Action failed after all retries for entry",
                **entry_log_details,
                error_type=type(e).__name__,
                error=str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "Unhandled error during processing of single entry",
                **entry_log_details,
                error_type=type(e).__name__,
                error=str(e),
            )
            return False

    def run(self) -> ProcessingStats:
        processed_successfully_count = 0
        failed_entries_count = 0

        try:
            all_fetched_entries = self.client.get_entries(self.config.filters)
        except MinifluxApiError as e:
            logger.critical("Failed to fetch initial entries from Miniflux", error=str(e))
            raise
        except Exception as e:
            logger.critical("Unexpected error during initial Miniflux setup", error=str(e))
            raise

        if not all_fetched_entries:
            logger.info("No matching unread entries found from Miniflux")
            return ProcessingStats(total_considered=0, processed_successfully=0, failed_processing=0)

        unsummarized_entries = self._filter_unsummarized_entries(all_fetched_entries)
        total_entries_considered = len(unsummarized_entries)

        if not unsummarized_entries:
            logger.info("All fetched entries have already been summarized")
            return ProcessingStats(
                total_considered=total_entries_considered,
                processed_successfully=0,
                failed_processing=0,
            )

        logger.info(
            "Attempting to process unsummarized entries",
            total_fetched=len(all_fetched_entries),
            total_considered=total_entries_considered,
        )

        for entry_count, entry in enumerate(unsummarized_entries, 1):
            logger.debug(
                "Processing entry",
                current_progress=f"{entry_count}/{total_entries_considered}",
                entry_id=entry.id,
            )

            if self._process_single_entry(entry):
                processed_successfully_count += 1
            else:
                failed_entries_count += 1

            if failed_entries_count >= FAILED_ENTRIES_ABORT_THRESHOLD:
                logger.critical(
                    "Aborting processing because too many entries failed",
                    failed_count=failed_entries_count,
                    attempted_this_run=entry_count,
                    total_considered=total_entries_considered,
                )
                raise TooManyFailuresError(
                    f"Processing aborted after {entry_count} of {total_entries_considered} "
                    f"entries attempted, due to {failed_entries_count} failures"
                )

        logger.debug(
            "Processing run complete",
            total_considered=total_entries_considered,
            successfully_processed=processed_successfully_count,
            failed_after_retries=failed_entries_count,
        )
        return ProcessingStats(
            total_considered=total_entries_considered,
            processed_successfully=processed_successfully_count,
            failed_processing=failed_entries_count,
        )

    def close_downloader(self):
        try:
            self.downloader.close()
            logger.debug("Downloader session closed")
        except Exception as e:
            logger.warning("Failed to close downloader HTTP session cleanly", error=str(e))
