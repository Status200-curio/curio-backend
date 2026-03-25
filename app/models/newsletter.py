import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class NewsletterHistory(Base):
    __tablename__ = "newsletter_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String, nullable=False)
    article_ids = Column(JSON, default=list)    # 발송된 기사 ID 목록
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
