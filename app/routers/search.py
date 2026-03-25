from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.search import RecentQueryRequest

router = APIRouter()


# GET /api/search/recent — 최근 검색어 조회
@router.get("/recent")
def get_recent_queries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: 구현
    pass


# POST /api/search/recent — 최근 검색어 저장 (UPSERT)
@router.post("/recent", status_code=201)
def save_recent_query(
    body: RecentQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: 구현
    pass


# DELETE /api/search/recent — 최근 검색어 전체 삭제
@router.delete("/recent", status_code=204)
def delete_recent_queries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: 구현
    pass
