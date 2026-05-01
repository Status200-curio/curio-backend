from tasks.celery_app import app
from app.database import SessionLocal
from app.models.user import User, UserPreference
from app.models.article import Article, UserArticleInsight
from app.models.newsletter import NewsletterHistory
from app.services.newsletter_service import send_newsletter
from app.services.ai_service import generate_insight
from datetime import datetime
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

            # 각 기사에 개인화 인사이트 추가 (캐시 우선 활용)
            article_dicts = []
            for article in articles:
                # 캐시된 인사이트 먼저 확인
                cached = db.query(UserArticleInsight).filter(
                    UserArticleInsight.user_id == user.id,
                    UserArticleInsight.article_id == article.id
                ).first()

                if cached:
                    # 캐시 있으면 Gemini 호출 없이 바로 사용
                    insight = cached.insight_text
                else:
                    # 캐시 없으면 새로 생성
                    insight = generate_insight(
                        article.title,
                        article.content or "",
                        pref.topics or [],
                        pref.keywords or [],
                        pref.sub_topics or []
                    )
                    # 생성된 인사이트 캐시 저장
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
                    "summary": article.ai_summary,
                    "insight": insight,
                })

            # 이메일 발송
            send_newsletter(user.email, user.name, article_dicts)

            # 발송 기록 저장
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