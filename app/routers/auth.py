from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
import httpx
import os
from fastapi.responses import RedirectResponse
from app.models.user import UserActivityLog
import pytz
from datetime import datetime

from app.database import get_db
from app.models.user import User, UserPreference
from app.schemas.auth import (
    RegisterRequest, LoginRequest, LoginResponse,
    RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest
)
from app.services.auth_service import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    get_user_by_email
)

router = APIRouter()


# POST /api/auth/register — 회원가입
@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    # 이메일 중복 확인
    existing_user = get_user_by_email(body.email, db)
    if existing_user:
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFLICT", "detail": "이미 사용 중인 이메일입니다."}
        )

    # 유저 생성
    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        is_google=False
    )
    db.add(user)
    db.flush()

    # 기본 설정 생성
    preference = UserPreference(
        user_id=user.id,
        topics=[],
        keywords=[],
        digest_frequency="daily",
        digest_time="08:00"
    )
    db.add(preference)
    db.commit()

    # JWT 토큰 발급
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_google": user.is_google
            }
        }
    }


# POST /api/auth/login — 이메일 로그인
@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    from app.models.user import UserActivityLog
    from datetime import datetime
    import pytz

    # 유저 조회
    user = get_user_by_email(body.email, db)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "detail": "이메일 또는 비밀번호가 올바르지 않습니다."}
        )

    # 비밀번호 검증
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "detail": "이메일 또는 비밀번호가 올바르지 않습니다."}
        )

    # 출석 기록 저장 (하루 1회, 중복 방지)
    KST = pytz.timezone("Asia/Seoul")
    today = datetime.now(KST).date()
    existing_log = db.query(UserActivityLog).filter(
        UserActivityLog.user_id == user.id,
        UserActivityLog.activity_date == today
    ).first()

    if not existing_log:
        log = UserActivityLog(
            id=str(uuid.uuid4()),
            user_id=user.id,
            activity_date=today
        )
        db.add(log)
        db.commit()

    # JWT 토큰 발급
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_google": user.is_google
            }
        }
    }

# POST /api/auth/refresh — 토큰 갱신
@router.post("/refresh")
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    from jose import JWTError, jwt
    from dotenv import load_dotenv
    import os
    load_dotenv()

    try:
        payload = jwt.decode(body.refresh_token, os.getenv("SECRET_KEY"), algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "detail": "유효하지 않은 토큰입니다."})
    except JWTError:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "detail": "토큰이 만료되었습니다."})

    access_token = create_access_token(user_id)

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "token_type": "bearer"
        }
    }


# POST /api/auth/logout — 로그아웃
@router.post("/logout")
def logout():
    # 클라이언트에서 토큰 삭제하면 됨
    return {"success": True, "message": "로그아웃 되었습니다."}


# POST /api/auth/google — Google OAuth 로그인
@router.post("/google")
async def google_login(body: dict, db: Session = Depends(get_db)):
    from dotenv import load_dotenv
    load_dotenv()

    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code가 필요합니다")

    # code로 access_token 교환
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
                "grant_type": "authorization_code",
            }
        )
        token_data = token_response.json()

    if "error" in token_data:
        raise HTTPException(status_code=400, detail="Google 인증 실패")

    # access_token으로 유저 정보 조회
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        google_user = user_response.json()

    email = google_user.get("email")
    name = google_user.get("name", "")
    avatar_url = google_user.get("picture", "")

    if not email:
        raise HTTPException(status_code=400, detail="이메일을 가져올 수 없습니다")

    # 기존 유저 조회 또는 신규 생성
    user = get_user_by_email(email, db)
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            avatar_url=avatar_url,
            is_google=True
        )
        db.add(user)
        db.flush()

        preference = UserPreference(
            user_id=user.id,
            topics=[],
            keywords=[],
            digest_frequency="daily",
            digest_time="08:00"
        )
        db.add(preference)
        db.commit()

        # 출석 기록 저장 (하루 1회, 중복 방지)
    KST = pytz.timezone("Asia/Seoul")
    today = datetime.now(KST).date()
    existing_log = db.query(UserActivityLog).filter(
        UserActivityLog.user_id == user.id,
        UserActivityLog.activity_date == today
    ).first()

    if not existing_log:
        log = UserActivityLog(
            id=str(uuid.uuid4()),
            user_id=user.id,
            activity_date=today
        )
        db.add(log)
        db.commit()

    # JWT 토큰 발급
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_google": user.is_google
            }
        }
    }


# POST /api/auth/password/forgot — 비밀번호 재설정 요청
@router.post("/password/forgot")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # TODO: 이메일 발송 구현
    return {"success": True, "message": "재설정 링크를 이메일로 발송했습니다."}


# POST /api/auth/password/reset — 비밀번호 재설정 완료
@router.post("/password/reset")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    # TODO: 토큰 검증 후 비밀번호 변경
    return {"success": True, "message": "비밀번호가 변경되었습니다."}

# GET /api/auth/google/callback — Google OAuth 리다이렉트 콜백
@router.get("/google/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    from dotenv import load_dotenv
    load_dotenv()
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # code로 access_token 교환
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
                "grant_type": "authorization_code",
            }
        )
        token_data = token_response.json()
    print("Google token response:", token_data)  

    # 리다이렉트 방식 
    if  "error" in token_data:
        return RedirectResponse(url=f"{frontend_url}/auth/callback?error=google_auth_failed")

    # 유저 정보 조회
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        google_user = user_response.json()

    email = google_user.get("email")
    name = google_user.get("name", "")
    avatar_url = google_user.get("picture", "")

    if not email:
        return RedirectResponse(url=f"{frontend_url}/auth/callback?error=no_email")

    # 기존 유저 조회 또는 신규 생성
    user = get_user_by_email(email, db)
    is_new_user = False
    if not user:
        is_new_user = True
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            avatar_url=avatar_url,
            is_google=True
        )
        db.add(user)
        db.flush()

        preference = UserPreference(
            user_id=user.id,
            topics=[],
            keywords=[],
            digest_frequency="daily",
            digest_time="08:00"
        )
        db.add(preference)
        db.commit()

    # 출석 기록 저장
    KST = pytz.timezone("Asia/Seoul")
    today = datetime.now(KST).date()
    existing_log = db.query(UserActivityLog).filter(
        UserActivityLog.user_id == user.id,
        UserActivityLog.activity_date == today
    ).first()

    if not existing_log:
        log = UserActivityLog(
            id=str(uuid.uuid4()),
            user_id=user.id,
            activity_date=today
        )
        db.add(log)
        db.commit()

    # JWT 토큰 발급 후 프론트로 리다이렉트
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return RedirectResponse(
        url=f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}&is_new_user={str(is_new_user).lower()}"
    )