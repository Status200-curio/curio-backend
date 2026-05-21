# app/routers/newsletter.py
"""
뉴스레터 발송 라우터

POST /api/newsletter/dispatch
  - Railway Cron Job (매 정시)이 호출하는 엔드포인트
  - 현재 KST 시각과 사용자의 digest_time(HH:MM)을 비교해 발송 대상을 추림
  - 각 사용자의 관심사(topics/topic_weights)에 맞는 기사 최대 5개를 선정해 이메일 발송
  - 발송 내역은 newsletter_history 테이블에 기록
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import pytz
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.article import Article, ArticleView
from app.models.newsletter import NewsletterHistory
from app.models.user import User, UserPreference
from app.services.newsletter_service import send_newsletter

router = APIRouter()

KST = pytz.timezone("Asia/Seoul")

# Railway Cron이 호출할 때 함께 보내는 공유 시크릿 (선택)
DISPATCH_SECRET = os.getenv("DISPATCH_SECRET", "")

TOPIC_ALIAS = {"global": "world", "entertainment": "entertain"}


# ──────────────────────────────────────────────────────────
# 내부 헬퍼: 사용자별 개인화 기사 선정
# ──────────────────────────────────────────────────────────
def _pick_articles_for_user(
    user: User,
    pref: UserPreference,
    db: Session,
    limit: int = 5,
) -> list[dict]:
    """
    사용자의 관심사(topics, topic_weights)를 바탕으로
    최근 48시간 내 기사 중 관련성 높은 기사를 최대 `limit`개 반환.
    """
    topics = pref.topics or []
    topic_weights: dict = pref.topic_weights or {}
    topics = [TOPIC_ALIAS.get(t, t) for t in topics]

    if not topics:
        # 관심사 미설정 → 전체 최신 기사
        articles = (
            db.query(Article)
            .filter(Article.ai_summary.isnot(None))
            .order_by(Article.published_at.desc())
            .limit(limit)
            .all()
        )
        return [_article_to_dict(a) for a in articles]

    # 이미 읽은 기사 ID 수집 (최근 7일)
    week_ago = datetime.now(KST) - timedelta(days=7)
    read_ids = {
        v.article_id
        for v in db.query(ArticleView.article_id)
        .filter(
            ArticleView.user_id == user.id,
            ArticleView.viewed_at >= week_ago,
        )
        .all()
    }

    # 48시간 내 발행 기사 후보
    cutoff = datetime.now(KST) - timedelta(hours=48)
    candidates = (
        db.query(Article)
        .filter(
            Article.topic.in_(topics),
            Article.ai_summary.isnot(None),
            Article.published_at >= cutoff,
        )
        .order_by(Article.published_at.desc())
        .limit(50)
        .all()
    )

    # 48시간 내 결과가 부족하면 7일로 넓힘
    if len(candidates) < limit:
        week_cutoff = datetime.now(KST) - timedelta(days=7)
        candidates = (
            db.query(Article)
            .filter(
                Article.topic.in_(topics),
                Article.ai_summary.isnot(None),
                Article.published_at >= week_cutoff,
            )
            .order_by(Article.published_at.desc())
            .limit(50)
            .all()
        )

    # topic_weight 가중치 적용해 정렬
    def score(article: Article) -> float:
        w = topic_weights.get(article.topic, 1.0)
        already_read = -5.0 if article.id in read_ids else 0.0
        rel = article.relevance_score or 0.0
        return w * (1 + rel) + already_read

    candidates.sort(key=score, reverse=True)
    selected = candidates[:limit]

    return [_article_to_dict(a) for a in selected]


def _article_to_dict(article: Article) -> dict:
    return {
        "id": article.id,
        "title": article.title,
        "summary": article.ai_summary or "",
        "insight": "",
        "topic": article.topic,
        "source_name": article.source_name or "",
        "original_url": article.original_url,
        "image_url": article.thumbnail_url or "",
        "published_at": (
            article.published_at.isoformat() if article.published_at else None
        ),
    }


# ──────────────────────────────────────────────────────────
# POST /api/newsletter/dispatch  (Railway Cron 전용)
# ──────────────────────────────────────────────────────────
@router.post("/dispatch")
def dispatch_newsletter(
    x_dispatch_secret: Optional[str] = Header(None, alias="X-Dispatch-Secret"),
    dry_run: bool = Query(False, description="실제 발송 없이 대상 목록만 반환"),
    db: Session = Depends(get_db),
):
    """
    현재 KST 정시(HH:00)에 발송해야 할 사용자에게 뉴스레터를 발송합니다.

    Railway Cron Job 설정 예시:
      Schedule: 0 * * * *  (매 정시 UTC)
      Command : curl -s -X POST https://curio-backend-production.up.railway.app/api/newsletter/dispatch
    """
    if DISPATCH_SECRET and x_dispatch_secret != DISPATCH_SECRET:
        raise HTTPException(status_code=403, detail="Invalid dispatch secret")

    now_kst = datetime.now(KST)
    current_day_str = now_kst.strftime("%a").lower()

    all_prefs = (
        db.query(UserPreference)
        .filter(UserPreference.digest_time.isnot(None))
        .all()
    )

    targets = []
    for pref in all_prefs:
        current_time_str = now_kst.strftime("%H:%M")
        if pref.digest_time != current_time_str:
            continue

        if pref.digest_frequency == "weekly":
            if pref.digest_day and pref.digest_day.lower() != current_day_str:
                continue

        today_sent = (
            db.query(NewsletterHistory)
            .filter(
                NewsletterHistory.user_id == pref.user_id,
                NewsletterHistory.sent_at >= now_kst.replace(hour=0, minute=0, second=0, microsecond=0),
            )
            .first()
        )
        if today_sent:
            continue

        targets.append(pref)

    sent_list = []
    skipped_list = []

    for pref in targets:
        user = db.query(User).filter(User.id == pref.user_id).first()
        if not user or not user.email:
            skipped_list.append({"user_id": pref.user_id, "reason": "이메일 없음"})
            continue

        articles = _pick_articles_for_user(user, pref, db, limit=5)
        if not articles:
            skipped_list.append({"user_id": pref.user_id, "email": user.email, "reason": "추천 기사 없음"})
            continue

        if not dry_run:
            try:
                send_newsletter(user.email, user.name, articles)
            except Exception as e:
                skipped_list.append({
                    "user_id": pref.user_id,
                    "email": user.email,
                    "reason": f"발송 실패: {e}",
                })
                continue

            history = NewsletterHistory(
                user_id=user.id,
                subject=f"[Curio] {user.name}님의 오늘의 뉴스레터",
                article_ids=[a["id"] for a in articles],
            )
            db.add(history)
            db.commit()

        sent_list.append({"user_id": pref.user_id, "email": user.email, "article_count": len(articles)})

    return {
        "success": True,
        "data": {
            "kst_time": now_kst.strftime("%Y-%m-%d %H:%M"),
            "dry_run": dry_run,
            "sent_count": len(sent_list),
            "skipped_count": len(skipped_list),
            "sent": sent_list,
            "skipped": skipped_list,
        },
    }


# ──────────────────────────────────────────────────────────
# POST /api/newsletter/send-now  (로그인 사용자 즉시 발송 테스트)
# ──────────────────────────────────────────────────────────
@router.post("/send-now")
def send_now(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    로그인한 사용자에게 즉시 뉴스레터를 발송합니다. (테스트용)
    """
    pref = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == current_user.id)
        .first()
    )
    if not pref:
        raise HTTPException(status_code=404, detail="사용자 설정을 찾을 수 없습니다")

    articles = _pick_articles_for_user(current_user, pref, db, limit=5)
    if not articles:
        raise HTTPException(status_code=404, detail="추천할 기사가 없습니다")

    send_newsletter(current_user.email, current_user.name, articles)

    history = NewsletterHistory(
        user_id=current_user.id,
        subject=f"[Curio] {current_user.name}님의 오늘의 뉴스레터",
        article_ids=[a["id"] for a in articles],
    )
    db.add(history)
    db.commit()

    return {
        "success": True,
        "data": {
            "email": current_user.email,
            "article_count": len(articles),
            "articles": [{"id": a["id"], "title": a["title"]} for a in articles],
        },
    }
