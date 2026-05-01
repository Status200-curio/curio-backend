from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import pytz

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserPreference, UserActivityLog
from app.models.article import Article, ArticleView
from app.schemas.user import PreferencesRequest

router = APIRouter()

KST = pytz.timezone("Asia/Seoul")


# GET /api/user/me — 프로필 및 설정 조회
@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pref = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id
    ).first()

    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "is_google": current_user.is_google,
            "avatar_url": current_user.avatar_url,
            "preferences": {
                "topics": pref.topics if pref else [],
                "keywords": pref.keywords if pref else [],
                "sub_topics": pref.sub_topics if pref else [],
                "digest_frequency": pref.digest_frequency if pref else "daily",
                "digest_time": pref.digest_time if pref else "08:00",
                "digest_day": pref.digest_day if pref else None,
                "ai_summary_depth": pref.ai_summary_depth if pref else "balanced",
                "dark_mode": pref.dark_mode if pref else False,
            } if pref else None
        }
    }


# PUT /api/user/preferences — 관심사·발송 설정 변경
@router.put("/preferences")
def update_preferences(
    body: PreferencesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pref = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id
    ).first()

    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)

    # 변경된 값만 업데이트
    if body.topics is not None:
        if len(body.topics) == 0:
            raise HTTPException(
                status_code=422,
                detail={"code": "UNPROCESSABLE", "detail": "최소 1개 이상의 카테고리를 선택해야 합니다."}
            )
        pref.topics = body.topics

    if body.keywords is not None:
        pref.keywords = body.keywords

    if body.sub_topics is not None:  
        pref.sub_topics = body.sub_topics

    if body.digest_frequency is not None:
        pref.digest_frequency = body.digest_frequency

    if body.digest_time is not None:
        pref.digest_time = body.digest_time

    if body.digest_day is not None:
        pref.digest_day = body.digest_day

    if body.ai_summary_depth is not None:
        pref.ai_summary_depth = body.ai_summary_depth

    if body.dark_mode is not None:
        pref.dark_mode = body.dark_mode

    # 관심사 변경 시 인사이트 캐시 초기화
    if body.topics is not None or body.sub_topics is not None or body.keywords is not None:
        from app.models.article import UserArticleInsight
        db.query(UserArticleInsight).filter(
            UserArticleInsight.user_id == current_user.id
        ).delete()    

    db.commit()

    return {
        "success": True,
        "data": {
            "topics": pref.topics,
            "keywords": pref.keywords,
            "sub_topics": pref.sub_topics,
            "digest_frequency": pref.digest_frequency,
            "digest_time": pref.digest_time,
            "digest_day": pref.digest_day,
            "ai_summary_depth": pref.ai_summary_depth,
            "dark_mode": pref.dark_mode,
        }
    }


# GET /api/user/history — 읽은 기사 기록 조회
@router.get("/history")
def get_history(
    topic: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ArticleView).filter(
        ArticleView.user_id == current_user.id
    ).order_by(ArticleView.viewed_at.desc())

    total = query.count()
    views = query.offset((page - 1) * limit).limit(limit).all()

    result = []
    for view in views:
        article = db.query(Article).filter(
            Article.id == view.article_id
        ).first()
        if article:
            if topic and article.topic != topic:
                continue
            result.append({
                "id": article.id,
                "title": article.title,
                "source_name": article.source_name,
                "topic": article.topic,
                "original_url": article.original_url,
                "viewed_at": view.viewed_at.isoformat(),
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


# GET /api/user/stats — 개인 페이지 대시보드 통계
@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy import func

    now_kst = datetime.now(KST)
    today = now_kst.date()

    # 이번 주 월요일 계산
    monday = today - timedelta(days=today.weekday())

    # 총 읽은 기사 수
    total_read = db.query(ArticleView).filter(
        ArticleView.user_id == current_user.id
    ).count()

    # 오늘 읽은 기사 수
    today_read = db.query(ArticleView).filter(
        ArticleView.user_id == current_user.id,
        func.date(ArticleView.viewed_at) == today
    ).count()

    # 이번 주 읽은 기사 수
    weekly_read = db.query(ArticleView).filter(
        ArticleView.user_id == current_user.id,
        ArticleView.viewed_at >= datetime(monday.year, monday.month, monday.day, tzinfo=KST)
    ).count()

    # 관심 카테고리 Top 3 (횟수)
    top_topics_query = db.query(
        Article.topic,
        func.count(ArticleView.id).label("count")
    ).join(
        ArticleView, Article.id == ArticleView.article_id
    ).filter(
        ArticleView.user_id == current_user.id,
        Article.topic != None
    ).group_by(
        Article.topic
    ).order_by(
        func.count(ArticleView.id).desc()
    ).limit(3).all()

    top_topics = [
        {
            "topic": t.topic,
            "count": t.count,
        }
        for t in top_topics_query
    ]

    # 출석 통계
    logs = db.query(UserActivityLog).filter(
        UserActivityLog.user_id == current_user.id
    ).order_by(UserActivityLog.activity_date).all()

    total_attendance = len(logs)
    current_streak = 0
    max_streak = 0

    if logs:
        # 현재 연속 출석
        streak = 0
        for i, log in enumerate(reversed(logs)):
            expected = today - timedelta(days=i)
            if log.activity_date == expected:
                streak += 1
            else:
                break
        current_streak = streak

        # 최장 연속 출석
        max_s = 1
        cur_s = 1
        for i in range(1, len(logs)):
            diff = (logs[i].activity_date - logs[i-1].activity_date).days
            if diff == 1:
                cur_s += 1
                max_s = max(max_s, cur_s)
            else:
                cur_s = 1
        max_streak = max_s

    return {
        "success": True,
        "data": {
            "reading": {
                "total_read": total_read,
                "today_read": today_read,
                "weekly_read": weekly_read,
                "top_topics": top_topics,
            },
            "attendance": {
                "total_attendance": total_attendance,
                "current_streak": current_streak,
                "max_streak": max_streak,
            }
        }
    }