import logging
import sys

import structlog


def configure_logging(log_level_str: str = "INFO") -> None:
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    for logger_name in logging.root.manager.loggerDict:
        if not logger_name.startswith("minigist"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def format_log_preview(text: str, text_char_limit: int = 80) -> str:
    """
    Formats a string for log preview: replaces newlines, truncates to text_char_limit,
    and adds ellipsis if the original text (after newline replacement) is longer.
    """
    if not text:
        return ""
    processed_text = text.replace("\n", " ")
    if len(processed_text) > text_char_limit:
        return processed_text[:text_char_limit] + "..."
    return processed_text
