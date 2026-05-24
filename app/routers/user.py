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
                "custom_insight_prompt": pref.custom_insight_prompt if pref else None,
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

    if body.custom_insight_prompt is not None:
        pref.custom_insight_prompt = body.custom_insight_prompt
        from app.models.article import UserArticleInsight
        db.query(UserArticleInsight).filter(
            UserArticleInsight.user_id == current_user.id
        ).delete()

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
            "custom_insight_prompt": pref.custom_insight_prompt,
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

# POST /api/user/attendance — 오늘 출석 기록 (중복 방지, 앱 진입 시 호출)
@router.post("/attendance", status_code=200)
def record_attendance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import uuid as _uuid
    today = datetime.now(KST).date()
    existing = db.query(UserActivityLog).filter(
        UserActivityLog.user_id == current_user.id,
        UserActivityLog.activity_date == today
    ).first()

    if not existing:
        log = UserActivityLog(
            id=str(_uuid.uuid4()),
            user_id=current_user.id,
            activity_date=today
        )
        db.add(log)
        db.commit()
        return {"success": True, "data": {"recorded": True, "message": "출석 완료"}}

    return {"success": True, "data": {"recorded": False, "message": "이미 오늘 출석했습니다"}}

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

# GET /api/user/recommendations — 읽기 기록 기반 연관 주제 추천
@router.get("/recommendations")
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy import func
    from app.models.article import Article

    # 토픽 친화도 맵 (읽은 주제 → 추천 주제 + 이유)
    AFFINITY = {
        "ai":       [("economy", "AI 기업과 테크 경제 흐름이 연결돼 있어요"),
                     ("science", "AI의 과학적 원리가 흥미로울 거예요")],
        "economy":  [("ai", "경제를 바꾸는 AI·테크 트렌드예요"),
                     ("world", "글로벌 경제 동향을 함께 보시면 좋아요")],
        "sports":   [("health", "스포츠와 건강은 자연스럽게 이어져요"),
                     ("culture", "스포츠 문화와 엔터테인먼트도 즐기실 수 있어요")],
        "politics": [("world", "국내 정치와 국제 정세는 맞닿아 있어요"),
                     ("economy", "정책이 경제에 미치는 영향을 볼 수 있어요")],
        "health":   [("science", "건강의 과학적 근거가 흥미로울 거예요"),
                     ("sports", "건강한 삶과 스포츠는 함께예요")],
        "culture":  [("entertain", "문화와 연예 콘텐츠는 겹치는 부분이 많아요"),
                     ("society", "문화가 사회에 미치는 영향도 있어요")],
        "science":  [("ai", "과학과 AI 기술의 연결고리예요"),
                     ("health", "과학이 건강에 미치는 영향이 있어요")],
        "world":    [("politics", "국제 정세와 정치는 밀접하게 연결돼요"),
                     ("economy", "세계 경제 흐름도 함께 보세요")],
        "society":  [("politics", "사회 문제와 정치 정책이 연결돼요"),
                     ("health", "사회적 건강 이슈도 함께예요")],
        "entertain":[("culture", "연예와 문화는 함께 즐길 수 있어요"),
                     ("society", "연예가 사회에 미치는 영향도 있어요")],
    }
    TOPIC_LABELS = {
        "ai": "AI / 기술", "economy": "경제", "sports": "스포츠",
        "culture": "문화", "politics": "정치", "science": "과학",
        "health": "건강", "world": "국제", "society": "사회", "entertain": "연예",
    }
    # 읽기 기록 기반 주제별 체류시간 합계 (오래 읽은 순)
    from app.models.article import ArticleView
    top_read = db.query(
        Article.topic,
        func.count(ArticleView.id).label("cnt"),
        func.sum(ArticleView.duration_seconds).label("total_sec")
    ).join(
        ArticleView, Article.id == ArticleView.article_id
    ).filter(
        ArticleView.user_id == current_user.id,
        ArticleView.duration_seconds > 0
    ).group_by(Article.topic).order_by(
        func.sum(ArticleView.duration_seconds).desc()
    ).limit(3).all()

    def _get_sample_article(rec_topic):
        article = db.query(Article).filter(
            Article.topic == rec_topic,
            Article.ai_summary != None
        ).order_by(Article.published_at.desc()).first()
        if not article:
            article = db.query(Article).filter(
                Article.topic == rec_topic
            ).order_by(Article.published_at.desc()).first()
        return article

    recommendations = []
    seen_topics = set()

    # 1차: 읽기 기록 기반 추천 (관심사 여부 무관하게 추천)
    for row in top_read:
        source_topic = row.topic
        total_sec = row.total_sec or 0
        for rec_topic, reason in AFFINITY.get(source_topic, []):
            if rec_topic in seen_topics:
                continue
            article = _get_sample_article(rec_topic)
            if not article:
                continue

            mins = total_sec // 60
            time_str = f"{mins}분" if mins >= 1 else f"{total_sec}초"
            recommendations.append({
                "recommended_topic": rec_topic,
                "recommended_topic_label": TOPIC_LABELS.get(rec_topic, rec_topic),
                "reason": reason,
                "based_on_topic": source_topic,
                "based_on_topic_label": TOPIC_LABELS.get(source_topic, source_topic),
                "read_time": time_str,
                "sample_article": {
                    "id": article.id,
                    "title": article.title,
                    "summary": article.ai_summary,
                    "source_name": article.source_name,
                    "original_url": article.original_url,
                    "topic": article.topic,
                },
            })
            seen_topics.add(rec_topic)
            if len(recommendations) >= 3:
                break
        if len(recommendations) >= 3:
            break

    # 2차: 읽기 기록이 없거나 3개 미만이면 전체 토픽에서 채우기
    if len(recommendations) < 3:
        ALL_TOPICS = list(TOPIC_LABELS.keys())
        for topic in ALL_TOPICS:
            if topic in seen_topics:
                continue
            article = _get_sample_article(topic)
            if not article:
                continue
            recommendations.append({
                "recommended_topic": topic,
                "recommended_topic_label": TOPIC_LABELS.get(topic, topic),
                "reason": "새로운 주제도 한번 둘러보세요",
                "based_on_topic": topic,
                "based_on_topic_label": TOPIC_LABELS.get(topic, topic),
                "read_time": None,
                "sample_article": {
                    "id": article.id,
                    "title": article.title,
                    "summary": article.ai_summary,
                    "source_name": article.source_name,
                    "original_url": article.original_url,
                    "topic": article.topic,
                },
            })
            seen_topics.add(topic)
            if len(recommendations) >= 3:
                break

    return {"success": True, "data": {"recommendations": recommendations}}


