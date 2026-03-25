import httpx
import feedparser
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from datetime import datetime
import os
import uuid

from app.models.article import Article

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# 카테고리별 RSS 피드 URL (무료, 호출 제한 없음)
RSS_FEEDS = {
    "ai": "https://techcrunch.com/feed/",
    "economy":   "https://www.yna.co.kr/rss/economy.xml",
    "sports":    "https://www.yna.co.kr/rss/sports.xml",
    "culture":   "https://www.yna.co.kr/rss/culture.xml",
    "politics":  "https://www.yna.co.kr/rss/politics.xml",
    "science":   "https://www.sciencedaily.com/rss/top/science.xml",
    "health":    "https://www.yna.co.kr/rss/health.xml",
    "world":     "https://www.yna.co.kr/rss/international.xml",
    "society":   "https://www.yna.co.kr/rss/society.xml",
    "entertain": "https://www.yna.co.kr/rss/entertainment.xml",
}

# 카테고리별 NewsAPI 검색 키워드
NEWS_API_KEYWORDS = {
    "ai":        "AI OR 인공지능 OR ChatGPT",
    "economy":   "경제 OR 주식 OR 금리",
    "sports":    "스포츠 OR 축구 OR 야구",
    "culture":   "문화 OR 예술 OR 영화",
    "politics":  "정치 OR 국회 OR 정부",
    "science":   "과학 OR 우주 OR 연구",
    "health":    "건강 OR 의료 OR 병원",
    "world":     "국제 OR 해외 OR 미국",
    "society":   "사회 OR 사건 OR 사고",
    "entertain": "연예 OR 드라마 OR 아이돌",
}


def fetch_by_rss(topic: str) -> list:
    """RSS 피드로 기사 수집"""
    feed_url = RSS_FEEDS.get(topic)
    if not feed_url:
        return []

    feed = feedparser.parse(feed_url)
    articles = []

    for entry in feed.entries:
        articles.append({
            "title": entry.get("title", ""),
            "content": entry.get("summary", ""),
            "original_url": entry.get("link", ""),
            "source_name": feed.feed.get("title", ""),
            "topic": topic,
            "published_at": _parse_date(entry.get("published", "")),
        })

    return articles


async def fetch_by_newsapi(topic: str) -> list:
    """NewsAPI로 기사 수집 (하루 100건 제한 주의)"""
    keyword = NEWS_API_KEYWORDS.get(topic, topic)
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": keyword,
        "language": "ko",
        "sortBy": "publishedAt",
        "apiKey": NEWS_API_KEY,
        "pageSize": 10,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return []

        data = response.json()
        articles = []

        for item in data.get("articles", []):
            articles.append({
                "title": item.get("title", ""),
                "content": item.get("content") or item.get("description", ""),
                "original_url": item.get("url", ""),
                "source_name": item.get("source", {}).get("name", ""),
                "topic": topic,
                "published_at": _parse_date(item.get("publishedAt", "")),
            })

        return articles


def save_articles_to_db(articles: list, db: Session) -> int:
    """수집된 기사를 DB에 저장 — 중복 방지 (original_url UNIQUE)"""
    saved_count = 0

    for item in articles:
        # URL 없거나 제목 없으면 스킵
        if not item.get("original_url") or not item.get("title"):
            continue

        # 이미 존재하는 기사면 스킵
        exists = db.query(Article).filter(
            Article.original_url == item["original_url"]
        ).first()

        if exists:
            continue

        article = Article(
            id=str(uuid.uuid4()),
            title=item["title"],
            content=item.get("content", ""),
            source_name=item.get("source_name", ""),
            original_url=item["original_url"],
            topic=item.get("topic", ""),
            tags=[item.get("topic", "")],
            relevance_score=0.5,
            published_at=item.get("published_at"),
        )
        db.add(article)
        saved_count += 1

    db.commit()
    return saved_count


def _parse_date(date_str: str):
    """날짜 문자열을 datetime으로 변환"""
    if not date_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",   # RSS 형식
        "%Y-%m-%dT%H:%M:%SZ",          # NewsAPI 형식
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None