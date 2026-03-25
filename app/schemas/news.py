from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ArticleOut(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None           # AI 3줄 요약 (공통)
    insight: Optional[str] = None           # 개인화 인사이트 (유저별)
    source_name: Optional[str] = None
    original_url: str
    topic: Optional[str] = None
    tags: List[str] = []
    relevance_score: float = 0.0
    read_time_minutes: int = 3
    published_at: Optional[datetime] = None
    is_saved: bool = False
    user_feedback: Optional[str] = None     # like | dislike | None

    class Config:
        from_attributes = True


class FeedResponse(BaseModel):
    articles: List[ArticleOut]
    pagination: dict


class FeedbackRequest(BaseModel):
    feedback: str   # like | dislike | cancel
