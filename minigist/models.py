from datetime import datetime
from typing import List

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

    class Config:
        arbitrary_types_allowed = True


class EntriesResponse(BaseModel):
    total: int
    entries: List[Entry]
