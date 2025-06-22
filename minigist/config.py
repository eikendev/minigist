from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator

from minigist.constants import DEFAULT_FETCH_LIMIT, DEFAULT_SYSTEM_PROMPT
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


class LLMServiceConfig(BaseModel):
    model: str = Field(
        "google/gemini-2.0-flash-lite-001",
        description="Base model identifier to use for summarization.",
    )
    system_prompt: str = Field(
        DEFAULT_SYSTEM_PROMPT,
        description="System prompt to guide the LLM summarization.",
    )
    api_key: str = Field(
        ...,
        description="API key for the LLM service.",
    )
    base_url: str | None = Field(
        "https://openrouter.ai/api/v1",
        description="Base URL for the LLM service API.",
    )


class NotificationConfig(BaseModel):
    urls: list[str] = Field(default_factory=list, description="List of Apprise notification URLs.")


class FilterConfig(BaseModel):
    feed_ids: list[int] | None = Field(None, description="List of specific feed IDs to include (fetch all if None).")
    fetch_limit: int | None = Field(DEFAULT_FETCH_LIMIT, description="Maximum number of entries to fetch per feed.")


class ScrapingConfig(BaseModel):
    pure_api_token: str | None = Field(None, description="API token for the pure.md service.")
    pure_base_urls: list[str] = Field(
        default_factory=list,
        description="List of base URL prefixes for which pure.md should be used.",
    )

    @field_validator("pure_base_urls", mode="before")
    @classmethod
    def ensure_list_if_none(cls, v):
        if v is None:
            return []
        return v


class AppConfig(BaseModel):
    filters: FilterConfig = Field(default_factory=lambda: FilterConfig.model_construct())
    llm: LLMServiceConfig
    miniflux: MinifluxConfig
    notifications: NotificationConfig = Field(default_factory=lambda: NotificationConfig.model_construct())
    scraping: ScrapingConfig = Field(default_factory=lambda: ScrapingConfig.model_construct())


def find_config_file(config_option: str | None = None) -> Path:
    search_paths = ([Path(config_option)] if config_option else []) + DEFAULT_CONFIG_PATHS

    for path in search_paths:
        logger.debug("Checking path for config file", path=str(path))
        if path.is_file():
            logger.debug("Found config file", path=str(path))
            return path

    raise ConfigError("No valid config file found")


def load_config_from_file(file_path: Path) -> dict:
    try:
        with open(file_path) as f:
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


def load_app_config(config_path_option: str | None = None) -> AppConfig:
    config_file = find_config_file(config_path_option)
    config_data = load_config_from_file(config_file)

    try:
        app_config = AppConfig(**config_data)
    except ValidationError as e:
        logger.error("Error validating application configuration", error=str(e))
        raise ConfigError("Invalid or incomplete configuration") from e

    if app_config.filters.fetch_limit is not None and app_config.filters.fetch_limit < DEFAULT_FETCH_LIMIT:
        logger.warning(
            "The 'fetch_limit' is set to a low value",
            fetch_limit=app_config.filters.fetch_limit,
            min_recommended_fetch_limit=DEFAULT_FETCH_LIMIT,
        )

    return app_config
