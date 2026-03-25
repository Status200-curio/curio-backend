"""
개발용 더미 데이터 삽입 스크립트
실행: python scripts/seed_data.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import User, UserPreference, Article
from passlib.context import CryptContext
from datetime import datetime, timedelta
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed():
    db = SessionLocal()
    try:
        # 더미 유저 3명
        users = [
            User(
                id=str(uuid.uuid4()),
                email="test1@curio.com",
                hashed_password=pwd_context.hash("password123"),
                name="김민준",
            ),
            User(
                id=str(uuid.uuid4()),
                email="test2@curio.com",
                hashed_password=pwd_context.hash("password123"),
                name="이수연",
            ),
            User(
                id=str(uuid.uuid4()),
                email="test3@curio.com",
                hashed_password=pwd_context.hash("password123"),
                name="박지원",
            ),
        ]
        for user in users:
            db.add(user)
        db.flush()

        # 각 유저 설정
        prefs = [
            UserPreference(user_id=users[0].id, topics=["ai", "economy"], digest_frequency="daily", digest_time="08:00"),
            UserPreference(user_id=users[1].id, topics=["economy", "sports"], digest_frequency="daily", digest_time="09:00"),
            UserPreference(user_id=users[2].id, topics=["ai", "science", "health"], digest_frequency="weekly", digest_time="08:00", digest_day="mon"),
        ]
        for pref in prefs:
            db.add(pref)

        # 더미 기사 30개 (카테고리별 3개씩)
        topics = ["ai", "economy", "sports", "culture", "politics", "science", "health", "world", "society", "entertain"]
        for i, topic in enumerate(topics):
            for j in range(3):
                article = Article(
                    id=str(uuid.uuid4()),
                    title=f"[{topic.upper()}] 테스트 기사 제목 {i*3+j+1}",
                    content=f"이것은 {topic} 카테고리의 테스트 기사 내용입니다. 개발 테스트용 더미 데이터입니다.",
                    ai_summary=f"{topic} 관련 주요 내용을 3줄로 요약한 텍스트입니다. 두 번째 줄입니다. 세 번째 줄입니다.",
                    source_name="테스트 언론사",
                    original_url=f"https://example.com/{topic}/{i*3+j+1}",
                    topic=topic,
                    tags=[topic, "테스트"],
                    relevance_score=round(0.5 + j * 0.1, 1),
                    read_time_minutes=3 + j,
                    published_at=datetime.utcnow() - timedelta(hours=j * 2),
                )
                db.add(article)

        db.commit()
        print("✅ 더미 데이터 삽입 완료!")
        print(f"   유저 3명: test1@curio.com, test2@curio.com, test3@curio.com")
        print(f"   비밀번호: password123")
        print(f"   기사 {len(topics) * 3}개 삽입 완료")

    except Exception as e:
        db.rollback()
        print(f"❌ 오류 발생: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
