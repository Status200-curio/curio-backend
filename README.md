 # Curio Backend

개인화 뉴스레터 및 정보 큐레이션 서비스 — FastAPI 백엔드

## 팀 정보
- 팀명: Status 200
- 담당 교수: 김태리 교수님

## 기술 스택
- **Framework**: FastAPI (Python 3.11)
- **DB**: PostgreSQL 16 + SQLAlchemy ORM + Alembic
- **Cache / Broker**: Redis
- **Background**: Celery
- **AI**: Gemini API
- **News**: NewsAPI + RSS feedparser
- **Email**: SendGrid
- **Auth**: JWT + Google OAuth2

## 로컬 개발 환경 세팅

### 1. 가상환경 생성 및 패키지 설치
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일에 실제 API 키 입력
```

### 3. DB 마이그레이션
```bash
alembic upgrade head
```

### 4. 더미 데이터 삽입 (선택)
```bash
python scripts/seed_data.py
```

### 5. 서버 실행
```bash
uvicorn app.main:app --reload
```

### 6. Celery Worker 실행 (별도 터미널)
```bash
celery -A tasks.celery_app worker --loglevel=info
```

### 7. Celery Beat 실행 (별도 터미널)
```bash
celery -A tasks.celery_app beat --loglevel=info
```

## API 문서
서버 실행 후 http://localhost:8000/docs 접속

## 브랜치 전략
- `main`: 배포용
- `develop`: 개발 통합
- `feature/기능명`: 기능 개발
