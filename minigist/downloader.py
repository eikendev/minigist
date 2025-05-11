from typing import Optional

from seleniumbase import SB  # type: ignore

from .logging import get_logger

logger = get_logger(__name__)


class Downloader:
    def __init__(self, uc=True, browser="chrome", headless=False, max_attempts=4):
        self._ctx = SB(uc=uc, browser=browser, xvfb=True)
        self.sb = self._ctx.__enter__()

    def fetch_html(self, url: str) -> Optional[str]:
        try:
            logger.debug(
                "Attempting to open URL with reconnect",
                url=url,
            )
            self.sb.activate_cdp_mode(url)
            self.sb.uc_gui_click_captcha()

            html = self.sb.cdp.get_element_html("body")
            if not html:
                logger.warning("Retrieved empty page source", url=url)
                return None

            return html

        except Exception as e:
            logger.error("Failed to fetch page HTML", url=url, error=str(e))
            return None

    def close(self):
        try:
            self._ctx.__exit__(None, None, None)
        except Exception as e:
            logger.warning(
                "Failed to close browser driver cleanly",
                error=str(e),
            )
