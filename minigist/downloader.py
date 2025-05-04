from typing import Optional

from seleniumbase import Driver


class Downloader:
    def __init__(self, uc=True, browser="chrome", headless=True):
        self.driver = Driver(uc=uc, browser=browser, headless=headless)

    def fetch_html(self, url: str) -> Optional[str]:
        try:
            self.driver.uc_open_with_reconnect(url, 4)
            return self.driver.page_source
        except Exception:
            return None

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass
