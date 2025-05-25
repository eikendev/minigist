from datetime import datetime

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(arbitrary_types_allowed=True)


class EntriesResponse(BaseModel):
    total: int
    entries: list[Entry]


class ProcessingStats(BaseModel):
    total_considered: int
    processed_successfully: int
    failed_processing: int
