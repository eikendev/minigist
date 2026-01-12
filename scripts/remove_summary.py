#!/usr/bin/env python3

import sys
import os

from bs4 import BeautifulSoup

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

    soup = BeautifulSoup(summarized_html_content, "html.parser")
    watermark_text_node = soup.find(string=lambda text: isinstance(text, str) and constants.WATERMARK_DETECTOR in text)

    if watermark_text_node is None:
        logger.error("Watermark detector text missing while attempting to remove summary.",
                     watermark_detector=constants.WATERMARK_DETECTOR)
        return None

    logger.debug("Located watermark detector node in parsed HTML.")

    watermark_block = watermark_text_node.find_parent()
    if watermark_block is None:
        logger.error("Unable to determine watermark block element around detector text.")
        return None

    logger.debug("Identified watermark block element.",
                 watermark_block_preview=format_log_preview(str(watermark_block), 200))

    hr_tag = watermark_block.find_next("hr")
    if hr_tag is None:
        logger.error("HR tag not found after watermark block. Cannot determine boundary to original content.")
        return None

    logger.debug("Found HR tag, indicating separation point.")

    original_fragments = []
    for sibling in hr_tag.next_siblings:
        if sibling is None:
            continue

        original_fragments.append(str(sibling))

    original_html = "".join(original_fragments).lstrip("\n")
    if not original_html:
        logger.warning("Extracted original HTML is empty after HR tag.")
        return None

    logger.debug("Successfully extracted original content using BeautifulSoup.",
                 original_content_preview=format_log_preview(original_html, 200))

    return original_html

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
    parser.add_argument(
        "--feed-id",
        type=int,
        default=None,
        help="Restrict processing to a single feed ID (default: fetch from all feeds).",
    )
    args = parser.parse_args()

    configure_logging(args.log_level.upper())
    logger.info("Starting script to remove summary from Miniflux articles.")
    logger.debug(f"Log level set to {args.log_level.upper()}")

    try:
        cfg = app_config_loader.load_app_config(config_path_option=None)
        logger.info("Configuration loaded successfully.")
        miniflux_client = MinifluxClient(cfg.miniflux, dry_run=False)
        feed_ids = [args.feed_id] if args.feed_id is not None else None
        if args.feed_id is not None:
            logger.info("Restricting fetch to feed ID.", feed_id=args.feed_id)
        all_entries = miniflux_client.get_entries(feed_ids=feed_ids, fetch_config=cfg.fetch)

        if not all_entries:
            logger.info("No entries found based on current fetch settings.")
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
            logger.info("Finished processing entries.", modified_count=processed_count)

    except KeyboardInterrupt:
        logger.info("Script interrupted by user during initial setup or entry fetching. Exiting.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An unexpected error occurred", error=str(e), exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
