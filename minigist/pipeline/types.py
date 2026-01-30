from dataclasses import dataclass

from minigist.models import Entry


@dataclass(frozen=True)
class InQueueItem:
    entry: Entry
    prompt_id: str
    article_text: str
    log_context: dict[str, object]


@dataclass(frozen=True)
class OutQueueItem:
    entry: Entry
    summary: str | None
    log_context: dict[str, object]
    error: Exception | None
