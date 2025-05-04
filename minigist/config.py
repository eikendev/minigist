from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, HttpUrl, ValidationError

from minigist.constants import DEFAULT_SYSTEM_PROMPT
from minigist.exceptions import ConfigError
from minigist.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_PATHS = [
    Path("~/.config/minigist/config.yaml").expanduser(),
    Path("~/.config/minigist/config.yml").expanduser(),
    Path("./config.yaml"),
    Path("./config.yml"),
    Path("/etc/minigist/config.yaml"),
    Path("/etc/minigist/config.yml"),
]


class MinifluxConfig(BaseModel):
    url: HttpUrl = Field(..., description="URL of the Miniflux instance.")
    api_key: str = Field(..., description="Miniflux API key.")


class AIServiceConfig(BaseModel):
    model: str = Field(
        "google/gemini-2.5-flash-preview",
        description="AI model identifier to use for summarization.",
    )
    system_prompt: str = Field(
        DEFAULT_SYSTEM_PROMPT,
        description="System prompt to guide the AI summarization.",
    )
    api_key: str = Field(
        ...,
        description="API key for the AI service.",
    )
    base_url: Optional[str] = Field(
        "https://openrouter.ai/api/v1",
        description="Base URL for the AI service API.",
    )


class NotificationConfig(BaseModel):
    urls: List[str] = Field(
        default_factory=list, description="List of Apprise notification URLs."
    )


class FilterConfig(BaseModel):
    feed_ids: Optional[List[int]] = Field(
        None, description="List of specific feed IDs to include (fetch all if None)."
    )
    fetch_limit: Optional[int] = Field(
        100, description="Maximum number of entries to fetch per feed."
    )


class AppConfig(BaseModel):
    miniflux: MinifluxConfig
    ai: AIServiceConfig
    notifications: NotificationConfig = Field(
        default_factory=lambda: NotificationConfig.model_construct()
    )
    filters: FilterConfig = Field(
        default_factory=lambda: FilterConfig.model_construct()
    )


def find_config_file(config_option: Optional[str] = None) -> Path:
    search_paths = (
        [Path(config_option)] if config_option else []
    ) + DEFAULT_CONFIG_PATHS

    for path in search_paths:
        logger.debug("Checking path for config file", path=str(path))
        if path.is_file():
            logger.debug("Found config file", path=str(path))
            return path

    raise ConfigError("No valid config file found")


def load_config_from_file(file_path: Path) -> dict:
    try:
        with open(file_path, "r") as f:
            config_data = yaml.safe_load(f)
    except FileNotFoundError as e:
        logger.error("Config file not found", path=str(file_path))
        raise ConfigError("Config file not found") from e
    except yaml.YAMLError as e:
        logger.error("Error parsing YAML file", path=str(file_path), error=str(e))
        raise ConfigError("Error parsing YAML file") from e
    except Exception as e:
        logger.error("Error reading config file", path=str(file_path), error=str(e))
        raise ConfigError("Error reading config file") from e

    if config_data is None:
        logger.warning("Config file is empty", path=str(file_path))
        raise ConfigError("Config file is empty")

    logger.debug("Loaded configuration", path=str(file_path))
    return config_data


def load_app_config(config_path_option: Optional[str] = None) -> AppConfig:
    config_file = find_config_file(config_path_option)
    config_data = load_config_from_file(config_file)

    try:
        app_config = AppConfig(**config_data)
    except ValidationError as e:
        logger.error("Error validating application configuration", error=str(e))
        raise ConfigError("Invalid or incomplete configuration") from e

    return app_config
