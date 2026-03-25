from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.bookmark import BookmarkTagUpdateRequest

router = APIRouter()


# GET /api/news/saved/tags — 북마크 태그 목록 조회
@router.get("/saved/tags")
def get_bookmark_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: 구현
    pass


# PATCH /api/news/saved/{bookmark_id}/tags — 북마크 태그 수정 (전체 교체)
@router.patch("/saved/{bookmark_id}/tags")
def update_bookmark_tags(
    bookmark_id: str,
    body: BookmarkTagUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: 구현
    pass


# DELETE /api/news/saved/{bookmark_id}/tags/{tag_name} — 태그 1개 삭제
@router.delete("/saved/{bookmark_id}/tags/{tag_name}", status_code=204)
def delete_bookmark_tag(
    bookmark_id: str,
    tag_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: 구현
    pass
