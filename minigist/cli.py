import sys

import click

from minigist import config, exceptions, notification
from minigist.constants import MINIGIST_ENV_PREFIX
from minigist.logging import configure_logging, get_logger
from minigist.models import ProcessingStats
from minigist.processor import Processor

logger = get_logger(__name__)


def _handle_critical_error(
    error_instance: Exception,
    error_notifier: notification.AppriseNotifier,
    log_message: str,
    notification_message_prefix: str,
):
    """Logs a critical error, sends a notification, and exits the application."""
    logger.critical(log_message, error=str(error_instance), exc_info=False)
    error_notifier.notify(
        title="Error occurred during minigist run",
        body=f"{notification_message_prefix}: {error_instance}",
    )
    sys.exit(1)


@click.group(context_settings=dict(auto_envvar_prefix=MINIGIST_ENV_PREFIX))
def cli():
    """
    A tool that generates concise summaries for you Miniflux feeds.
    """
    pass


@cli.command()
@click.option(
    "--config-file",
    type=click.Path(dir_okay=False),
    help="Path to the YAML configuration file.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
    show_default=True,
    help="Set the logging level.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Perform a dry run without updating Miniflux.",
)
def run(
    config_file: str | None,
    log_level: str,
    dry_run: bool,
):
    """Fetch entries, summarize, and update Miniflux."""
    configure_logging(log_level)

    try:
        app_config = config.load_app_config(config_file)
        notifier = notification.AppriseNotifier(app_config.notifications.urls)

    except exceptions.ConfigError as e:
        logger.critical("Configuration error", error=str(e))
        sys.exit(1)

    processor = None
    stats = ProcessingStats(total_considered=0, processed_successfully=0, failed_processing=0)

    try:
        processor = Processor(app_config, dry_run=dry_run)
        stats = processor.run()

    except exceptions.TooManyFailuresError as e:
        _handle_critical_error(
            e,
            notifier,
            log_message="Processing aborted due to excessive entry failures",
            notification_message_prefix="Too many entry failures",
        )
    except exceptions.MinifluxApiError as e:
        _handle_critical_error(
            e,
            notifier,
            log_message="Miniflux API error occurred",
            notification_message_prefix="Miniflux API error",
        )
    except Exception as e:
        _handle_critical_error(
            e,
            notifier,
            log_message="An unexpected error occurred during processing",
            notification_message_prefix="An unexpected error occurred",
        )
    finally:
        if processor:
            processor.close_downloader()

    log_data = {
        "total_considered": stats.total_considered,
        "processed_successfully": stats.processed_successfully,
        "failed_processing": stats.failed_processing,
    }
    if stats.failed_processing > 0:
        logger.warning("Processing finished with failures", **log_data)
        summary_message = (
            f"Processing finished: {stats.total_considered} considered, "
            f"{stats.processed_successfully} processed, {stats.failed_processing} failed"
        )
        notifier.notify(title="minigist caught an error", body=summary_message)
    else:
        logger.info("Processing finished successfully", **log_data)


if __name__ == "__main__":
    cli()
