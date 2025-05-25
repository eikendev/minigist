import apprise

from .logging import get_logger

logger = get_logger(__name__)


class AppriseNotifier:
    def __init__(self, urls: list[str]):
        self.apobj = apprise.Apprise()
        self.has_urls = False

        if urls:
            for url in urls:
                if self.apobj.add(url):
                    logger.info("Added Apprise notification URL", url=url)
                    self.has_urls = True
                else:
                    logger.error("Failed to add invalid Apprise URL", url=url)
        else:
            logger.warning("No Apprise notification URLs configured")

    def notify(self, title: str, body: str) -> None:
        if not self.has_urls:
            logger.debug("Skipping notification as no valid Apprise URLs are configured")
            return

        try:
            logger.info("Sending notification", title=title)
            sent = self.apobj.notify(body=body, title=title)
            if sent:
                logger.debug("Notification sent successfully")
            else:
                logger.error("Failed to send notification to any configured Apprise URL")

        except Exception as e:
            logger.error("Error sending notification via Apprise", error=str(e))
