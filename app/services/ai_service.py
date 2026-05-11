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


def generate_insight(title: str, content: str, user_topics: list, user_keywords: list = [], user_sub_topics: list = [], topic: str = "", article_tags: list = []) -> str:
    """개인화 인사이트 생성 — 유저 관심사 기반, 유저별 다름"""
    if not user_topics:
        return ""

    topics_str = ", ".join(user_topics)
    keywords_str = ", ".join(user_keywords) if user_keywords else ""
    sub_topics_str = ", ".join(user_sub_topics) if user_sub_topics else ""
    text_input = content[:1500] if content else "내용 없음"

    keyword_line = f"\n- 관심 키워드: {keywords_str}" if keywords_str else ""
    sub_topic_line = f"\n- 세부 관심사: {sub_topics_str}" if sub_topics_str else ""

    # 세부 카테고리별 가이드
    sub_topic_guide = {
        # 경제
        "stock":      "주식 투자자 시각에서 이 기사가 종목 선택이나 매매 타이밍에 미치는 영향을 분석해주세요.",
        "crypto":     "가상화폐 투자자 시각에서 시장 흐름과 투자 전략에 미치는 영향을 분석해주세요.",
        "realestate": "부동산 관심자 시각에서 매매/전세 시장에 미치는 영향을 분석해주세요.",
        "finance":    "금융 소비자 시각에서 금리/대출/저축에 미치는 영향을 분석해주세요.",
        "trade":      "무역/경제 관심자 시각에서 국내 산업과 경제에 미치는 영향을 분석해주세요.",
        "company":    "투자자 시각에서 기업 가치와 주가에 미치는 영향을 분석해주세요.",
        "exchange":   "환율 관심자 시각에서 환전이나 해외 투자에 미치는 영향을 분석해주세요.",
        "employment": "구직자/직장인 시각에서 취업 시장과 커리어에 미치는 영향을 분석해주세요.",
        # 스포츠
        "football":   "축구팬 시각에서 경기 관전 포인트나 선수/팀 상황을 짚어주세요.",
        "baseball":   "야구팬 시각에서 경기 관전 포인트나 선수/팀 상황을 짚어주세요.",
        "basketball": "농구팬 시각에서 경기 관전 포인트나 선수/팀 상황을 짚어주세요.",
        "golf":       "골프팬 시각에서 대회 관전 포인트나 선수 상황을 짚어주세요.",
        "esports":    "e스포츠팬 시각에서 대회 관전 포인트나 팀/선수 상황을 짚어주세요.",
        "volleyball": "배구팬 시각에서 경기 관전 포인트나 선수/팀 상황을 짚어주세요.",
        "badminton":  "배드민턴팬 시각에서 대회 관전 포인트나 선수 상황을 짚어주세요.",
        "tennis":     "테니스팬 시각에서 대회 관전 포인트나 선수 상황을 짚어주세요.",
        "mma":        "격투기팬 시각에서 경기 관전 포인트나 선수 상황을 짚어주세요.",
        "motorsports":"모터스포츠팬 시각에서 레이스 관전 포인트나 드라이버 상황을 짚어주세요.",
        "swimming":   "수영팬 시각에서 대회 관전 포인트나 선수 상황을 짚어주세요.",
        "boxing":     "복싱팬 시각에서 경기 관전 포인트나 선수 상황을 짚어주세요.",
        "taekwondo":  "태권도팬 시각에서 대회 관전 포인트나 선수 상황을 짚어주세요.",
        "judo":       "유도팬 시각에서 대회 관전 포인트나 선수 상황을 짚어주세요.",
        "fencing":    "펜싱팬 시각에서 대회 관전 포인트나 선수 상황을 짚어주세요.",
        "archery":    "양궁팬 시각에서 대회 관전 포인트나 선수 상황을 짚어주세요.",
        # IT/기술
        "llm":         "AI/LLM 관심자 시각에서 이 기술이 가져올 변화나 활용 포인트를 알려주세요.",
        "semiconductor":"반도체 관심자 시각에서 산업 트렌드와 투자 포인트를 알려주세요.",
        "mobile":      "모바일 사용자 시각에서 실생활에 미치는 영향을 알려주세요.",
        "security":    "보안 관심자 시각에서 개인정보 보호나 주의할 점을 알려주세요.",
        "startup":     "스타트업 관심자 시각에서 창업 트렌드나 투자 포인트를 알려주세요.",
        "cloud":       "클라우드 관심자 시각에서 산업 변화와 주목할 포인트를 알려주세요.",
        "ev":          "전기차 관심자 시각에서 시장 변화나 구매/투자 포인트를 알려주세요.",
        "internet":    "인터넷/SNS 사용자 시각에서 트렌드 변화와 활용 포인트를 알려주세요.",
        "game_tech":   "게임/메타버스 관심자 시각에서 트렌드 변화와 주목할 포인트를 알려주세요.",
        # 건강
        "disease":  "건강 관리 시각에서 예방이나 주의해야 할 점을 알려주세요.",
        "fitness":  "운동하는 사람 시각에서 실생활에 적용할 수 있는 방법을 알려주세요.",
        "diet":     "다이어트 관심자 시각에서 실생활에 적용할 수 있는 방법을 알려주세요.",
        "mental":   "정신건강 관심자 시각에서 일상에서 실천할 수 있는 방법을 알려주세요.",
        "beauty":   "뷰티 관심자 시각에서 실생활에 적용할 수 있는 팁을 알려주세요.",
        "medical":  "의료 관심자 시각에서 건강 관리에 도움이 되는 정보를 알려주세요.",
        "nutrition":"영양 관심자 시각에서 식단이나 영양 관리에 도움이 되는 정보를 알려주세요.",
        "pharma":   "제약/바이오 관심자 시각에서 신약이나 의료 기술 변화를 알려주세요.",
        # 연예
        "kpop":    "K-POP팬 시각에서 놓치면 안 될 포인트나 관련 콘텐츠를 추천해주세요.",
        "drama":   "드라마 시청자 시각에서 놓치면 안 될 포인트를 알려주세요.",
        "variety": "예능 시청자 시각에서 놓치면 안 될 포인트를 알려주세요.",
        "actor":   "배우 팬 시각에서 놓치면 안 될 포인트를 알려주세요.",
        "overseas":"해외 연예 팬 시각에서 놓치면 안 될 포인트를 알려주세요.",
        "kmusic":  "가요 팬 시각에서 놓치면 안 될 포인트를 알려주세요.",
        # 문화
        "movie":      "영화 팬 시각에서 꼭 봐야 할 이유나 관람 포인트를 알려주세요.",
        "music":      "음악 팬 시각에서 놓치면 안 될 포인트를 알려주세요.",
        "art":        "미술/전시 관심자 시각에서 꼭 경험해봐야 할 이유를 알려주세요.",
        "book":       "독서 관심자 시각에서 이 책/작가를 주목해야 할 이유를 알려주세요.",
        "travel":     "여행 관심자 시각에서 여행 계획에 도움이 되는 정보를 알려주세요.",
        "food":       "음식/맛집 관심자 시각에서 꼭 가봐야 할 이유나 팁을 알려주세요.",
        "fashion":    "패션 관심자 시각에서 트렌드 변화와 스타일링 포인트를 알려주세요.",
        "game":       "게임 팬 시각에서 놓치면 안 될 포인트를 알려주세요.",
        "performance":"공연 관심자 시각에서 꼭 봐야 할 이유나 관람 포인트를 알려주세요.",
        # 과학
        "space":      "우주 관심자 시각에서 이 발견이 미래에 가져올 변화를 알려주세요.",
        "environment":"환경 관심자 시각에서 일상에서 실천할 수 있는 방법을 알려주세요.",
        "biology":    "생명과학 관심자 시각에서 이 연구가 가져올 변화를 알려주세요.",
        "physics":    "물리/화학 관심자 시각에서 이 연구가 가져올 변화를 알려주세요.",
        "medicine":   "의학/바이오 관심자 시각에서 이 연구가 건강에 미치는 영향을 알려주세요.",
        "math":       "수학/통계 관심자 시각에서 이 연구의 실용적 활용 포인트를 알려주세요.",
        "robot":      "로봇/기계 관심자 시각에서 이 기술이 가져올 변화를 알려주세요.",
        "energy":     "에너지/신소재 관심자 시각에서 이 기술이 가져올 변화를 알려주세요.",
        # 사회
        "education":   "학생/학부모 시각에서 교육 정책이나 입시에 미치는 영향을 알려주세요.",
        "crime":       "시민 시각에서 이 사건이 사회 안전에 미치는 영향을 알려주세요.",
        "welfare":     "복지 관심자 시각에서 실생활에 도움이 되는 정보를 알려주세요.",
        "labor":       "직장인 시각에서 노동 환경 변화가 내 삶에 미치는 영향을 알려주세요.",
        "disaster":    "시민 시각에서 재난 대비나 안전 관리에 도움이 되는 정보를 알려주세요.",
        "human_rights":"인권 관심자 시각에서 이 이슈가 사회에 미치는 영향을 알려주세요.",
        "media":       "미디어 소비자 시각에서 이 이슈가 정보 환경에 미치는 영향을 알려주세요.",
        "religion":    "종교 관심자 시각에서 이 이슈가 사회에 미치는 영향을 알려주세요.",
        "local":       "지역 주민 시각에서 이 이슈가 지역 생활에 미치는 영향을 알려주세요.",
        # 국제
        "us":           "글로벌 관심자 시각에서 미국 이슈가 한국에 미치는 영향을 알려주세요.",
        "china":        "글로벌 관심자 시각에서 중국 이슈가 한국에 미치는 영향을 알려주세요.",
        "japan":        "글로벌 관심자 시각에서 일본 이슈가 한국에 미치는 영향을 알려주세요.",
        "europe":       "글로벌 관심자 시각에서 유럽 이슈가 한국에 미치는 영향을 알려주세요.",
        "middleeast":   "글로벌 관심자 시각에서 중동 이슈가 에너지/경제에 미치는 영향을 알려주세요.",
        "asia":         "글로벌 관심자 시각에서 아시아 이슈가 한국에 미치는 영향을 알려주세요.",
        "russia":       "글로벌 관심자 시각에서 러시아 이슈가 한국에 미치는 영향을 알려주세요.",
        "world_economy":"글로벌 경제 관심자 시각에서 세계 경제 흐름이 한국에 미치는 영향을 알려주세요.",
        "world_affairs":"글로벌 관심자 시각에서 국제 정세가 한국에 미치는 영향을 알려주세요.",
        # 정치
        "domestic":   "시민 시각에서 이 정치 이슈가 일상생활에 미치는 영향을 알려주세요.",
        "election":   "유권자 시각에서 이 선거 이슈가 정치 지형에 미치는 영향을 알려주세요.",
        "northkorea": "안보 관심자 시각에서 이 북한 이슈가 한반도 정세에 미치는 영향을 알려주세요.",
        "foreign":    "글로벌 관심자 시각에서 이 외교 이슈가 한국에 미치는 영향을 알려주세요.",
        "policy":     "시민 시각에서 이 정책이 일상생활에 미치는 직접적인 영향을 알려주세요.",
        "judiciary":  "시민 시각에서 이 사법 이슈가 법치와 사회에 미치는 영향을 알려주세요.",
    }

    # 큰 카테고리 가이드
    topic_guide = {
        "economy":  "경제 관심자 시각에서 이 기사가 일상 경제생활에 미치는 영향과 구체적인 액션을 제안해주세요.",
        "sports":   "스포츠팬 시각에서 경기 관전 포인트나 선수/팀 상황을 짚어주세요.",
        "ai":       "기술 관심자 시각에서 이 기술이 가져올 변화나 주목할 포인트를 알려주세요.",
        "entertain":"엔터테인먼트 팬 시각에서 놓치면 안 될 포인트나 관련 콘텐츠를 추천해주세요.",
        "health":   "건강 관리 시각에서 실생활에 적용할 수 있는 구체적인 행동을 제안해주세요.",
        "politics": "시민 시각에서 이 정책이나 이슈가 일상생활에 미치는 직접적인 영향을 알려주세요.",
        "science":  "일반인 시각에서 이 과학적 발견이 미래에 어떤 변화를 가져올지 알려주세요.",
        "culture":  "문화 소비자 시각에서 꼭 경험해봐야 할 이유나 추천 포인트를 알려주세요.",
        "society":  "시민 시각에서 이 사회 이슈가 내 삶과 어떻게 연결되는지 알려주세요.",
        "world":    "글로벌 관심자 시각에서 이 이슈가 한국에 미치는 영향을 알려주세요.",
    }

    # 기사 topic에 맞는 sub_topic 중 기사 tags에도 있는 것만 매칭
    topic_sub_mapping = {
        "sports":   ["football", "baseball", "basketball", "golf", "esports",
                     "volleyball", "badminton", "tennis", "mma", "motorsports",
                     "swimming", "boxing", "taekwondo", "judo", "fencing", "archery"],
        "economy":  ["stock", "crypto", "realestate", "finance", "trade",
                     "company", "exchange", "employment"],
        "ai":       ["llm", "semiconductor", "mobile", "security", "startup",
                     "cloud", "internet", "ev", "game_tech"],
        "entertain":["kpop", "drama", "variety", "actor", "overseas", "kmusic"],
        "health":   ["disease", "medical", "fitness", "diet", "mental",
                     "beauty", "nutrition", "pharma"],
        "culture":  ["movie", "music", "art", "book", "travel", "food",
                     "fashion", "game", "performance"],
        "science":  ["space", "environment", "biology", "physics", "medicine",
                     "math", "robot", "energy"],
        "society":  ["education", "crime", "welfare", "labor", "disaster",
                     "human_rights", "media", "religion", "local"],
        "world":    ["us", "china", "japan", "europe", "middleeast", "asia",
                     "russia", "world_economy", "world_affairs"],
        "politics": ["domestic", "election", "northkorea", "foreign",
                     "policy", "judiciary"],
    }

    valid_subs = topic_sub_mapping.get(topic, [])

    # 유저 sub_topics + 기사 tags 교차 매칭
    matched = [st for st in user_sub_topics
               if st in valid_subs
               and st in sub_topic_guide
               and st in article_tags]

    if matched:
        guide = sub_topic_guide[matched[0]]
    else:
        guide = topic_guide.get(topic, "독자에게 이 기사가 왜 중요한지 핵심을 짚어주세요.")

    prompt = f"""당신은 개인화 뉴스 인사이트 전문가입니다.

아래 뉴스 기사를 읽고, 독자에게 실질적으로 도움이 되는 인사이트를 제공해주세요.

독자 정보:
- 관심 카테고리: {topics_str}{sub_topic_line}{keyword_line}

인사이트 방향:
{guide}

엄격한 규칙:
1. 반드시 1~2문장으로만 작성 (절대 초과 금지)
2. 기사 내용과 직접 관련된 인사이트만 작성
3. 관심 키워드를 억지로 끼워넣지 말 것
4. "~해보세요", "~주목하세요", "~확인해보세요" 같은 액션 중심으로 작성
5. 독자에게 직접 말하듯 자연스럽게 작성
6. 반드시 한국어로 작성
7. 반드시 JSON 형식으로만 응답 (다른 텍스트 절대 금지)

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

답변 규칙:
1. 인사말, 자기소개, 맺음말 금지 ("안녕하세요", "궁금한 점이 있으시면" 등)
2. 기사 내용에 없는 사실은 답변하지 말 것
3. 핵심만 간결하게
4. 필요시 번호 목록 또는 줄바꿈 활용
5. 기사와 무관한 질문이면 "이 기사와 관련된 질문만 답변할 수 있습니다"라고 안내

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