from tasks.celery_app import app
from app.database import SessionLocal
from app.services.news_service import fetch_by_rss, fetch_by_newsapi, save_articles_to_db
from app.services.ai_service import generate_summary, translate_title
from app.models.article import Article
import time
import asyncio

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

            # NewsAPI 수집 (하루 100건 제한)
            api_articles = asyncio.run(fetch_by_newsapi(topic))
            api_saved = save_articles_to_db(api_articles, db)
            print(f"[NewsAPI] {topic}: {api_saved}개 저장")

        # AI 요약 생성 + 영어 제목 번역 (summary가 null인 기사만)
        unsummarized = db.query(Article).filter(
            Article.ai_summary == None
        ).limit(20).all()

        for article in unsummarized:
            # 영어 제목이면 한국어로 번역
            translated = translate_title(article.title)
            if translated != article.title:
                article.title = translated
                print(f"[번역] {translated[:30]}")
            
            time.sleep(7)  # 번역/요약 상관없이 항상 대기

            # AI 요약 생성
            summary = generate_summary(article.title, article.content or "")
            if summary:
                article.ai_summary = summary
                print(f"[AI] 요약 생성: {article.title[:30]}")
            else:
                print(f"[AI] 요약 실패 (스킵): {article.title[:30]}")
            
            time.sleep(7)  # 요약 후에도 항상 대기
            
        db.commit()
    finally:
        db.close()


@app.task
def collect_single_topic(topic: str):
    """단일 카테고리 수집 (수동 트리거용)"""
    db = SessionLocal()
    try:
        articles = fetch_by_rss(topic)
        save_articles_to_db(articles, db)
        print(f"[RSS] {topic}: 저장 완료")
    finally:
        db.close()