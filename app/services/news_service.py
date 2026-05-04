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

# 카테고리별 RSS 피드 URL (여러 개)
RSS_FEEDS = {
    "ai": [
        "https://techcrunch.com/feed/",
        "https://rss.etnews.com/Section901.xml",
        "https://zdnet.co.kr/rss/rss.php",
    ],
    "economy": [
        "https://www.yna.co.kr/rss/economy.xml",
        "https://news.kbs.co.kr/rss/rss_economy.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=economy",
        "https://www.hankyung.com/feed/economy",
        "https://rss.mk.co.kr/rss/30200030.xml",
    ],
    "sports": [
        "https://www.yna.co.kr/rss/sports.xml",
        "https://news.kbs.co.kr/rss/rss_sports.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=sports",
        "https://www.sportschosun.com/rss/sports.xml",
    ],
    "culture": [
        "https://www.yna.co.kr/rss/culture.xml",
        "https://news.kbs.co.kr/rss/rss_culture.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=culture",
    ],
    "politics": [
        "https://www.yna.co.kr/rss/politics.xml",
        "https://news.kbs.co.kr/rss/rss_politics.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=politics",
    ],
    "science": [
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://www.yna.co.kr/rss/science.xml",
    ],
    "health": [
        "https://www.yna.co.kr/rss/health.xml",
        "https://health.chosun.com/site/data/rss/rss.xml",
    ],
    "world": [
    "https://www.yna.co.kr/rss/international.xml",
    "https://news.kbs.co.kr/rss/rss_world.xml",
    "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=international",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.reuters.com/reuters/worldNews",
],
    "society": [
        "https://www.yna.co.kr/rss/society.xml",
        "https://news.kbs.co.kr/rss/rss_society.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=society",
    ],
    "entertain": [
        "https://www.yna.co.kr/rss/entertainment.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=entertainment",
        "https://www.sportschosun.com/rss/entertain.xml",
    ],
}

# 카테고리별 NewsAPI 검색 키워드
NEWS_API_KEYWORDS = {
    "ai":        "AI OR 인공지능 OR ChatGPT OR 반도체 OR 스타트업 OR 클라우드 OR 빅데이터 OR 사이버보안 OR 메타버스 OR 전기차",
    "economy":   "경제 OR 주식 OR 금리 OR 부동산 OR 가상화폐 OR 환율 OR 코스피 OR 코스닥 OR 무역 OR 기업 OR 취업 OR 고용",
    "sports":    "스포츠 OR 축구 OR 야구 OR 농구 OR 골프 OR 배드민턴 OR 테니스 OR 배구 OR 수영 OR 태권도 OR e스포츠 OR UFC OR F1",
    "culture":   "문화 OR 영화 OR 음악 OR 공연 OR 전시 OR 도서 OR 여행 OR 맛집 OR 패션 OR 게임 OR 미술",
    "politics":  "정치 OR 국회 OR 정부 OR 대통령 OR 선거 OR 외교 OR 북한 OR 정책 OR 여당 OR 야당 OR 검찰 OR 사법",
    "science":   "과학 OR 우주 OR 연구 OR 생명과학 OR 물리 OR 화학 OR 로봇 OR 에너지 OR 기후 OR NASA OR 신소재",
    "health":    "건강 OR 의료 OR 병원 OR 질병 OR 다이어트 OR 운동 OR 정신건강 OR 뷰티 OR 영양 OR 제약 OR 바이오",
    "world":     "국제 OR 해외 OR 미국 OR 중국 OR 일본 OR 유럽 OR 중동 OR 러시아 OR 아시아 OR 외교 OR 전쟁",
    "society":   "사회 OR 사건 OR 사고 OR 교육 OR 복지 OR 노동 OR 인권 OR 재난 OR 환경 OR 미디어 OR 종교",
    "entertain": "연예 OR 드라마 OR 아이돌 OR K-POP OR 영화 OR 예능 OR 배우 OR 가수 OR 넷플릭스 OR 할리우드",
}

