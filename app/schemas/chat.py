from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ChatRequest(BaseModel):
    article_id: str
    session_id: Optional[str] = None    # None이면 새 세션 생성
    message: str


class ChatMessageOut(BaseModel):
    id: str
    role: str           # user | assistant
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionOut(BaseModel):
    id: str
    article_id: Optional[str] = None
    turn_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
