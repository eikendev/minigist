import pytest

from minigist.config import ScrapingConfig
from minigist.downloader import Downloader


class TestDownloaderShouldUsePure:
    @pytest.fixture
    def log_context(self):
        return {"processor_id": "1/1"}

    def test_should_use_pure_no_base_urls_configured(self, log_context):
        config = ScrapingConfig(pure_api_token="test_token", pure_base_urls=[])
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("https://example.com/article", log_context)

    def test_should_use_pure_url_matches_pattern(self, log_context):
        config = ScrapingConfig(
            pure_api_token="test_token",
            pure_base_urls=["https://example.com/", "https://another.org/blog"],
        )
        downloader = Downloader(scraping_config=config)
        assert downloader._should_use_pure("https://example.com/article/123", log_context)
        assert downloader._should_use_pure("https://another.org/blog/post-title", log_context)

    def test_should_use_pure_url_does_not_match_pattern(self, log_context):
        config = ScrapingConfig(
            pure_api_token="test_token",
            pure_base_urls=["https://example.com/", "https://another.org/blog"],
        )
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("https://different.com/page", log_context)
        assert not downloader._should_use_pure("http://example.com/article", log_context)  # Scheme mismatch
        assert not downloader._should_use_pure("https://example.com", log_context)  # No trailing path part

    def test_should_use_pure_url_partially_matches_but_not_prefix(self, log_context):
        config = ScrapingConfig(pure_api_token="test_token", pure_base_urls=["https://example.com/specific/"])
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("https://example.com/article", log_context)

    def test_should_use_pure_empty_url(self, log_context):
        config = ScrapingConfig(pure_api_token="test_token", pure_base_urls=["https://example.com/"])
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("", log_context)

    def test_should_use_pure_base_urls_is_none_when_loaded(self, log_context):
        config_data = {"pure_api_token": "test_token", "pure_base_urls": None}
        config = ScrapingConfig.model_validate(config_data)
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("https://example.com/article", log_context)
        assert config.pure_base_urls == []
