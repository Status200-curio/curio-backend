import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class SearchRecentQuery(Base):
    __tablename__ = "search_recent_queries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(String, nullable=False)
    searched_at = Column(DateTime(timezone=True), server_default=func.now())  # 재검색 시 갱신

    __table_args__ = (
        UniqueConstraint("user_id", "query", name="uq_user_search_query"),
    )
