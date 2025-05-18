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
            "system_prompt": "Test prompt",
            "base_url": "https://api.test.com",
        },
    }


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
    }


@pytest.fixture
def mock_config_file(valid_config_dict):
    """Fixture providing a mock file with valid YAML config content."""
    return mock_open(read_data=yaml.dump(valid_config_dict))


@pytest.fixture
def mock_config_path():
    """Fixture providing a mock config file path."""
    return Path("/mock/path/config.yaml")
