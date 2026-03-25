from tasks.celery_app import app
from app.database import SessionLocal
from app.services.news_service import fetch_by_rss, fetch_by_newsapi, save_articles_to_db
from app.services.ai_service import generate_summary
from app.models.article import Article
import time

TOPICS = ["ai", "economy", "sports", "culture", "politics", "science", "health", "world", "society", "entertain"]


@app.task
def collect_all_topics():
    """매시간 전체 카테고리 뉴스 수집 + AI 요약 생성"""
    db = SessionLocal()
    try:
        for topic in TOPICS:
            # RSS 수집
            articles = fetch_by_rss(topic)
            save_articles_to_db(articles, db)
            print(f"[RSS] {topic}: 저장 완료")

            # NewsAPI 수집 (하루 100건 제한 — 필요시 주석 해제)
            # articles_api = fetch_by_newsapi(topic)
            # save_articles_to_db(articles_api, db)
            # print(f"[NewsAPI] {topic}: 저장 완료")

        # AI 요약 생성 (summary가 null인 기사만)
        unsummarized = db.query(Article).filter(
            Article.ai_summary == None
        ).limit(20).all()

        for article in unsummarized:
            summary = generate_summary(article.title, article.content or "")
            if summary:
                article.ai_summary = summary
                print(f"[AI] 요약 생성: {article.title[:30]}")
                time.sleep(13)  # 분당 5회 제한 → 12초 간격으로 호출

        db.commit()
    finally:
        db.close()


@app.task
def collect_single_topic(topic: str):
    """단일 카테고리 수집 (수동 트리거용)"""
    db = SessionLocal()
    try:
        # RSS 수집
        articles = fetch_by_rss(topic)
        save_articles_to_db(articles, db)
        print(f"[RSS] {topic}: 저장 완료")

        # NewsAPI 수집 (하루 100건 제한 — 필요시 주석 해제)
        # articles_api = fetch_by_newsapi(topic)
        # save_articles_to_db(articles_api, db)
        # print(f"[NewsAPI] {topic}: 저장 완료")
    finally:
        db.close()