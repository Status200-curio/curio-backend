from sqlalchemy.orm import Session
from app.models import UserPreference, UserArticleInteraction, ArticleView


def calculate_relevance_score(article_topic: str, article_tags: list, user_pref: UserPreference) -> float:
    """기사와 유저 관심사 간 관련도 점수 계산 (0.0 ~ 1.0)"""
    score = 0.0
    user_topics = user_pref.topics or []
    user_keywords = user_pref.keywords or []

    # 카테고리 일치 여부
    if article_topic in user_topics:
        score += 0.6

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

    topics = pref.topics or []

    if feedback == "like":
        # 좋아요: 해당 토픽이 없으면 추가
        if article_topic not in topics:
            topics.append(article_topic)
    elif feedback == "dislike":
        # 싫어요: 해당 토픽 제거 (단, 최소 1개 유지)
        if article_topic in topics and len(topics) > 1:
            topics.remove(article_topic)

    pref.topics = topics
    db.commit()
