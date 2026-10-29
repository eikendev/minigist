import httpx2
import pytest

from minigist.constants import MAX_RETRIES_PER_ENTRY
from minigist.http_client import create_http_client, get_with_retry, is_retryable_error

URL = "https://example.com/article"


class SequenceTransport(httpx2.BaseTransport):
    """Transport that replays a fixed sequence of responses or exceptions."""

    def __init__(self, outcomes: list[httpx2.Response | Exception]):
        self.outcomes = list(outcomes)
        self.requests: list[httpx2.Request] = []

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("minigist.http_client.RETRY_DELAY_SECONDS", 0)


def make_client(outcomes: list[httpx2.Response | Exception]) -> tuple[httpx2.Client, SequenceTransport]:
    transport = SequenceTransport(outcomes)
    return create_http_client(headers={"User-Agent": "test"}, transport=transport), transport


class TestGetWithRetry:
    def test_returns_successful_response_without_retry(self):
        client, transport = make_client([httpx2.Response(200, text="hello")])

        response = get_with_retry(client, URL, timeout=1.0)

        assert response.text == "hello"
        assert len(transport.requests) == 1

    def test_sends_default_headers(self):
        client, transport = make_client([httpx2.Response(200)])

        get_with_retry(client, URL, timeout=1.0)

        assert transport.requests[0].headers["User-Agent"] == "test"

    @pytest.mark.parametrize("status_code", [429, 502, 503, 504])
    def test_retries_retryable_status_then_succeeds(self, status_code):
        client, transport = make_client([httpx2.Response(status_code), httpx2.Response(200, text="ok")])

        response = get_with_retry(client, URL, timeout=1.0)

        assert response.text == "ok"
        assert len(transport.requests) == 2

    def test_retries_transport_error_then_succeeds(self):
        client, transport = make_client([httpx2.ConnectError("boom"), httpx2.Response(200, text="ok")])

        response = get_with_retry(client, URL, timeout=1.0)

        assert response.text == "ok"
        assert len(transport.requests) == 2

    def test_gives_up_after_max_attempts_and_reraises(self):
        client, transport = make_client([httpx2.Response(503)] * MAX_RETRIES_PER_ENTRY)

        with pytest.raises(httpx2.HTTPStatusError) as exc_info:
            get_with_retry(client, URL, timeout=1.0)

        assert exc_info.value.response.status_code == 503
        assert len(transport.requests) == MAX_RETRIES_PER_ENTRY

    def test_gives_up_after_max_attempts_on_transport_error(self):
        client, transport = make_client([httpx2.ReadTimeout("slow")] * MAX_RETRIES_PER_ENTRY)

        with pytest.raises(httpx2.ReadTimeout):
            get_with_retry(client, URL, timeout=1.0)

        assert len(transport.requests) == MAX_RETRIES_PER_ENTRY

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 500])
    def test_does_not_retry_non_retryable_status(self, status_code):
        client, transport = make_client([httpx2.Response(status_code)])

        with pytest.raises(httpx2.HTTPStatusError) as exc_info:
            get_with_retry(client, URL, timeout=1.0)

        assert exc_info.value.response.status_code == status_code
        assert len(transport.requests) == 1

    def test_follows_redirects(self):
        client, transport = make_client(
            [
                httpx2.Response(302, headers={"Location": "https://example.com/moved"}),
                httpx2.Response(200, text="moved"),
            ]
        )

        response = get_with_retry(client, URL, timeout=1.0)

        assert response.text == "moved"
        assert str(transport.requests[1].url) == "https://example.com/moved"


class TestIsRetryableError:
    def test_transport_errors_are_retryable(self):
        assert is_retryable_error(httpx2.ConnectError("x"))
        assert is_retryable_error(httpx2.ReadTimeout("x"))
        assert is_retryable_error(httpx2.RemoteProtocolError("x"))

    def test_unrelated_errors_are_not_retryable(self):
        assert not is_retryable_error(ValueError("x"))
        assert not is_retryable_error(httpx2.InvalidURL("x"))
