from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserPreference
from app.models.article import Article, ArticleView, UserArticleInteraction
from app.schemas.news import FeedbackRequest
from app.services.recommend_service import update_topic_weights
from datetime import datetime, timedelta
import pytz
import uuid

router = APIRouter()

KST = pytz.timezone("Asia/Seoul")


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
    user_keywords = pref.keywords if pref and pref.keywords else []
    user_sub_topics = pref.sub_topics if pref and pref.sub_topics else []

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

    # 24시간 이내 읽은 기사 제외
    since_24h = datetime.now(KST) - timedelta(hours=24)
    viewed_24h = db.query(ArticleView.article_id).filter(
        ArticleView.user_id == current_user.id,
        ArticleView.viewed_at >= since_24h
    ).subquery()
    query = query.filter(Article.id.notin_(viewed_24h))

    # 정렬
    now = datetime.now(KST)
    if sort == "latest":
        query = query.order_by(Article.published_at.desc())
    elif sort == "relevance":
        # 최신 기사 가중치
        freshness_boost = case(
            (Article.published_at >= now - timedelta(hours=24), 0.3),
            (Article.published_at >= now - timedelta(hours=48), 0.1),
            else_=0.0
        )

        # sub_topics 가중치 (세부 카테고리 매칭)
        sub_topic_boost = case(
            *[(Article.tags.contains([st]), 0.5) for st in user_sub_topics] if user_sub_topics else [(True, 0.0)],
            else_=0.0
        )

        if user_keywords:
            keyword_boost = case(
                *[(Article.title.ilike(f"%{kw}%"), 1.0) for kw in user_keywords],
                else_=0.0
            )
            query = query.order_by(
                (Article.relevance_score + freshness_boost + keyword_boost).desc(),
                Article.published_at.desc()
            )
        else:
            query = query.order_by(
                (Article.relevance_score + freshness_boost).desc(),
                Article.published_at.desc()
            )
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
                try:
                    from app.services.ai_service import generate_insight
                    insight_text = generate_insight(
                        article.title,
                        article.content or "",
                        user_topics,
                        user_keywords,
                        user_sub_topics
                    )
                    if insight_text:
                        new_insight = UserArticleInsight(
                            user_id=current_user.id,
                            article_id=article.id,
                            insight_text=insight_text
                        )
                        db.add(new_insight)
                        db.commit()
                except Exception:
                    insight_text = None

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
    # 최근 검색어 자동 저장
    from app.models.search import SearchRecentQuery
    from sqlalchemy.sql import func

    existing = db.query(SearchRecentQuery).filter(
        SearchRecentQuery.user_id == current_user.id,
        SearchRecentQuery.query == q
    ).first()

    if existing:
        existing.searched_at = func.now()
        db.commit()
    else:
        count = db.query(SearchRecentQuery).filter(
            SearchRecentQuery.user_id == current_user.id
        ).count()

        if count >= 10:
            oldest = db.query(SearchRecentQuery).filter(
                SearchRecentQuery.user_id == current_user.id
            ).order_by(SearchRecentQuery.searched_at.asc()).first()
            db.delete(oldest)

        new_query = SearchRecentQuery(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            query=q
        )
        db.add(new_query)
        db.commit()

    # 검색 쿼리
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
    duration_seconds: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(ArticleView).filter(
        ArticleView.user_id == current_user.id,
        ArticleView.article_id == article_id
    ).first()

    if not existing:
        # 처음 읽는 기사 → 새로 저장
        view = ArticleView(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            article_id=article_id,
            duration_seconds=duration_seconds
        )
        db.add(view)
    else:
        # 이미 읽은 기사 → 최장 체류시간만 업데이트
        if duration_seconds > (existing.duration_seconds or 0):
            existing.duration_seconds = duration_seconds

    db.commit()

    # 체류시간 기반 가중치 반영
    if duration_seconds > 0:
        article = db.query(Article).filter(Article.id == article_id).first()
        if article and article.topic:
            _apply_duration_weight(current_user.id, article.topic, duration_seconds, db)

    return {"success": True}


def _apply_duration_weight(user_id: str, topic: str, duration_seconds: int, db):
    """체류시간 기반 topic_weights 업데이트"""
    from app.models.user import UserPreference

    pref = db.query(UserPreference).filter(
        UserPreference.user_id == user_id
    ).first()
    if not pref:
        return

    topic_weights = dict(pref.topic_weights or {})
    current = topic_weights.get(topic, 1.0)

    if duration_seconds < 5:
        # 5초 미만 → 관심없음
        weight = round(max(0.1, current - 0.1), 1)
    elif duration_seconds >= 180:
        # 3분 이상 → 매우 관심있음
        weight = round(min(2.0, current + 0.3), 1)
    elif duration_seconds >= 60:
        # 1분 이상 → 높은 관심
        weight = round(min(2.0, current + 0.2), 1)
    elif duration_seconds >= 30:
        # 30초 이상 → 관심있음
        weight = round(min(2.0, current + 0.1), 1)
    else:
        return  # 5~30초는 가중치 변화 없음

    topic_weights[topic] = weight
    pref.topic_weights = topic_weights
    db.commit()
    print(f"[체류시간] {topic}: {duration_seconds}초 → 가중치 {weight}")


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

    # 좋아요/싫어요 가중치 반영
    if body.feedback != "cancel":
        article = db.query(Article).filter(Article.id == article_id).first()
        if article and article.topic:
            update_topic_weights(current_user.id, article.topic, body.feedback, db)

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
    )

    # tag 필터링
    if tag:
        query = query.join(Bookmark.tags).filter(
            BookmarkTag.name == tag
    )

    query = query.order_by(Bookmark.created_at.desc()) 

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

