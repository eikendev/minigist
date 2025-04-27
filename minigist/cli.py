import sys
from typing import Optional

import click

from minigist import config, exceptions, notification
from minigist.logging import configure_logging, get_logger
from minigist.processor import Processor

MINIGIST_ENV_PREFIX = "MINIGIST"

logger = get_logger(__name__)


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
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
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
    config_file: Optional[str],
    log_level: str,
    dry_run: bool,
):
    """Fetch entries, summarize, and update Miniflux."""
    configure_logging(log_level)

    try:
        app_config = config.load_app_config(config_file)
    except exceptions.ConfigError as e:
        logger.critical("Configuration error", error=str(e))
        sys.exit(1)

    notifier = notification.AppriseNotifier(app_config.notifications.urls)

    try:
        processor = Processor(app_config, dry_run=dry_run)
        processor.run()
    except Exception as e:
        logger.critical("An error occurred during processing", error=str(e))
        notifier.notify(
            title="Minigist Critical Error",
            body=f"An error occurred during processing: {e}",
        )
        sys.exit(1)


if __name__ == "__main__":
    cli()
