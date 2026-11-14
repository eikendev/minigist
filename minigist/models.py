from datetime import datetime

from pydantic import BaseModel


class Entry(BaseModel):
    id: int
    user_id: int
    feed_id: int
    title: str
    url: str
    comments_url: str = ""
    author: str = ""
    content: str = ""
    hash: str
    published_at: datetime
    created_at: datetime
    status: str
    share_code: str = ""
    starred: bool = False
    reading_time: int = 0


class EntriesResponse(BaseModel):
    total: int
    entries: list[Entry]


class ProcessingStats(BaseModel):
    total_considered: int
    processed_successfully: int
    failed_processing: int


class Category(BaseModel):
    id: int
    title: str


class Feed(BaseModel):
    id: int
    title: str
    category: Category | None = None
    crawler: bool = False
    ignore_entry_updates: bool = False

    @property
    def keeps_existing_entries(self) -> bool:
        """Return whether scheduled refreshes leave existing entries untouched."""
        return self.crawler or self.ignore_entry_updates


class FeedsResponse(BaseModel):
    feeds: list[Feed]
