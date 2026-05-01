from sqlalchemy.orm import Session
from app.models.user import UserPreference
from app.models.article import UserArticleInteraction


def calculate_relevance_score(article_topic: str, article_tags: list, user_pref: UserPreference) -> float:
    """기사와 유저 관심사 간 관련도 점수 계산 (0.0 ~ 1.0)"""
    score = 0.0
    user_topics = user_pref.topics or []
    user_keywords = user_pref.keywords or []
    topic_weights = user_pref.topic_weights or {}

    # 카테고리 일치 여부 + 가중치 반영
    if article_topic in user_topics:
        base_score = 0.6
        weight = topic_weights.get(article_topic, 1.0)  # 기본 가중치 1.0
        score += base_score * weight

    # 키워드 매칭
    matched_keywords = [kw for kw in user_keywords if kw in article_tags]
    if matched_keywords:
        score += min(0.4, len(matched_keywords) * 0.1)

    return round(min(score, 1.0), 2)


def update_topic_weights(user_id: str, article_topic: str, feedback: str, db: Session):
    """피드백(좋아요/싫어요) 기반 관심사 가중치 업데이트"""
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not pref:
        return

    topic_weights = dict(pref.topic_weights or {})

    if feedback == "like":
        # 좋아요: 가중치 +0.3 (최대 2.0)
        current = topic_weights.get(article_topic, 1.0)
        topic_weights[article_topic] = round(min(2.0, current + 0.3), 1)

    elif feedback == "dislike":
        # 싫어요: 가중치 -0.2 (최소 0.1)
        current = topic_weights.get(article_topic, 1.0)
        topic_weights[article_topic] = round(max(0.1, current - 0.2), 1)

    pref.topic_weights = topic_weights
    db.commit()
    print(f"[가중치] {article_topic}: {topic_weights.get(article_topic)}")