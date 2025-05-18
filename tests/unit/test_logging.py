from minigist.logging import format_log_preview


class TestFormatLogPreview:
    def test_empty_string(self):
        assert format_log_preview("") == ""

    def test_string_shorter_than_limit(self):
        text = "Hello, world!"
        assert format_log_preview(text, 80) == text

    def test_string_equal_to_limit(self):
        text = "a" * 80
        assert format_log_preview(text, 80) == text

    def test_string_longer_than_limit(self):
        text = "a" * 100
        expected = "a" * 80 + "..."
        assert format_log_preview(text, 80) == expected

    def test_string_with_newlines(self):
        text = "Hello\nworld\nthis is a test."
        expected_processed = "Hello world this is a test."
        assert format_log_preview(text, 80) == expected_processed

    def test_string_with_newlines_and_longer_than_limit(self):
        text = "Line one.\n" + "This is line two which is quite long and will exceed the limit."
        expected_processed_text = "Line one. This is line two which is quite long and will exceed the limit."
        expected_truncated = expected_processed_text[:50] + "..."
        assert format_log_preview(text, 50) == expected_truncated

    def test_custom_limit(self):
        text = "Short text"
        assert format_log_preview(text, 5) == "Short..."
        assert format_log_preview(text, 10) == "Short text"  # Exact length
        assert format_log_preview(text, 11) == "Short text"  # Longer than text

    def test_limit_of_zero(self):
        text = "Some text"
        assert format_log_preview(text, 0) == "..."

    def test_limit_of_one(self):
        text = "Some text"
        assert format_log_preview(text, 1) == "S..."
