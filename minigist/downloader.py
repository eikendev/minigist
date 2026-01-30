import json

import httpx
import trafilatura
from httpx_retries import RetryTransport

from .config import ScrapingConfig
from .constants import DEFAULT_HTTP_TIMEOUT_SECONDS
from .exceptions import ArticleFetchError
from .logging import get_logger
from .pure_client import DEFAULT_USER_AGENT, PureMDClient

logger = get_logger(__name__)


class Downloader:
    def __init__(self, scraping_config: ScrapingConfig, user_agent: str = DEFAULT_USER_AGENT):
        self.scraping_config = scraping_config
        self.pure_client = PureMDClient(api_token=scraping_config.pure_api_token, user_agent=user_agent)
        self.http_session = httpx.Client(
            transport=RetryTransport(),
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def _should_use_pure(self, url: str, log_context: dict[str, object]) -> bool:
        if not self.scraping_config.pure_base_urls:
            logger.debug("Not using pure.md as no base URLs are configured", **log_context)
            return False

        for base_url_pattern in self.scraping_config.pure_base_urls:
            if url.startswith(base_url_pattern):
                logger.debug(
                    "URL matches pure.md base URL pattern",
                    **log_context,
                    url=url,
                    pattern=base_url_pattern,
                )
                return True

        logger.debug(
            "Not using pure.md: URL does not match any base patterns",
            **log_context,
            url=url,
            configured_patterns=self.scraping_config.pure_base_urls,
        )
        return False

    def _extract_text_from_html(self, html: str, url: str, log_context: dict[str, object]) -> str:
        try:
            extracted_json_str = trafilatura.extract(
                html,
                output_format="json",
                with_metadata=True,
                include_comments=False,
            )
        except Exception as e:
            logger.error("Trafilatura extraction failed", **log_context, url=url, error=str(e))
            raise ArticleFetchError(f"Trafilatura extraction failed for {url}: {e}") from e

        if not extracted_json_str:
            logger.warning("Trafilatura returned no content", **log_context, url=url)
            raise ArticleFetchError(f"Trafilatura returned no content for {url}")

        try:
            content_data = json.loads(extracted_json_str)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON from trafilatura output",
                **log_context,
                url=url,
                error=str(e),
                raw_output_preview=extracted_json_str[:200],
            )
            raise ArticleFetchError(f"Failed to parse JSON from trafilatura for {url}: {e}") from e

        text = content_data.get("text")
        if not text or not text.strip():
            logger.warning(
                "No text content in trafilatura extracted data or text is empty",
                **log_context,
                url=url,
            )
            raise ArticleFetchError(f"No text content in trafilatura extracted data for {url}")

        return text

    def _fetch_and_parse_html_via_http_get(self, url: str, timeout: float, log_context: dict[str, object]) -> str:
        logger.info("Attempting standard HTTP GET and parse", **log_context, url=url)

        html_content: str | None = None
        try:
            response = self.http_session.get(url, timeout=timeout)
            response.raise_for_status()
            html_content = response.text
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error during standard GET",
                **log_context,
                url=url,
                status_code=e.response.status_code if e.response else "N/A",
                error=str(e),
            )
            raise ArticleFetchError(
                f"HTTP error {e.response.status_code if e.response else 'N/A'} during GET for {url}: {e}"
            ) from e
        except httpx.RequestError as e:
            logger.error("RequestException during standard GET", **log_context, url=url, error=str(e))
            raise ArticleFetchError(f"RequestException during GET for {url}: {e}") from e
        except Exception as e:
            logger.error(
                "Unexpected error during standard GET",
                **log_context,
                url=url,
                error=str(e),
            )
            raise ArticleFetchError(f"Unexpected error during GET for {url}: {e}") from e

        if not html_content:
            logger.warning("Standard HTTP GET returned no HTML content", **log_context, url=url)
            raise ArticleFetchError(f"Standard HTTP GET returned no HTML content for {url}")

        return self._extract_text_from_html(html_content, url, log_context)

    def fetch_content(
        self,
        url: str,
        log_context: dict[str, object],
        timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        force_use_pure: bool = False,
    ) -> str:
        log_context = log_context or {}
        use_pure = force_use_pure or self._should_use_pure(url, log_context)

        if use_pure:
            logger.info(
                "Fetching content via pure.md",
                **log_context,
                url=url,
                forced=force_use_pure,
            )
            content = self.pure_client.fetch_markdown_content(url, timeout=timeout)
            if content and content.strip():
                return content
            else:
                logger.warning("pure.md fetch failed or returned empty content", **log_context, url=url)
                raise ArticleFetchError(f"pure.md fetch failed or returned empty content for {url}")

        return self._fetch_and_parse_html_via_http_get(url, timeout=timeout, log_context=log_context)

    def close(self):
        try:
            self.http_session.close()
        except Exception as e:
            logger.warning("Failed to close downloader HTTP session cleanly", error=str(e))

        self.pure_client.close()
