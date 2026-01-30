from pathlib import Path
from unittest.mock import mock_open

import pytest
import yaml


@pytest.fixture
def valid_config_dict():
    """Fixture providing a valid configuration dictionary."""
    return {
        "miniflux": {"url": "https://example.com", "api_key": "test_miniflux_key"},
        "llm": {
            "api_key": "test_ai_key",
            "model": "test-model",
            "base_url": "https://api.test.com",
        },
        "fetch": {"limit": 50},
        "prompts": [
            {"id": "default", "prompt": "Test prompt"},
        ],
        "targets": [
            {"prompt_id": "default", "feed_ids": [1]},
        ],
    }


@pytest.fixture(autouse=True)
def clear_minigist_env(monkeypatch):
    """Ensure config tests are not affected by external MINIGIST_* env vars."""
    monkeypatch.delenv("MINIGIST_MINIFLUX_API_KEY", raising=False)
    monkeypatch.delenv("MINIGIST_LLM_API_KEY", raising=False)


@pytest.fixture
def invalid_config_dict():
    """Fixture providing an invalid configuration dictionary (missing required fields)."""
    return {
        "miniflux": {
            "url": "https://example.com"
            # Missing api_key
        },
        "llm": {
            # Missing api_key
            "model": "test-model"
        },
        "fetch": {"limit": 50},
        "prompts": [
            {"id": "default", "prompt": "Test prompt"},
        ],
        "targets": [
            {"prompt_id": "default", "feed_ids": [1]},
        ],
    }


@pytest.fixture
def mock_config_file(valid_config_dict):
    """Fixture providing a mock file with valid YAML config content."""
    return mock_open(read_data=yaml.dump(valid_config_dict))


@pytest.fixture
def mock_config_path():
    """Fixture providing a mock config file path."""
    return Path("/mock/path/config.yaml")
