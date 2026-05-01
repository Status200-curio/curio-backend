import uuid
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)  # Google OAuth는 NULL 허용
    name = Column(String, nullable=False)
    is_google = Column(Boolean, default=False)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    preference = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete")
    activity_logs = relationship("UserActivityLog", back_populates="user", cascade="all, delete")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topics = Column(JSON, default=list)             # ["ai", "economy", "sports"]
    keywords = Column(JSON, default=list)           # ["반도체", "ChatGPT"]
    sub_topics = Column(JSON, default=list)   # ["football", "basketball", "stock"]
    topic_weights = Column(JSON, default=dict)      # {"ai": 1.3, "economy": 0.8} ← 추가
    digest_frequency = Column(String, default="daily")  # daily | weekly
    digest_time = Column(String, default="08:00")   # HH:MM
    digest_day = Column(String, nullable=True)      # weekly일 때 요일 (mon~sun)
    ai_summary_depth = Column(String, default="balanced")  # brief | balanced | deep
    language = Column(String, default="ko")
    dark_mode = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="preference")


class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_date = Column(Date, nullable=False)    # KST 기준 날짜 (하루 1회 중복 방지)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="activity_logs")
