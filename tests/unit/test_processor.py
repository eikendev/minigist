from datetime import datetime
from unittest.mock import MagicMock

import pytest

from minigist.config import TargetConfig
from minigist.constants import WATERMARK_DETECTOR
from minigist.exceptions import ConfigError
from minigist.models import Category, Entry, Feed
from minigist.processor import Processor


@pytest.fixture
def mock_app_config():
    config = MagicMock()

    config.miniflux = MagicMock()
    config.miniflux.url = "http://miniflux.example.com"
    config.miniflux.api_key = "miniflux_api_key"

    config.llm = MagicMock()
    config.llm.model = "test-llm-model"
    config.llm.api_key = "test-llm-api-key"
    config.llm.base_url = "http://llm.example.com/v1"

    config.scraping = MagicMock()
    config.scraping.pure_api_token = "test_pure_token"
    config.scraping.pure_base_urls = []

    config.fetch = MagicMock()
    config.fetch.limit = 100

    config.notifications = MagicMock()
    config.notifications.urls = []
    config.default_prompt_id = None
    config.prompts = [MagicMock()]
    config.prompts[0].id = "default"
    config.prompts[0].prompt = "Test prompt"
    config.targets = [MagicMock()]
    config.targets[0].prompt_id = "default"
    config.targets[0].feed_ids = [1, 3]
    config.targets[0].category_ids = []
    config.targets[0].use_pure = False
    return config


@pytest.fixture
def processor_instance(mock_app_config):
    processor = Processor(config=mock_app_config, dry_run=True)
    processor.client = MagicMock()  # type: ignore[assignment]
    processor.summarizer = MagicMock()
    processor.downloader = MagicMock()
    processor.feed_target_map = {1: ("default", False), 2: ("default", True)}
    return processor


def create_mock_entry(entry_id: int, content: str) -> Entry:
    return Entry(
        id=entry_id,
        user_id=1,
        feed_id=1,
        title=f"Test Entry {entry_id}",
        url=f"http://example.com/{entry_id}",
        comments_url="",
        author="Test Author",
        content=content,
        hash="testhash",
        published_at=datetime.now(),
        created_at=datetime.now(),
        status="unread",
        share_code="",
        starred=False,
        reading_time=0,
    )


class TestProcessorFilterUnsummarizedEntries:
    def test_filter_no_entries(self, processor_instance: Processor):
        entries: list[Entry] = []
        filtered = processor_instance._filter_unsummarized_entries(entries)
        assert len(filtered) == 0

    def test_filter_all_unsummarized(self, processor_instance: Processor):
        entries = [
            create_mock_entry(1, "Content without watermark."),
            create_mock_entry(2, "Another fresh article."),
        ]
        filtered = processor_instance._filter_unsummarized_entries(entries)
        assert len(filtered) == 2
        assert filtered[0].id == 1
        assert filtered[1].id == 2

    def test_filter_all_summarized(self, processor_instance: Processor):
        entries = [
            create_mock_entry(1, f"Content with {WATERMARK_DETECTOR}."),
            create_mock_entry(2, f"Already processed. {WATERMARK_DETECTOR} here."),
        ]
        filtered = processor_instance._filter_unsummarized_entries(entries)
        assert len(filtered) == 0

    def test_filter_mixed_entries(self, processor_instance: Processor):
        entries = [
            create_mock_entry(1, "Needs summarization."),
            create_mock_entry(2, f"This one has the {WATERMARK_DETECTOR}."),
            create_mock_entry(3, "Another to process."),
            create_mock_entry(4, f"{WATERMARK_DETECTOR} is present."),
        ]
        filtered = processor_instance._filter_unsummarized_entries(entries)
        assert len(filtered) == 2
        assert filtered[0].id == 1
        assert filtered[1].id == 3

    def test_filter_entry_with_watermark_substring_but_not_exact(self, processor_instance: Processor):
        entries = [create_mock_entry(1, "Content that mentions 'Summarized by minigi' but not the full detector.")]
        filtered = processor_instance._filter_unsummarized_entries(entries)
        assert len(filtered) == 1
        assert filtered[0].id == 1


class TestProcessorBuildFeedTargetMap:
    def test_build_feed_target_map_resolves_feeds_and_categories(self, processor_instance: Processor):
        feed1 = Feed(id=1, title="A", category=Category(id=10, title="Cat 10"))
        feed2 = Feed(id=2, title="B", category=Category(id=20, title="Cat 20"))
        processor_instance.client = MagicMock()  # type: ignore[assignment]
        processor_instance.client.get_feeds.return_value = [feed1, feed2]
        processor_instance.config.targets = [
            TargetConfig(prompt_id="default", feed_ids=[1], category_ids=None, use_pure=False),
            TargetConfig(prompt_id="default", feed_ids=None, category_ids=[20], use_pure=True),
        ]

        feed_target_map = processor_instance._build_feed_target_map()

        assert feed_target_map[1] == ("default", False)
        assert feed_target_map[2] == ("default", True)

    def test_build_feed_target_map_conflicting_feed_assignment(self, processor_instance: Processor):
        feed1 = Feed(id=1, title="A", category=None)
        processor_instance.client = MagicMock()  # type: ignore[assignment]
        processor_instance.client.get_feeds.return_value = [feed1]
        processor_instance.config.targets = [
            TargetConfig(prompt_id="default", feed_ids=[1], category_ids=None, use_pure=False),
            TargetConfig(prompt_id="default", feed_ids=[1], category_ids=None, use_pure=False),
        ]

        with pytest.raises(ConfigError):
            processor_instance._build_feed_target_map()

    def test_filter_entry_content_is_empty(self, processor_instance: Processor):
        entries = [create_mock_entry(1, "")]
        filtered = processor_instance._filter_unsummarized_entries(entries)
        assert len(filtered) == 1
        assert filtered[0].id == 1
