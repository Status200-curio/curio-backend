# Alembic이 모든 테이블을 인식할 수 있도록 전체 모델 import
from .user import User, UserPreference, UserActivityLog
from .article import Article, ArticleView, UserArticleInteraction, UserArticleInsight
from .bookmark import Bookmark, BookmarkTag
from .newsletter import NewsletterHistory
from .chat import ChatSession, ChatMessage
from .search import SearchRecentQuery
