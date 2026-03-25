from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserPreference
from app.models.article import Article, ArticleView, UserArticleInteraction
from app.schemas.news import FeedbackRequest
import uuid

router = APIRouter()


# GET /api/news/feed — 개인화 피드 조회
@router.get("/feed")
def get_feed(
    sort: str = Query("relevance", description="relevance | latest | popular"),
    topic: Optional[str] = Query(None, description="카테고리 필터"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 유저 관심사 조회
    pref = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id
    ).first()

    user_topics = pref.topics if pref and pref.topics else []

    # 특정 카테고리 필터 있으면 그것만, 없으면 관심사 전체
    if topic:
        topics_filter = [topic]
    elif user_topics:
        topics_filter = user_topics
    else:
        topics_filter = None  # 관심사 없으면 전체 기사

    # 기사 쿼리
    query = db.query(Article)

    if topics_filter:
        query = query.filter(Article.topic.in_(topics_filter))

    # 정렬
    if sort == "latest":
        query = query.order_by(Article.published_at.desc())
    elif sort == "relevance":
        query = query.order_by(Article.relevance_score.desc(), Article.published_at.desc())
    else:
        query = query.order_by(Article.published_at.desc())

    # 페이지네이션
    total = query.count()
    articles = query.offset((page - 1) * limit).limit(limit).all()

    # 유저가 저장/피드백한 기사 목록 조회
    saved_ids = set()
    feedback_map = {}

    if articles:
        article_ids = [a.id for a in articles]

        saved = db.query(ArticleView).filter(
            ArticleView.user_id == current_user.id,
            ArticleView.article_id.in_(article_ids)
        ).all()
        saved_ids = {s.article_id for s in saved}

        feedbacks = db.query(UserArticleInteraction).filter(
            UserArticleInteraction.user_id == current_user.id,
            UserArticleInteraction.article_id.in_(article_ids)
        ).all()
        feedback_map = {f.article_id: f.feedback for f in feedbacks}

    # 응답 구성
    result = []
    for article in articles:
        insight_text = None
        if user_topics:
            from app.models.article import UserArticleInsight
            cached = db.query(UserArticleInsight).filter(
                UserArticleInsight.user_id == current_user.id,
                UserArticleInsight.article_id == article.id
            ).first()

            if cached:
                insight_text = cached.insight_text
            else:
                from app.services.ai_service import generate_insight
                insight_text = generate_insight(
                    article.title,
                    article.content or "",
                    user_topics
                )
                if insight_text:
                    new_insight = UserArticleInsight(
                        user_id=current_user.id,
                        article_id=article.id,
                        insight_text=insight_text
                    )
                    db.add(new_insight)
                    db.commit()

        result.append({
            "id": article.id,
            "title": article.title,
            "summary": article.ai_summary,
            "insight": insight_text,
            "source_name": article.source_name,
            "original_url": article.original_url,
            "topic": article.topic,
            "tags": article.tags or [],
            "relevance_score": article.relevance_score,
            "read_time_minutes": article.read_time_minutes,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "is_saved": article.id in saved_ids,
            "user_feedback": feedback_map.get(article.id),
        })

    return {
        "success": True,
        "data": {
            "articles": result,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "has_next": (page * limit) < total
            }
        }
    }


# GET /api/news/search — 키워드 실시간 검색
@router.get("/search")
def search_news(
    q: str = Query(..., description="검색 키워드"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Article).filter(
        Article.title.ilike(f"%{q}%")
    ).order_by(Article.published_at.desc())

    total = query.count()
    articles = query.offset((page - 1) * limit).limit(limit).all()

    result = []
    for article in articles:
        result.append({
            "id": article.id,
            "title": article.title,
            "summary": article.ai_summary,
            "source_name": article.source_name,
            "original_url": article.original_url,
            "topic": article.topic,
            "published_at": article.published_at.isoformat() if article.published_at else None,
        })

    return {
        "success": True,
        "data": {
            "articles": result,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "has_next": (page * limit) < total
            }
        }
    }


# POST /api/news/{article_id}/view — 기사 열람 기록 저장
@router.post("/{article_id}/view", status_code=201)
def record_view(
    article_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 이미 열람했으면 스킵
    exists = db.query(ArticleView).filter(
        ArticleView.user_id == current_user.id,
        ArticleView.article_id == article_id
    ).first()

    if not exists:
        view = ArticleView(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            article_id=article_id
        )
        db.add(view)
        db.commit()

    return {"success": True}


# POST /api/news/{article_id}/feedback — 좋아요/싫어요 피드백
@router.post("/{article_id}/feedback")
def feedback(
    article_id: str,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(UserArticleInteraction).filter(
        UserArticleInteraction.user_id == current_user.id,
        UserArticleInteraction.article_id == article_id
    ).first()

    if existing:
        if body.feedback == "cancel":
            existing.feedback = None
        else:
            existing.feedback = body.feedback
        db.commit()
    else:
        interaction = UserArticleInteraction(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            article_id=article_id,
            feedback=body.feedback
        )
        db.add(interaction)
        db.commit()

    return {"success": True}


# POST /api/news/{article_id}/save — 북마크 저장/해제 토글
@router.post("/{article_id}/save")
def toggle_save(
    article_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.bookmark import Bookmark

    existing = db.query(Bookmark).filter(
        Bookmark.user_id == current_user.id,
        Bookmark.article_id == article_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"success": True, "is_saved": False}
    else:
        bookmark = Bookmark(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            article_id=article_id
        )
        db.add(bookmark)
        db.commit()
        return {"success": True, "is_saved": True}


# GET /api/news/saved — 북마크 목록 조회
@router.get("/saved")
def get_saved(
    tag: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.bookmark import Bookmark

    query = db.query(Bookmark).filter(
        Bookmark.user_id == current_user.id
    ).order_by(Bookmark.created_at.desc())

    total = query.count()
    bookmarks = query.offset((page - 1) * limit).limit(limit).all()

    result = []
    for bm in bookmarks:
        article = db.query(Article).filter(Article.id == bm.article_id).first()
        if article:
            result.append({
                "id": bm.id,
                "article_id": article.id,
                "title": article.title,
                "source_name": article.source_name,
                "topic": article.topic,
                "tags": [t.name for t in bm.tags],
                "created_at": bm.created_at.isoformat(),
            })

    return {
        "success": True,
        "data": {
            "bookmarks": result,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "has_next": (page * limit) < total
            }
        }
    }