# 세부 카테고리 자동 태깅 규칙
SUB_TOPIC_TAGS = {
    "football":    ["축구", "손흥민", "월드컵", "K리그", "프리미어리그", "FA컵", "UEFA", "FIFA"],
    "baseball":    ["야구", "KBO", "MLB", "류현진", "오타니", "홈런"],
    "basketball":  ["농구", "NBA", "KBL", "르브론", "커리"],
    "golf":        ["골프", "PGA", "LPGA", "마스터스", "US오픈"],
    "esports":     ["e스포츠", "롤", "리그오브레전드", "오버워치", "LCK"],
    "volleyball":  ["배구", "V리그"],
    "stock":       ["주식", "코스피", "코스닥", "증시", "상장", "IPO"],
    "realestate":  ["부동산", "아파트", "청약", "전세", "매매"],
    "crypto":      ["비트코인", "코인", "가상화폐", "이더리움", "NFT"],
    "finance":     ["금리", "금융", "은행", "대출", "이자"],
    "trade":       ["무역", "수출", "수입", "관세", "FTA"],
    "llm":         ["ChatGPT", "LLM", "생성AI", "GPT", "클로드", "제미나이", "AI모델"],
    "semiconductor": ["반도체", "엔비디아", "삼성", "AI칩", "HBM", "파운드리"],
    "mobile":      ["스마트폰", "아이폰", "갤럭시", "앱", "모바일"],
    "security":    ["보안", "해킹", "사이버", "랜섬웨어"],
    "startup":     ["스타트업", "창업", "벤처", "유니콘"],
    "domestic":    ["국회", "대통령", "정부", "여당", "야당"],
    "foreign":     ["외교", "정상회담", "대사관", "외무"],
    "policy":      ["정책", "법안", "규제", "입법"],
    "disease":     ["질병", "암", "당뇨", "고혈압", "코로나", "독감"],
    "fitness":     ["운동", "헬스", "트레이닝", "근육"],
    "diet":        ["다이어트", "체중", "식단", "칼로리"],
    "mental":      ["정신건강", "우울", "스트레스", "불안"],
    "movie":       ["영화", "박스오피스", "개봉", "감독"],
    "music":       ["음악", "앨범", "콘서트", "공연"],
    "art":         ["미술", "전시", "갤러리", "작품"],
    "book":        ["책", "도서", "출판", "베스트셀러"],
    "kpop":        ["K-POP", "아이돌", "BTS", "블랙핑크", "뉴진스"],
    "drama":       ["드라마", "넷플릭스", "OTT", "시즌"],
    "celebrity":   ["연예인", "배우", "가수", "MC"],
    "space":       ["우주", "NASA", "로켓", "위성", "블랙홀"],
    "environment": ["환경", "기후", "탄소", "온실가스"],
    "biology":     ["생물", "유전자", "DNA", "줄기세포"],
    "education":   ["교육", "학교", "대학", "수능"],
    "crime":       ["사건", "사고", "범죄", "경찰", "검찰"],
    "welfare":     ["복지", "연금", "기초생활", "노인"],
    "us":          ["미국", "바이든", "트럼프", "워싱턴", "백악관"],
    "china":       ["중국", "시진핑", "베이징", "홍콩"],
    "japan":       ["일본", "기시다", "도쿄", "엔화"],
    "europe":      ["유럽", "EU", "독일", "프랑스", "영국"],
}

def _get_sub_tags(title: str, content: str) -> list:
    """제목 + 내용 기반으로 세부 태그 자동 추출"""
    text = (title + " " + (content or ""))[:500]
    matched = []
    for tag, keywords in SUB_TOPIC_TAGS.items():
        for kw in keywords:
            if kw in text:
                matched.append(tag)
                break
    return matched

def fetch_by_rss(topic: str) -> list:
    """RSS 피드로 기사 수집 (카테고리당 여러 RSS)"""
    feed_urls = RSS_FEEDS.get(topic, [])
    if not feed_urls:
        return []

    articles = []
    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                articles.append({
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", ""),
                    "original_url": entry.get("link", ""),
                    "source_name": feed.feed.get("title", ""),
                    "topic": topic,
                    "published_at": _parse_date(entry.get("published", "")),
                })
        except Exception as e:
            print(f"RSS 수집 실패 ({feed_url}): {e}")
            continue

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
        if not item.get("original_url") or not item.get("title"):
            continue

        exists = db.query(Article).filter(
            Article.original_url == item["original_url"]
        ).first()

        if exists:
            continue

        # 세부 태그 자동 추출
        sub_tags = _get_sub_tags(item["title"], item.get("content", ""))
        tags = [item.get("topic", "")] + sub_tags

        article = Article(
            id=str(uuid.uuid4()),
            title=item["title"],
            content=item.get("content", ""),
            source_name=item.get("source_name", ""),
            original_url=item["original_url"],
            topic=item.get("topic", ""),
            tags=tags,
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
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None