from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
import os

load_dotenv()

app = Celery(
    "curio",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["tasks.collect_news", "tasks.send_newsletter"]
)

app.conf.timezone = "Asia/Seoul"

# 스케줄 설정
app.conf.beat_schedule = {
    # 매시간 정각 뉴스 수집
    "collect-news-every-hour": {
        "task": "tasks.collect_news.collect_all_topics",
        "schedule": crontab(minute=0),
    },
    # 매분 발송 시간 도달한 유저 뉴스레터 발송 체크
    "send-newsletters": {
        "task": "tasks.send_newsletter.dispatch_newsletters",
        "schedule": crontab(minute="*"),
    },
}
