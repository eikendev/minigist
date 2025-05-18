import json

import requests
import trafilatura

from .config import ScrapingConfig
from .logging import get_logger
from .pure_client import DEFAULT_TIMEOUT_SECONDS, DEFAULT_USER_AGENT, PureMDClient

logger = get_logger(__name__)


class Downloader:
    def __init__(self, scraping_config: ScrapingConfig, user_agent: str = DEFAULT_USER_AGENT):
        self.scraping_config = scraping_config
        self.pure_client = PureMDClient(api_token=scraping_config.pure_api_token, user_agent=user_agent)
        self.http_session = requests.Session()
        self.http_session.headers.update({"User-Agent": user_agent})

    def _should_use_pure(self, url: str) -> bool:
        if not self.scraping_config.pure_base_urls:
            logger.debug("Not using pure.md as no base URLs are configured")
            return False

        for base_url_pattern in self.scraping_config.pure_base_urls:
            if url.startswith(base_url_pattern):
                logger.debug(
                    "URL matches pure.md base URL pattern",
                    url=url,
                    pattern=base_url_pattern,
                )
                return True

        logger.debug(
            "Not using pure.md: URL does not match any base patterns",
            url=url,
            configured_patterns=self.scraping_config.pure_base_urls,
        )
        return False

    def _extract_text_from_html(self, html: str, url: str) -> str | None:
        try:
            extracted_json_str = trafilatura.extract(
                html,
                output_format="json",
                with_metadata=True,
                include_comments=False,
            )
        except Exception as e:
            logger.error("Trafilatura extraction failed", url=url, error=str(e))
            return None

        if not extracted_json_str:
            logger.warning("Trafilatura returned no content", url=url)
            return None

        try:
            content_data = json.loads(extracted_json_str)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON from trafilatura output",
                url=url,
                error=str(e),
                raw_output_preview=extracted_json_str[:200],
            )
            return None

        text = content_data.get("text")
        if not text or not text.strip():
            logger.warning(
                "No text content in trafilatura extracted data or text is empty",
                url=url,
            )
            return None

        return text

    def _fetch_and_parse_html_via_http_get(self, url: str, timeout: int) -> str | None:
        logger.info("Attempting standard HTTP GET and parse", url=url)

        html_content: str | None = None
        try:
            response = self.http_session.get(url, timeout=timeout)
            response.raise_for_status()
            html_content = response.text
        except requests.exceptions.HTTPError as e:
            logger.error(
                "HTTP error during standard GET",
                url=url,
                status_code=e.response.status_code if e.response else "N/A",
                error=str(e),
            )
            return None
        except requests.exceptions.RequestException as e:
            logger.error("RequestException during standard GET", url=url, error=str(e))
            return None
        except Exception as e:
            logger.error(
                "Unexpected error during standard GET",
                url=url,
                error=str(e),
            )
            return None

        if not html_content:
            logger.warning("Standard HTTP GET returned no HTML content", url=url)
            return None

        return self._extract_text_from_html(html_content, url)

    def fetch_content(self, url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str | None:
        if self._should_use_pure(url):
            logger.info("Fetching content via pure.md", url=url)
            content = self.pure_client.fetch_markdown_content(url, timeout=timeout)
            if content:
                return content
            else:
                logger.warning("pure.md fetch failed", url=url)
                return None

        return self._fetch_and_parse_html_via_http_get(url, timeout=timeout)

    def close(self):
        try:
            self.http_session.close()
        except Exception as e:
            logger.warning("Failed to close downloader HTTP session cleanly", error=str(e))
