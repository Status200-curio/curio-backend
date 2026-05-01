import uuid
from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    content = Column(String, nullable=True)
    ai_summary = Column(String, nullable=True)          # Claude 3줄 요약 (공통 캐싱)
    source_name = Column(String, nullable=True)
    original_url = Column(String, unique=True, nullable=False)  # 중복 수집 방지
    topic = Column(String, nullable=True, index=True)   # ai | economy | sports ...
    tags = Column(JSON, default=list)
    relevance_score = Column(Float, default=0.0)
    read_time_minutes = Column(Integer, default=3)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ai_generated_at = Column(DateTime(timezone=True), nullable=True)  # NULL이면 요약 미생성
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ArticleView(Base):
    __tablename__ = "article_view"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())
    duration_seconds = Column(Integer, default=0, nullable=True)  # 최장 체류시간 (초)

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article_view"),
    )


class UserArticleInteraction(Base):
    __tablename__ = "user_article_interactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    feedback = Column(String, nullable=True)   # like | dislike | None
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article_interaction"),
    )


class UserArticleInsight(Base):
    __tablename__ = "user_article_insights"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    insight_text = Column(String, nullable=False)   # 유저별 개인화 인사이트
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article_insight"),
    )
