from tasks.celery_app import app
from app.database import SessionLocal
from app.models import User, UserPreference, Article
from app.services.newsletter_service import send_newsletter, build_newsletter_html
from app.services.ai_service import generate_insight
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")


@app.task
def dispatch_newsletters():
    """매분 실행 — 현재 시각에 발송 설정된 유저에게 뉴스레터 발송"""
    db = SessionLocal()
    try:
        now_kst = datetime.now(KST)
        current_time = now_kst.strftime("%H:%M")
        current_day = now_kst.strftime("%a").lower()  # mon, tue, ...

        prefs = db.query(UserPreference).filter(
            UserPreference.digest_time == current_time
        ).all()

        for pref in prefs:
            # 발송 주기 체크
            if pref.digest_frequency == "weekly" and pref.digest_day != current_day:
                continue

            user = db.query(User).filter(User.id == pref.user_id).first()
            if not user:
                continue

            # 유저 관심사 기반 TOP 5 기사 선별
            articles = db.query(Article).filter(
                Article.topic.in_(pref.topics or [])
            ).order_by(
                Article.relevance_score.desc(),
                Article.published_at.desc()
            ).limit(5).all()

            if not articles:
                continue

            # 각 기사에 개인화 인사이트 추가
            article_dicts = []
            for article in articles:
                insight = generate_insight(
                    article.title,
                    article.content or "",
                    pref.topics or []
                )
                article_dicts.append({
                    "id": article.id,
                    "title": article.title,
                    "summary": article.ai_summary,
                    "insight": insight,
                })

            # 이메일 발송
            send_newsletter(user.email, user.name, article_dicts)

    finally:
        db.close()
