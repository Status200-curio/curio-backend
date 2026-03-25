from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from app.routers import auth, news, bookmark, search, user, chat

load_dotenv()

app = FastAPI(
    title="Curio API",
    description="개인화 뉴스레터 및 정보 큐레이션 서비스 — Status 200",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router,     prefix="/api/auth",   tags=["Auth"])
app.include_router(news.router,     prefix="/api/news",   tags=["News"])
app.include_router(bookmark.router, prefix="/api/news",   tags=["Bookmark"])
app.include_router(search.router,   prefix="/api/search", tags=["Search"])
app.include_router(user.router,     prefix="/api/user",   tags=["User"])
app.include_router(chat.router,     prefix="/api/chat",   tags=["Chat"])


@app.get("/")
def root():
    return {"message": "Curio API is running"}
