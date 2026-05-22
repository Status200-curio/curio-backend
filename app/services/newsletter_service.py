import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
from datetime import datetime
import pytz

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

TOPIC_EMOJI = {
    "ai":       "💻 IT/기술",
    "economy":  "💰 경제",
    "sports":   "🏆 스포츠",
    "culture":  "🎨 문화",
    "politics": "🏛️ 정치",
    "science":  "🔬 과학",
    "health":   "💊 건강",
    "world":    "🌍 국제",
    "society":  "👥 사회",
    "entertain":"🎬 연예",
}


def send_newsletter(user_email: str, user_name: str, articles: list):
    """개인화 뉴스레터 이메일 발송 (Gmail SMTP)"""
    html_content = build_newsletter_html(user_name, articles)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Curio] {user_name}님의 오늘의 뉴스레터"
    msg["From"] = GMAIL_USER
    msg["To"] = user_email

    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, user_email, msg.as_string())
            print(f"[뉴스레터] {user_email} 발송 완료")
    except Exception as e:
        print(f"Gmail SMTP 발송 실패: {e}")


def build_newsletter_html(user_name: str, articles: list) -> str:
    """뉴스레터 HTML 본문 생성"""
    KST = pytz.timezone("Asia/Seoul")
    today = datetime.now(KST).strftime("%Y년 %m월 %d일")

    items_html = ""
    for article in articles:
        article_url = f"{FRONTEND_URL}/article/{article['id']}"
        thumbnail = article.get('thumbnail_url', '')
        topic = article.get('topic', '')
        topic_label = TOPIC_EMOJI.get(topic, '📰 뉴스')

        thumbnail_html = f'<img src="{thumbnail}" style="width:100%; max-height:200px; object-fit:cover; border-radius:8px; margin-bottom:14px;">' if thumbnail else ''

        insight = article.get('insight', '')
        insight_html = f"""
        <div style="background:#f0f4ff; padding:12px 16px; border-radius:8px; margin-bottom:14px; border-left:3px solid #4f46e5;">
            <span style="font-size:11px; color:#4f46e5; font-weight:600;">✨ AI 인사이트</span>
            <p style="margin:4px 0 0; font-size:13px; color:#333; line-height:1.6;">{insight}</p>
        </div>""" if insight else ''

        items_html += f"""
        <div style="margin-bottom:24px; padding:20px; border:1px solid #eee; border-radius:12px; background:#fff;">
            {thumbnail_html}
            <span style="font-size:11px; color:#4f46e5; font-weight:600; background:#ede9fe; padding:3px 10px; border-radius:20px;">{topic_label}</span>
            <h2 style="font-size:16px; margin:10px 0 10px; line-height:1.5;">
                <a href="{article_url}" style="color:#1a1a1a; text-decoration:none;">
                    {article['title']}
                </a>
            </h2>
            <p style="color:#555; font-size:13px; line-height:1.7; margin:0 0 12px;">
                {article.get('summary', '')}
            </p>
            {insight_html}
            <a href="{article_url}" style="font-size:13px; color:#4f46e5; font-weight:500;">
                Curio에서 더 읽기 →
            </a>
        </div>"""

    return f"""
    <html>
    <body style="background:#f5f5f5; font-family:sans-serif; margin:0; padding:0;">
        <div style="max-width:600px; margin:0 auto; padding:20px;">
            <div style="background:linear-gradient(135deg, #4f46e5, #7c3aed); border-radius:12px; padding:28px; margin-bottom:24px; text-align:center;">
                <h1 style="color:#fff; font-size:26px; margin:0 0 6px;">📰 Curio</h1>
                <p style="color:#c4b5fd; margin:0; font-size:14px;">{today} · {user_name}님의 맞춤 뉴스레터</p>
            </div>
            {items_html}
            <hr style="border:none; border-top:1px solid #ddd; margin:24px 0;">
            <p style="font-size:12px; color:#aaa; text-align:center; line-height:1.8;">
                Curio — 개인화 뉴스레터 서비스<br>
                <a href="{FRONTEND_URL}/settings" style="color:#4f46e5;">수신 설정 변경</a>
            </p>
        </div>
    </body>
    </html>"""