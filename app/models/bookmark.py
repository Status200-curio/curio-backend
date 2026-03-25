import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id = Column(String, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tags = relationship("BookmarkTag", back_populates="bookmark", cascade="all, delete")

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article_bookmark"),
    )


class BookmarkTag(Base):
    __tablename__ = "bookmark_tags"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    bookmark_id = Column(String, ForeignKey("bookmarks.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)   # 태그 이름
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bookmark = relationship("Bookmark", back_populates="tags")
