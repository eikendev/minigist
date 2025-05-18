from minigist.config import ScrapingConfig
from minigist.downloader import Downloader


class TestDownloaderShouldUsePure:
    def test_should_use_pure_no_base_urls_configured(self):
        config = ScrapingConfig(pure_api_token="test_token", pure_base_urls=[])
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("https://example.com/article")

    def test_should_use_pure_url_matches_pattern(self):
        config = ScrapingConfig(
            pure_api_token="test_token",
            pure_base_urls=["https://example.com/", "https://another.org/blog"],
        )
        downloader = Downloader(scraping_config=config)
        assert downloader._should_use_pure("https://example.com/article/123")
        assert downloader._should_use_pure("https://another.org/blog/post-title")

    def test_should_use_pure_url_does_not_match_pattern(self):
        config = ScrapingConfig(
            pure_api_token="test_token",
            pure_base_urls=["https://example.com/", "https://another.org/blog"],
        )
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("https://different.com/page")
        assert not downloader._should_use_pure("http://example.com/article")  # Scheme mismatch
        assert not downloader._should_use_pure("https://example.com")  # No trailing path part

    def test_should_use_pure_url_partially_matches_but_not_prefix(self):
        config = ScrapingConfig(pure_api_token="test_token", pure_base_urls=["https://example.com/specific/"])
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("https://example.com/article")

    def test_should_use_pure_empty_url(self):
        config = ScrapingConfig(pure_api_token="test_token", pure_base_urls=["https://example.com/"])
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("")

    def test_should_use_pure_base_urls_is_none_when_loaded(self):
        config_data = {"pure_api_token": "test_token", "pure_base_urls": None}
        config = ScrapingConfig.model_validate(config_data)
        downloader = Downloader(scraping_config=config)
        assert not downloader._should_use_pure("https://example.com/article")
        assert config.pure_base_urls == []
