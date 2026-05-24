from tasks.celery_app import app
from app.database import SessionLocal
from app.models.user import User, UserPreference
from app.models.article import Article, UserArticleInsight
from app.models.newsletter import NewsletterHistory
from app.services.newsletter_service import send_newsletter
from app.services.ai_service import generate_insight
from datetime import datetime, timedelta
import pytz
import uuid

KST = pytz.timezone("Asia/Seoul")


@app.task
def dispatch_newsletters():
    """매분 실행 — 현재 시각에 발송 설정된 유저에게 뉴스레터 발송"""
    db = SessionLocal()
    try:
        now_kst = datetime.now(KST)
        current_time = now_kst.strftime("%H:%M")
        current_day = now_kst.strftime("%a").lower()

        # ① 5분 후 발송 예정 유저 인사이트 미리 생성
        future_time = (now_kst + timedelta(minutes=5)).strftime("%H:%M")
        future_prefs = db.query(UserPreference).filter(
            UserPreference.digest_time == future_time
        ).all()

        for pref in future_prefs:
            if pref.digest_frequency == "weekly" and pref.digest_day != current_day:
                continue
            user = db.query(User).filter(User.id == pref.user_id).first()
            if not user:
                continue

            articles = db.query(Article).filter(
                Article.topic.in_(pref.topics or [])
            ).order_by(
                Article.relevance_score.desc(),
                Article.published_at.desc()
            ).limit(5).all()

            for article in articles:
                cached = db.query(UserArticleInsight).filter(
                    UserArticleInsight.user_id == user.id,
                    UserArticleInsight.article_id == article.id
                ).first()

                if not cached:
                    insight = generate_insight(
                        article.title,
                        article.content or "",
                        pref.topics or [],
                        pref.keywords or [],
                        pref.sub_topics or [],
                        article.topic,
                        article.tags or [],
                        pref.custom_insight_prompt or ""
                    )
                    if insight:
                        new_insight = UserArticleInsight(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            article_id=article.id,
                            insight_text=insight
                        )
                        db.add(new_insight)
                        db.commit()
                        print(f"[뉴스레터 사전생성] {user.email} 인사이트 캐시 완료")

        # ② 현재 발송 시간인 유저 즉시 발송
        prefs = db.query(UserPreference).filter(
            UserPreference.digest_time == current_time
        ).all()

        for pref in prefs:
            if pref.digest_frequency == "weekly" and pref.digest_day != current_day:
                continue
            user = db.query(User).filter(User.id == pref.user_id).first()
            if not user:
                continue

            articles = db.query(Article).filter(
                Article.topic.in_(pref.topics or [])
            ).order_by(
                Article.relevance_score.desc(),
                Article.published_at.desc()
            ).limit(5).all()

            if not articles:
                continue

            article_dicts = []
            for article in articles:
                cached = db.query(UserArticleInsight).filter(
                    UserArticleInsight.user_id == user.id,
                    UserArticleInsight.article_id == article.id
                ).first()

                if cached:
                    insight = cached.insight_text
                else:
                    insight = generate_insight(
                        article.title,
                        article.content or "",
                        pref.topics or [],
                        pref.keywords or [],
                        pref.sub_topics or [],
                        article.topic,
                        article.tags or [],
                        pref.custom_insight_prompt or ""
                    )
                    if insight:
                        new_insight = UserArticleInsight(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            article_id=article.id,
                            insight_text=insight
                        )
                        db.add(new_insight)
                        db.commit()

                article_dicts.append({
                    "id": article.id,
                    "title": article.title,
                    "insight": insight,
                    "thumbnail_url": article.thumbnail_url,
                    "topic": article.topic,
                })

            send_newsletter(user.email, user.name, article_dicts)

            history = NewsletterHistory(
                id=str(uuid.uuid4()),
                user_id=user.id,
                subject=f"[Curio] {user.name}님의 오늘의 뉴스레터",
                article_ids=[a["id"] for a in article_dicts]
            )
            db.add(history)
            db.commit()
            print(f"[뉴스레터] {user.email} 발송 완료")

    finally:
        db.close()