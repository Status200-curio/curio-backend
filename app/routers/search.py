from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.search import SearchRecentQuery
from app.schemas.search import RecentQueryRequest
import uuid

router = APIRouter()


# GET /api/search/recent — 최근 검색어 조회
@router.get("/recent")
def get_recent_queries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    queries = db.query(SearchRecentQuery).filter(
        SearchRecentQuery.user_id == current_user.id
    ).order_by(SearchRecentQuery.searched_at.desc()).limit(10).all()

    return {
        "success": True,
        "data": [q.query for q in queries]
    }


# POST /api/search/recent — 최근 검색어 저장
@router.post("/recent", status_code=201)
def save_recent_query(
    body: RecentQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 이미 있으면 시간만 업데이트 (UPSERT)
    existing = db.query(SearchRecentQuery).filter(
        SearchRecentQuery.user_id == current_user.id,
        SearchRecentQuery.query == body.query
    ).first()

    if existing:
        from sqlalchemy.sql import func
        existing.searched_at = func.now()
        db.commit()
    else:
        # 최대 10개 유지 — 넘으면 가장 오래된 것 삭제
        count = db.query(SearchRecentQuery).filter(
            SearchRecentQuery.user_id == current_user.id
        ).count()

        if count >= 10:
            oldest = db.query(SearchRecentQuery).filter(
                SearchRecentQuery.user_id == current_user.id
            ).order_by(SearchRecentQuery.searched_at.asc()).first()
            db.delete(oldest)

        new_query = SearchRecentQuery(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            query=body.query
        )
        db.add(new_query)
        db.commit()

    return {"success": True}


# DELETE /api/search/recent — 최근 검색어 전체 삭제
@router.delete("/recent", status_code=204)
def delete_recent_queries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db.query(SearchRecentQuery).filter(
        SearchRecentQuery.user_id == current_user.id
    ).delete()
    db.commit()