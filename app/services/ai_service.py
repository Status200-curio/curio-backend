from google import genai
from dotenv import load_dotenv
import os
import json
import time

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _call_gemini(prompt: str, retries: int = 3) -> str:
    """Gemini API 호출 — 실패 시 최대 3회 재시도"""
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=prompt
            )
            text = response.text.strip()

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            return text
        except Exception as e:
            print(f"Gemini API 오류 (시도 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(15)
    return ""


def generate_summary(title: str, content: str) -> str:
    """기사 3줄 요약 생성 — 모든 유저 공통 캐싱"""
    text_input = content[:2000] if content else "내용 없음"

    prompt = f"""다음 뉴스 기사를 반드시 한국어로 3줄 이내로 요약해줘.
영어 기사라도 한국어로 요약해야 해.
반드시 JSON 형식으로만 응답해. 다른 텍스트 없이 JSON만.

제목: {title}
내용: {text_input}

응답 형식:
{{"summary": "3줄 요약 내용"}}"""

    text = _call_gemini(prompt)

    if not text:
        return ""

    try:
        result = json.loads(text)
        return result.get("summary", "")
    except json.JSONDecodeError:
        print(f"JSON 파싱 실패: {text[:100]}")
        return ""


def generate_insight(title: str, content: str, user_topics: list, user_keywords: list = [], user_sub_topics: list = []) -> str:
    """개인화 인사이트 생성 — 유저 관심사 기반, 유저별 다름"""
    if not user_topics:
        return ""

    topics_str = ", ".join(user_topics)
    keywords_str = ", ".join(user_keywords) if user_keywords else ""
    sub_topics_str = ", ".join(user_sub_topics) if user_sub_topics else ""
    text_input = content[:1500] if content else "내용 없음"

    keyword_line = f"\n관심 키워드: {keywords_str}" if keywords_str else ""
    sub_topic_line = f"\n세부 관심사: {sub_topics_str}" if sub_topics_str else ""

    prompt = f"""당신은 개인화 뉴스 인사이트 전문가입니다.

아래 뉴스 기사를 읽고, 이 독자의 관심사({topics_str}){sub_topic_line}{keyword_line}를 가진 사람의 시각에서
왜 이 기사가 중요한지 분석해주세요.

엄격한 규칙:
1. 반드시 1~2문장으로만 작성 (절대 초과 금지)
2. 관심사별로 나눠서 쓰지 말 것 (하나의 통합된 관점으로)
3. "~관점에서", "~분야에서" 같은 표현 사용 금지
4. 독자에게 직접 말하듯 자연스럽게 작성
5. 반드시 한국어로 작성
6. 반드시 JSON 형식으로만 응답 (다른 텍스트 절대 금지)

제목: {title}
내용: {text_input}

응답 형식:
{{"insight": "1~2문장 인사이트"}}"""

    text = _call_gemini(prompt)

    if not text:
        return ""

    try:
        result = json.loads(text)
        return result.get("insight", "")
    except json.JSONDecodeError:
        print(f"JSON 파싱 실패: {text[:100]}")
        return ""


def translate_title(title: str) -> str:
    """영어 제목을 한국어로 번역 — 영어가 아니면 그대로 반환"""
    alpha_count = sum(1 for c in title if c.isascii() and c.isalpha())
    if len(title) == 0 or alpha_count / len(title) < 0.5:
        return title

    prompt = f"""다음 영어 제목을 한국어로 자연스럽게 번역해줘.
반드시 JSON 형식으로만 응답해. 다른 텍스트 없이 JSON만.

제목: {title}

응답 형식:
{{"title": "한국어 번역 제목"}}"""

    text = _call_gemini(prompt)

    if not text:
        return title

    try:
        result = json.loads(text)
        return result.get("title", title)
    except json.JSONDecodeError:
        return title


async def chat_stream(article_title: str, article_content: str, messages: list):
    """AI 챗봇 SSE 스트리밍 — 기사 컨텍스트 기반"""
    system_prompt = f"""너는 뉴스 기사 분석 전문가야.
아래 기사를 바탕으로 사용자의 질문에 친절하고 명확하게 한국어로 답변해줘.

기사 제목: {article_title}
기사 내용: {article_content[:2000] if article_content else "내용 없음"}"""

    last_message = messages[-1]["content"] if messages else ""
    full_prompt = f"{system_prompt}\n\n{last_message}"

    contents = []
    for msg in messages[:-1]:
        contents.append({
            "role": msg["role"],
            "parts": [{"text": msg["content"]}]
        })
    contents.append({
        "role": "user",
        "parts": [{"text": full_prompt}]
    })

    response = client.models.generate_content_stream(
        model="gemini-3.1-flash-lite-preview",
        contents=contents
    )

    for chunk in response:
        if chunk.text:
            yield f"data: {chunk.text}\n\n"

    yield "data: [DONE]\n\n"