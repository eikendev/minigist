from typing import Optional

from seleniumbase import Driver  # type: ignore

from .logging import get_logger

logger = get_logger(__name__)


class Downloader:
    def __init__(self, uc=True, browser="chrome", headless=False, max_attempts=4):
        self.driver = Driver(uc=uc, browser=browser, headless=headless)
        self.max_attempts = max_attempts

    def fetch_html(self, url: str) -> Optional[str]:
        try:
            logger.debug(
                "Attempting to open URL with reconnect",
                url=url,
                max_attempts=self.max_attempts,
            )
            self.driver.uc_open_with_reconnect(url, self.max_attempts)
            self.driver.uc_gui_click_captcha()

            html = self.driver.page_source
            if not html:
                logger.warning("Retrieved empty page source", url=url)
                return None

            return html

        except Exception as e:
            logger.error("Failed to fetch page HTML", url=url, error=str(e))
            return None

    def close(self):
        try:
            self.driver.quit()
        except Exception as e:
            logger.warning(
                "Failed to close browser driver cleanly",
                error=str(e),
            )
