from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class BookmarkTagOut(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True


class BookmarkOut(BaseModel):
    id: str
    article_id: str
    title: str
    source_name: Optional[str] = None
    topic: Optional[str] = None
    tags: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class BookmarkTagUpdateRequest(BaseModel):
    tags: List[str]     # 태그 이름 목록으로 전체 교체
