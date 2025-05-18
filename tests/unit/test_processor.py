from datetime import datetime
from unittest.mock import MagicMock

import pytest

from minigist.constants import WATERMARK_DETECTOR
from minigist.models import Entry
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
    config.llm.system_prompt = "Test system prompt"

    config.scraping = MagicMock()
    config.scraping.pure_api_token = "test_pure_token"
    config.scraping.pure_base_urls = []

    config.filters = MagicMock()
    config.filters.feed_ids = None
    config.filters.fetch_limit = 100

    config.notifications = MagicMock()
    config.notifications.urls = []
    return config


@pytest.fixture
def processor_instance(mock_app_config):
    processor = Processor(config=mock_app_config, dry_run=True)
    processor.client = MagicMock()
    processor.summarizer = MagicMock()
    processor.downloader = MagicMock()
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

    def test_filter_entry_content_is_empty(self, processor_instance: Processor):
        entries = [create_mock_entry(1, "")]
        filtered = processor_instance._filter_unsummarized_entries(entries)
        assert len(filtered) == 1
        assert filtered[0].id == 1
