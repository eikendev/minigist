from minigist.pure_client import DEFAULT_PUREMD_API_BASE_URL, PureMDClient


class TestPureMDClientPrepareRequestUrl:
    def test_default_base_url_simple_target(self):
        client = PureMDClient(api_token="test_token")
        target_url = "https://example.com/article"
        expected = DEFAULT_PUREMD_API_BASE_URL + target_url
        assert client._prepare_request_url(target_url) == expected

    def test_empty_target_url(self):
        client = PureMDClient(api_token="test_token")
        target_url = ""
        expected = DEFAULT_PUREMD_API_BASE_URL
        assert client._prepare_request_url(target_url) == expected

    def test_target_url_with_special_characters(self):
        client = PureMDClient(api_token="test_token")
        target_url = "https://example.com/path?query=value&another=param#fragment"
        expected = DEFAULT_PUREMD_API_BASE_URL + target_url
        assert client._prepare_request_url(target_url) == expected

    def test_custom_base_url_with_trailing_slash(self):
        custom_base = "https://custom.pure.md/api/v1/"
        client = PureMDClient(api_token="test_token", base_url=custom_base)
        target_url = "http://blog.com/post"
        expected = custom_base + target_url
        assert client._prepare_request_url(target_url) == expected

    def test_custom_base_url_without_trailing_slash(self):
        custom_base = "https://custom.pure.md/api/v1"  # No trailing slash
        client = PureMDClient(api_token="test_token", base_url=custom_base)
        target_url = "https://news.com/story.html"
        expected = custom_base + "/" + target_url
        assert client._prepare_request_url(target_url) == expected