# GET /api/news/categories — 카테고리 및 세부 카테고리 목록
@router.get("/categories")
def get_categories():
    categories = [
        {
            "topic": "ai",
            "label": "IT/기술",
            "sub_topics": [
                {"key": "llm", "label": "AI/LLM"},
                {"key": "semiconductor", "label": "반도체"},
                {"key": "mobile", "label": "모바일"},
                {"key": "security", "label": "보안"},
                {"key": "startup", "label": "스타트업"},
                {"key": "cloud", "label": "클라우드"},
                {"key": "internet", "label": "인터넷/SNS"},
                {"key": "ev", "label": "전기차"},
                {"key": "game_tech", "label": "게임/메타버스"},
            ]
        },
        {
            "topic": "economy",
            "label": "경제",
            "sub_topics": [
                {"key": "stock", "label": "주식"},
                {"key": "realestate", "label": "부동산"},
                {"key": "crypto", "label": "가상화폐"},
                {"key": "finance", "label": "금융"},
                {"key": "trade", "label": "무역"},
                {"key": "company", "label": "기업"},
                {"key": "exchange", "label": "환율"},
                {"key": "employment", "label": "취업/노동"},
            ]
        },
        {
            "topic": "sports",
            "label": "스포츠",
            "sub_topics": [
                {"key": "football", "label": "축구"},
                {"key": "baseball", "label": "야구"},
                {"key": "basketball", "label": "농구"},
                {"key": "golf", "label": "골프"},
                {"key": "esports", "label": "e스포츠"},
                {"key": "volleyball", "label": "배구"},
                {"key": "badminton", "label": "배드민턴"},
                {"key": "tabletennis", "label": "탁구"},
                {"key": "taekwondo", "label": "태권도"},
                {"key": "judo", "label": "유도"},
                {"key": "boxing", "label": "복싱"},
                {"key": "mma", "label": "종합격투기/MMA"},
                {"key": "tennis", "label": "테니스"},
                {"key": "motorsports", "label": "F1/모터스포츠"},
                {"key": "handball", "label": "핸드볼"},
                {"key": "ssireum", "label": "씨름"},
                {"key": "swimming", "label": "수영"},
                {"key": "fencing", "label": "펜싱"},
                {"key": "archery", "label": "양궁"},
            ]
        },
        {
            "topic": "politics",
            "label": "정치",
            "sub_topics": [
                {"key": "domestic", "label": "국내정치"},
                {"key": "election", "label": "선거"},
                {"key": "northkorea", "label": "북한"},
                {"key": "foreign", "label": "외교"},
                {"key": "policy", "label": "정책"},
                {"key": "judiciary", "label": "사법"},
            ]
        },
        {
            "topic": "health",
            "label": "건강",
            "sub_topics": [
                {"key": "disease", "label": "질병"},
                {"key": "medical", "label": "의료"},
                {"key": "fitness", "label": "운동"},
                {"key": "diet", "label": "다이어트"},
                {"key": "mental", "label": "정신건강"},
                {"key": "beauty", "label": "뷰티"},
                {"key": "nutrition", "label": "영양"},
                {"key": "pharma", "label": "제약/바이오"},
    ]
        },
        {
            "topic": "culture",
            "label": "문화",
            "sub_topics": [
                {"key": "movie", "label": "영화"},
                {"key": "music", "label": "음악"},
                {"key": "art", "label": "미술/전시"},
                {"key": "book", "label": "도서"},
                {"key": "travel", "label": "여행"},
                {"key": "food", "label": "음식/맛집"},
                {"key": "fashion", "label": "패션"},
                {"key": "game", "label": "게임"},
                {"key": "performance", "label": "공연"},
            ]
        },
        {
            "topic": "entertain",
            "label": "연예",
            "sub_topics": [
                {"key": "kpop", "label": "K-POP/아이돌"},
                {"key": "drama", "label": "드라마"},
                {"key": "movie", "label": "영화"},
                {"key": "variety", "label": "예능"},
                {"key": "music", "label": "가요/음악"},
                {"key": "actor", "label": "배우"},
                {"key": "overseas", "label": "해외연예"},
            ]
        },
        {
            "topic": "science",
            "label": "과학",
            "sub_topics": [
                {"key": "space", "label": "우주"},
                {"key": "environment", "label": "환경"},
                {"key": "biology", "label": "생명과학"},
                {"key": "physics", "label": "물리/화학"},
                {"key": "medicine", "label": "의학/바이오"},
                {"key": "math", "label": "수학/통계"},
                {"key": "robot", "label": "로봇/기계"},
                {"key": "energy", "label": "에너지/신소재"},
            ]
        },
        {
            "topic": "society",
            "label": "사회",
            "sub_topics": [
                {"key": "education", "label": "교육"},
                {"key": "crime", "label": "사건/사고"},
                {"key": "welfare", "label": "복지"},
                {"key": "labor", "label": "노동"},
                {"key": "disaster", "label": "재난/재해"},
                {"key": "human_rights", "label": "인권"},
                {"key": "media", "label": "미디어"},
                {"key": "religion", "label": "종교"},
                {"key": "local", "label": "지역"},
            ]
        },
        {
            "topic": "world",
            "label": "국제",
            "sub_topics": [
                {"key": "us", "label": "미국"},
                {"key": "china", "label": "중국"},
                {"key": "japan", "label": "일본"},
                {"key": "europe", "label": "유럽"},
                {"key": "middleeast", "label": "중동"},
                {"key": "asia", "label": "아시아"},
                {"key": "russia", "label": "러시아"},
                {"key": "world_economy", "label": "국제경제"},
                {"key": "world_affairs", "label": "국제정세"},
            ]
        },
    ]

    return {
        "success": True,
        "data": categories
    }