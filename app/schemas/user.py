from pydantic import BaseModel
from typing import Optional, List


class PreferencesRequest(BaseModel):
    topics: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    sub_topics: Optional[List[str]] = None  # ["football", "basketball"] 
    digest_frequency: Optional[str] = None  # daily | weekly
    digest_time: Optional[str] = None       # HH:MM
    digest_day: Optional[str] = None        # mon~sun
    ai_summary_depth: Optional[str] = None  # brief | balanced | deep
    dark_mode: Optional[bool] = None


class UserStatsResponse(BaseModel):
    total_read: int
    weekly_read: int
    top_topics: List[str]
    total_attendance: int
    current_streak: int
    max_streak: int
