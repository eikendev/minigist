#!/usr/bin/env python3

import sys
import os
import markdown

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from minigist import config as app_config_loader
from minigist import constants
from minigist.logging import configure_logging, get_logger, format_log_preview
from minigist.miniflux_client import MinifluxClient

logger = get_logger("remove_summary")

def find_original_content(summarized_html_content: str) -> str | None:
    logger.debug("Attempting to find original content in HTML.", content_preview=format_log_preview(summarized_html_content, 200))
    if constants.WATERMARK_DETECTOR not in summarized_html_content:
        logger.debug("Watermark detector text not found in content. This should not happen if called after initial check.",
                     watermark_detector=constants.WATERMARK_DETECTOR)
        return None

    html_watermark_block = markdown.markdown(constants.WATERMARK).strip()
    logger.debug("Generated HTML watermark block for search.",
                 expected_html_watermark_block=format_log_preview(html_watermark_block, 100))

    idx_watermark_start = summarized_html_content.find(html_watermark_block)
    logger.debug("Result of searching for HTML watermark block.",
                 idx_watermark_start=idx_watermark_start)

    if idx_watermark_start == -1:
        logger.error("Full HTML watermark block not found, despite watermark detector text being present. "
                     "This indicates an inconsistency or unexpected content structure.",
                     watermark_detector=constants.WATERMARK_DETECTOR)
        return None

    logger.debug("Found full HTML watermark block in content.")
    search_start_for_hr = idx_watermark_start + len(html_watermark_block)

    hr_tag = "<hr/>"
    logger.debug("Searching for HR tag to identify end of summary.",
                 hr_tag_to_find=hr_tag,
                 search_start_index=search_start_for_hr)
    idx_hr = summarized_html_content.find(hr_tag, search_start_for_hr)
    logger.debug("Result of searching for HR tag.",
                 idx_hr_tag=idx_hr)

    if idx_hr == -1:
        logger.error("HR tag not found after the HTML watermark block. Cannot determine start of original content.",
                     hr_tag_searched=hr_tag,
                     searched_from_index=search_start_for_hr)
        return None

    logger.debug("Found HR tag, indicating separation point.", hr_tag_found=hr_tag)
    original_content_start_idx = idx_hr + len(hr_tag)

    while original_content_start_idx < len(summarized_html_content) and \
          summarized_html_content[original_content_start_idx] == '\n':
        original_content_start_idx += 1
    logger.debug("Determined start index of original content after stripping leading newlines.",
                 final_original_content_start_idx=original_content_start_idx)
    return summarized_html_content[original_content_start_idx:]

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Remove summaries from Miniflux articles.")
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO).",
    )
    args = parser.parse_args()

    configure_logging(args.log_level.upper())
    logger.info("Starting script to remove summary from Miniflux articles.")
    logger.debug(f"Log level set to {args.log_level.upper()}")

    try:
        cfg = app_config_loader.load_app_config(config_path_option=None)
        logger.info("Configuration loaded successfully.")
        miniflux_client = MinifluxClient(cfg.miniflux, dry_run=False)
        all_entries = miniflux_client.get_entries(cfg.filters)

        if not all_entries:
            logger.info("No entries found based on current filters.")
            sys.exit(0)

        logger.info(f"Fetched {len(all_entries)} entries.")

        processed_count = 0

        for i, entry in enumerate(all_entries):
            logger.info(f"Checking entry {i+1}/{len(all_entries)}", entry_id=entry.id, title=entry.title)
            logger.debug("Entry content snippet", snippet=format_log_preview(entry.content, 200))

            if constants.WATERMARK_DETECTOR not in entry.content:
                logger.info(f"Watermark detector ('{constants.WATERMARK_DETECTOR}') NOT FOUND in content. Skipping.", entry_id=entry.id)
                continue

            logger.info(f"Watermark detector ('{constants.WATERMARK_DETECTOR}') FOUND in content.", entry_id=entry.id)
            extracted_original = find_original_content(entry.content)

            if extracted_original is None:
                logger.warning("Could NOT extract original content. Skipping.", entry_id=entry.id)
                continue

            logger.info("Successfully extracted original content.", entry_id=entry.id, title=entry.title)

            try:
                confirm = input(f"  Proceed to remove summary from entry ID {entry.id} ('{entry.title}')? (y/N): ")
            except KeyboardInterrupt:
                logger.info("\nScript interrupted by user during confirmation. Exiting.")
                sys.exit(0)

            if confirm.lower() != 'y':
                logger.info(f"User declined. Skipping update for entry ID {entry.id}.")
                continue

            logger.info(f"User confirmed. Updating entry with original content.", entry_id=entry.id)
            try:
                miniflux_client.update_entry(entry_id=entry.id, content=extracted_original)
                logger.info(f"Successfully removed summary from entry.", entry_id=entry.id)
                processed_count += 1
            except Exception as update_e:
                logger.error(f"Failed to update entry ID {entry.id}", error=str(update_e), exc_info=True)

        if processed_count == 0:
            logger.info("No entries were modified in this run.")
        else:
            logger.info(f"Finished processing. Modified {processed_count} entries.")

    except KeyboardInterrupt:
        logger.info("Script interrupted by user during initial setup or entry fetching. Exiting.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An unexpected error occurred", error=str(e), exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
