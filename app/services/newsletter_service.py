from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv
import os

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def send_newsletter(user_email: str, user_name: str, articles: list):
    """개인화 뉴스레터 이메일 발송 (SendGrid)"""
    html_content = build_newsletter_html(user_name, articles)

    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=user_email,
        subject=f"[Curio] {user_name}님의 오늘의 뉴스레터",
        html_content=html_content
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        print(f"SendGrid 발송 실패: {e}")


def build_newsletter_html(user_name: str, articles: list) -> str:
    """뉴스레터 HTML 본문 생성
    - 각 기사: 제목 + AI 3줄 요약 + 개인화 인사이트 + Curio 피드 링크
    """
    items_html = ""
    for article in articles:
        article_url = f"{FRONTEND_URL}/article/{article['id']}"
        items_html += f"""
        <div style="margin-bottom:32px; padding:20px; border:1px solid #eee; border-radius:8px;">
            <h2 style="font-size:18px; margin:0 0 12px;">
                <a href="{article_url}" style="color:#1a1a1a; text-decoration:none;">
                    {article['title']}
                </a>
            </h2>
            <p style="color:#555; font-size:14px; line-height:1.7; margin:0 0 12px;">
                {article.get('summary', '')}
            </p>
            <div style="background:#f8f8f8; padding:12px; border-radius:6px; margin-bottom:12px;">
                <span style="font-size:12px; color:#888;">AI 인사이트</span>
                <p style="margin:4px 0 0; font-size:14px; color:#333;">
                    {article.get('insight', '')}
                </p>
            </div>
            <a href="{article_url}" style="font-size:13px; color:#4f46e5;">
                Curio에서 더 읽기 →
            </a>
        </div>"""

    return f"""
    <html><body style="font-family:sans-serif; max-width:600px; margin:0 auto; padding:20px;">
        <h1 style="font-size:24px; color:#1a1a1a;">안녕하세요, {user_name}님 👋</h1>
        <p style="color:#555;">오늘의 맞춤 뉴스레터입니다.</p>
        {items_html}
        <hr style="border:none; border-top:1px solid #eee; margin:32px 0;">
        <p style="font-size:12px; color:#aaa; text-align:center;">
            Curio — 개인화 뉴스레터 서비스<br>
            <a href="{FRONTEND_URL}/settings" style="color:#aaa;">수신 설정 변경</a>
        </p>
    </body></html>"""
