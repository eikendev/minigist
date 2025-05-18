from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from minigist.config import AppConfig, load_app_config, load_config_from_file
from minigist.exceptions import ConfigError


def test_load_config_from_file_success(valid_config_dict):
    mock_yaml_content = yaml.dump(valid_config_dict)
    with patch("builtins.open", mock_open(read_data=mock_yaml_content)):
        result = load_config_from_file(Path("fake_path.yaml"))

    assert result == valid_config_dict


def test_load_config_from_file_empty():
    with (
        patch("builtins.open", mock_open(read_data="")),
        pytest.raises(ConfigError, match="Config file is empty"),
    ):
        load_config_from_file(Path("fake_path.yaml"))


def test_load_config_from_file_not_found():
    with (
        patch("builtins.open", side_effect=FileNotFoundError()),
        pytest.raises(ConfigError, match="Config file not found"),
    ):
        load_config_from_file(Path("nonexistent.yaml"))


def test_load_app_config_success(valid_config_dict, mock_config_path):
    with (
        patch("minigist.config.find_config_file", return_value=mock_config_path),
        patch("minigist.config.load_config_from_file", return_value=valid_config_dict),
    ):
        result = load_app_config("some/path")

        assert isinstance(result, AppConfig)
        assert str(result.miniflux.url) == "https://example.com/"
        assert result.miniflux.api_key == "test_miniflux_key"
        assert result.llm.api_key == "test_ai_key"
        assert result.llm.model == "test-model"


def test_load_app_config_validation_error(invalid_config_dict, mock_config_path):
    with (
        patch("minigist.config.find_config_file", return_value=mock_config_path),
        patch("minigist.config.load_config_from_file", return_value=invalid_config_dict),
        pytest.raises(ConfigError, match="Invalid or incomplete configuration"),
    ):
        load_app_config("some/path")


def test_load_app_config_config_error(mock_config_path):
    with (
        patch(
            "minigist.config.find_config_file",
            side_effect=ConfigError("No valid config file found"),
        ),
        pytest.raises(ConfigError, match="No valid config file found"),
    ):
        load_app_config("some/path")