# GET /api/user/stats/top-reads — 이번 주 체류시간 TOP 3 기사
@router.get("/stats/top-reads")
def get_top_reads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now_kst = datetime.now(KST)
    today = now_kst.date()
    monday = today - timedelta(days=today.weekday())
    week_start = datetime(monday.year, monday.month, monday.day, tzinfo=KST)

    views = db.query(ArticleView).filter(
        ArticleView.user_id == current_user.id,
        ArticleView.viewed_at >= week_start,
        ArticleView.duration_seconds > 0
    ).all()

    # article_id별 최장 체류 시간 집계 (같은 기사를 여러 번 읽었을 때 최대값)
    aggregated = {}
    for v in views:
        if v.article_id not in aggregated or v.duration_seconds > aggregated[v.article_id]:
            aggregated[v.article_id] = v.duration_seconds

    # 내림차순 정렬 후 상위 3개
    top3 = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)[:3]

    result = []
    for article_id, duration in top3:
        article = db.query(Article).filter(Article.id == article_id).first()
        if article:
            result.append({
                "id": article.id,
                "title": article.title,
                "source_name": article.source_name,
                "topic": article.topic,
                "original_url": article.original_url,
                "thumbnail_url": article.thumbnail_url,
                "ai_summary": article.ai_summary,
                "duration_seconds": duration,
            })

    return {
        "success": True,
        "data": {"top_reads": result}
    }