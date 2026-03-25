from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.chat import ChatRequest

router = APIRouter()


# POST /api/chat — AI 챗봇 메시지 전송 (SSE 스트리밍)
@router.post("")
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: Claude API SSE 스트리밍 응답 구현
    # StreamingResponse(generate(), media_type="text/event-stream") 반환
    pass


# GET /api/chat/sessions — 챗봇 세션 목록 조회
@router.get("/sessions")
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: 구현
    pass


# GET /api/chat/sessions/{session_id}/messages — 세션 메시지 조회
@router.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: 구현
    pass
