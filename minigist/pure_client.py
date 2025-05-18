import time
from collections import deque
from urllib.parse import urlparse, urlunparse

import requests

from .logging import get_logger

logger = get_logger(__name__)

DEFAULT_PUREMD_API_BASE_URL = "https://pure.md/"
DEFAULT_USER_AGENT = "minigist"
DEFAULT_TIMEOUT_SECONDS = 30
REQUEST_WINDOW_SECONDS = 60.0
MAX_REQUESTS_PER_WINDOW_NO_TOKEN = 6


class PureMDClient:
    def __init__(
        self,
        api_token: str | None,
        base_url: str = DEFAULT_PUREMD_API_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.api_token = api_token
        self.base_url = base_url
        self.headers = {"User-Agent": user_agent}
        if self.api_token:
            self.headers["x-puremd-api-token"] = self.api_token
        else:
            self._request_timestamps: deque[float] = deque(maxlen=MAX_REQUESTS_PER_WINDOW_NO_TOKEN)
            logger.warning(
                "Using pure.md without API token",
                rate_limit_requests=MAX_REQUESTS_PER_WINDOW_NO_TOKEN,
                rate_limit_window_seconds=int(REQUEST_WINDOW_SECONDS),
            )

    def _apply_rate_limit_delay_if_needed(self):
        """Checks if rate limit is about to be hit and sleeps if necessary."""
        now = time.monotonic()

        while self._request_timestamps and self._request_timestamps[0] <= now - REQUEST_WINDOW_SECONDS:
            self._request_timestamps.popleft()

        if len(self._request_timestamps) >= MAX_REQUESTS_PER_WINDOW_NO_TOKEN:
            oldest_in_window_request_time = self._request_timestamps[0]
            time_until_window_resets = (oldest_in_window_request_time + REQUEST_WINDOW_SECONDS) - now

            if time_until_window_resets > 0:
                wait_time = time_until_window_resets
                logger.info(
                    "Rate limit delay activated",
                    sleep_seconds=round(wait_time, 2),
                    current_requests_in_window=len(self._request_timestamps),
                    max_requests_per_window=MAX_REQUESTS_PER_WINDOW_NO_TOKEN,
                    window_seconds=int(REQUEST_WINDOW_SECONDS),
                )
                time.sleep(wait_time)
                now = time.monotonic()

        self._request_timestamps.append(now)

    def _prepare_request_url(self, target_url: str) -> str:
        parsed_base = urlparse(self.base_url)
        path = parsed_base.path

        if not path:
            path = "/"
        elif not path.endswith("/"):
            path += "/"

        base_url_normalized = urlunparse(
            (
                parsed_base.scheme,
                parsed_base.netloc,
                path,
                parsed_base.params,
                parsed_base.query,
                parsed_base.fragment,
            )
        )
        return base_url_normalized + target_url

    def fetch_markdown_content(self, target_url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str | None:
        if not self.api_token:
            self._apply_rate_limit_delay_if_needed()

        request_url = self._prepare_request_url(target_url)

        logger.debug(
            "Fetching content with pure.md",
            target_url=target_url,
            request_url=request_url,
        )
        try:
            response = requests.get(request_url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            logger.error(
                "HTTP error fetching content from pure.md",
                url=target_url,
                status_code=e.response.status_code if e.response else "N/A",
                response_text=e.response.text[:200] if e.response else "N/A",
                error=str(e),
            )
            return None
        except requests.exceptions.RequestException as e:
            logger.error(
                "RequestException fetching content from pure.md",
                url=target_url,
                error=str(e),
            )
            return None
        except Exception as e:
            logger.error(
                "Unexpected error fetching content from pure.md",
                url=target_url,
                error=str(e),
            )
            return None
