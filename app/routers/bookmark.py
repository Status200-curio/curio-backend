from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.bookmark import Bookmark, BookmarkTag
from app.schemas.bookmark import BookmarkTagUpdateRequest
from urllib.parse import unquote

router = APIRouter()


# GET /api/news/saved/tags — 북마크 태그 목록 조회
@router.get("/saved/tags")
def get_bookmark_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 유저의 모든 북마크 조회
    bookmarks = db.query(Bookmark).filter(
        Bookmark.user_id == current_user.id
    ).all()

    bookmark_ids = [b.id for b in bookmarks]

    # 태그 목록 조회
    tags = db.query(BookmarkTag).filter(
        BookmarkTag.bookmark_id.in_(bookmark_ids)
    ).all()

    # 중복 제거
    unique_tags = list(set([t.name for t in tags]))

    return {
        "success": True,
        "data": unique_tags
    }


# PATCH /api/news/saved/{bookmark_id}/tags — 북마크 태그 수정
@router.patch("/saved/{bookmark_id}/tags")
def update_bookmark_tags(
    bookmark_id: str,
    body: BookmarkTagUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 북마크 확인
    bookmark = db.query(Bookmark).filter(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == current_user.id
    ).first()

    if not bookmark:
        raise HTTPException(status_code=404, detail="북마크를 찾을 수 없습니다")

    # 기존 태그 전체 삭제
    db.query(BookmarkTag).filter(
        BookmarkTag.bookmark_id == bookmark_id
    ).delete()

    # 새 태그 추가
    for tag_name in body.tags:
        tag = BookmarkTag(
            bookmark_id=bookmark_id,
            name=tag_name
        )
        db.add(tag)

    db.commit()

    return {
        "success": True,
        "data": {
            "bookmark_id": bookmark_id,
            "tags": body.tags
        }
    }


# DELETE /api/news/saved/{bookmark_id}/tags/{tag_name} — 태그 1개 삭제
@router.delete("/saved/{bookmark_id}/tags/{tag_name}", status_code=204)
def delete_bookmark_tag(
    bookmark_id: str,
    tag_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tag_name = unquote(tag_name) # URL에서 한글이 자동으로 인코딩되게함

    # 북마크 확인
    bookmark = db.query(Bookmark).filter(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == current_user.id
    ).first()

    if not bookmark:
        raise HTTPException(status_code=404, detail="북마크를 찾을 수 없습니다")

    # 태그 삭제
    tag = db.query(BookmarkTag).filter(
    BookmarkTag.bookmark_id == bookmark_id,
    BookmarkTag.name == tag_name  # tag_name → name
    ).first()

    if not tag:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다")

    db.delete(tag)
    db.commit()