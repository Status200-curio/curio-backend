from pydantic import BaseModel
from typing import List
from datetime import datetime


class RecentQueryOut(BaseModel):
    id: str
    query: str
    searched_at: datetime

    class Config:
        from_attributes = True


class RecentQueryRequest(BaseModel):
    query: str
