import os
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from pydantic.functional_validators import BeforeValidator

from minigist.constants import (
    DEFAULT_FETCH_LIMIT,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_MINIFLUX_TIMEOUT_SECONDS,
    DEFAULT_SCRAPE_TIMEOUT_SECONDS,
    DEFAULT_SYSTEM_PROMPT,
    MINIGIST_ENV_PREFIX,
)
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
    timeout_seconds: float = Field(
        DEFAULT_MINIFLUX_TIMEOUT_SECONDS,
        description="Timeout for Miniflux API requests in seconds.",
    )


class LLMConfig(BaseModel):
    model: str = Field(
        "google/gemini-2.5-flash-lite",
        description="Base model identifier to use for summarization.",
    )
    api_key: str = Field(
        ...,
        description="API key for the LLM service.",
    )
    base_url: str = Field(
        "https://openrouter.ai/api/v1",
        description="Base URL for the LLM service API.",
    )
    timeout_seconds: float = Field(
        DEFAULT_LLM_TIMEOUT_SECONDS,
        description="Timeout for LLM requests in seconds.",
    )


class NotificationConfig(BaseModel):
    urls: list[str] = Field(default_factory=list, description="List of Apprise notification URLs.")


class FetchConfig(BaseModel):
    limit: int | None = Field(DEFAULT_FETCH_LIMIT, description="Maximum number of entries to fetch per feed.")


def ensure_list_if_none(v: Any) -> list[str]:
    if v is None:
        return []
    return v


class ScrapingConfig(BaseModel):
    pure_api_token: str | None = Field(None, description="API token for the pure.md service.")
    pure_base_urls: Annotated[list[str], BeforeValidator(ensure_list_if_none)] = Field(
        default_factory=list,
        description="List of base URL prefixes for which pure.md should always be used.",
    )
    timeout_seconds: float = Field(
        DEFAULT_SCRAPE_TIMEOUT_SECONDS,
        description="Timeout for HTTP fetch requests in seconds.",
    )


class PromptConfig(BaseModel):
    id: str = Field(..., description="Identifier for the prompt.")
    system_prompt: str = Field(DEFAULT_SYSTEM_PROMPT, description="System prompt text to guide summarization.")


class TargetConfig(BaseModel):
    prompt_id: str = Field(..., description="Prompt identifier to use for this target.")
    feed_ids: list[int] | None = Field(
        None,
        description="List of feed IDs that should use this prompt.",
    )
    category_ids: list[int] | None = Field(
        None,
        description="List of category IDs whose feeds should use this prompt.",
    )
    use_pure: bool = Field(False, description="Whether to prefer pure.md for this target.")


class AppConfig(BaseModel):
    default_prompt_id: str | None = Field(
        None,
        description="Optional default prompt ID to use when no targets are configured.",
    )
    prompts: list[PromptConfig]
    targets: list[TargetConfig] = Field(default_factory=list)
    fetch: FetchConfig = Field(default_factory=lambda: FetchConfig.model_construct())
    llm: LLMConfig
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
    _apply_env_overrides(config_data)

    try:
        app_config = AppConfig(**config_data)
    except ValidationError as e:
        logger.error("Error validating application configuration", error=str(e))
        raise ConfigError("Invalid or incomplete configuration") from e

    _validate_app_config(app_config)

    if app_config.fetch.limit is not None and app_config.fetch.limit < DEFAULT_FETCH_LIMIT:
        logger.warning(
            "The 'fetch_limit' is set to a low value",
            fetch_limit=app_config.fetch.limit,
            min_recommended_fetch_limit=DEFAULT_FETCH_LIMIT,
        )

    return app_config


def _apply_env_overrides(config_data: dict) -> None:
    miniflux_key = os.getenv(f"{MINIGIST_ENV_PREFIX}_MINIFLUX_API_KEY")
    llm_key = os.getenv(f"{MINIGIST_ENV_PREFIX}_LLM_API_KEY")

    if miniflux_key:
        config_data.setdefault("miniflux", {})["api_key"] = miniflux_key
    if llm_key:
        config_data.setdefault("llm", {})["api_key"] = llm_key


def _validate_app_config(app_config: AppConfig) -> None:
    if not app_config.prompts:
        logger.error("Validation failed: no prompts configured")
        raise ConfigError("At least one prompt must be configured")

    prompt_ids = [prompt.id for prompt in app_config.prompts]
    if len(prompt_ids) != len(set(prompt_ids)):
        logger.error("Validation failed: duplicate prompt IDs detected")
        raise ConfigError("Prompt IDs must be unique")

    if app_config.default_prompt_id and app_config.default_prompt_id not in prompt_ids:
        logger.error(
            "Validation failed: default_prompt_id does not exist",
            default_prompt_id=app_config.default_prompt_id,
        )
        raise ConfigError(f"default_prompt_id '{app_config.default_prompt_id}' does not match any configured prompt")

    if not app_config.targets:
        logger.info("No targets configured; default prompt will be used for all unread entries")
        return

    available_prompt_ids = set(prompt_ids)
    seen_feed_ids: set[int] = set()

    for target in app_config.targets:
        if target.prompt_id not in available_prompt_ids:
            logger.error("Validation failed: target references unknown prompt ID", prompt_id=target.prompt_id)
            raise ConfigError(f"Target references unknown prompt_id '{target.prompt_id}'")

        has_feeds = bool(target.feed_ids)
        has_categories = bool(target.category_ids)

        if not has_feeds and not has_categories:
            logger.error("Validation failed: target missing feed_ids and category_ids", prompt_id=target.prompt_id)
            raise ConfigError("Each target must specify at least one feed_id or category_id")

        if target.feed_ids:
            for feed_id in target.feed_ids:
                if feed_id in seen_feed_ids:
                    logger.error(
                        "Validation failed: feed ID assigned to multiple targets",
                        feed_id=feed_id,
                        prompt_id=target.prompt_id,
                    )
                    raise ConfigError(f"Feed ID {feed_id} is assigned to multiple targets")
                seen_feed_ids.add(feed_id)
