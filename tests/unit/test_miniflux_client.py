from unittest.mock import MagicMock

from minigist.config import MinifluxConfig
from minigist.miniflux_client import MinifluxClient
from minigist.models import Feed


def test_disable_entry_updates_skips_update_in_dry_run():
    config = MinifluxConfig(url="https://miniflux.example.com", api_key="test_key")  # type: ignore[arg-type]
    client = MinifluxClient(config, dry_run=True)
    client.client = MagicMock()

    client.disable_entry_updates(Feed(id=1, title="A"))

    client.client.update_feed.assert_not_called()
