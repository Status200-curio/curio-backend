import httpx
import feedparser
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from datetime import datetime
from bs4 import BeautifulSoup
import logging
import os
import uuid

from app.models.article import Article

load_dotenv()
logger = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# 카테고리별 RSS 피드 URL (여러 개)
RSS_FEEDS = {
    "ai": [
        # 국내 IT 전문지
        "https://rss.etnews.com/Section901.xml",          # 전자신문
        "https://zdnet.co.kr/rss/rss.php",                # ZDNet Korea
        "https://www.ddaily.co.kr/rss/all.xml",           # 디지털데일리           
        "https://www.bloter.net/feed",                    # 블로터

        # 글로벌 테크
        "https://techcrunch.com/feed/",                   # TechCrunch
        "https://venturebeat.com/feed/",                  # VentureBeat
        "https://feeds.arstechnica.com/arstechnica/index", # Ars Technica
        "https://www.theverge.com/rss/index.xml",         # The Verge
        "https://feeds.feedburner.com/TheHackersNews",

        # AI 전문
        "https://openai.com/news/rss.xml",                # OpenAI
        "https://blog.google/technology/ai/rss/",         # Google AI
        "https://www.marktechpost.com/feed/",             # MarkTechPost
    ],
    "economy": [
        "https://www.yna.co.kr/rss/economy.xml",
        "https://news.kbs.co.kr/rss/rss_economy.xml",
        "https://www.hankyung.com/feed/economy",
        "https://rss.mk.co.kr/rss/30200030.xml",
        "https://www.edaily.co.kr/rss/rss.asp?code=newsRss",
    ],
    "sports": [
        "https://www.yna.co.kr/rss/sports.xml",
        "https://news.kbs.co.kr/rss/rss_sports.xml",
        "https://www.sportschosun.com/rss/sports.xml",
        "https://www.donga.com/sports/rss",
        "https://www.spotvnews.co.kr/rss/S1N2.xml",
        "https://feeds.bbci.co.uk/sport/rss.xml",
        "https://www.espn.com/espn/rss/news",
    ],
    "culture": [
        "https://www.yna.co.kr/rss/culture.xml",
        "https://news.kbs.co.kr/rss/rss_culture.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=culture",
    ],
    "politics": [
        "https://www.yna.co.kr/rss/politics.xml",
        "https://news.kbs.co.kr/rss/rss_politics.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=politics",
        "https://www.hani.co.kr/rss/politics.xml",
        "https://rss.donga.com/politics.xml",
    ],
    "science": [
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://www.yna.co.kr/rss/science.xml",
        "https://feeds.nature.com/nature/rss/current",      # Nature (해외 최고 과학)
        "https://www.science.org/rss/news_current.xml",     # Science (해외) 
        "https://www.nasa.gov/rss/dyn/breaking_news.rss", # NASA
    ],
    "health": [
        "https://www.yna.co.kr/rss/health.xml",
        "https://health.chosun.com/site/data/rss/rss.xml",
        "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=08&plink=RSSREADER",
        "https://kormedi.com/feed/",
    ],
    "world": [
    "https://www.yna.co.kr/rss/international.xml",
    "https://news.kbs.co.kr/rss/rss_world.xml",
    "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=international",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
],
    "society": [
        "https://www.yna.co.kr/rss/society.xml",
        "https://news.kbs.co.kr/rss/rss_society.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=society",
        "https://www.hani.co.kr/rss/society.xml",
    ],
    "entertain": [
        "https://www.yna.co.kr/rss/entertainment.xml",
        "https://api.sbs.co.kr/xml/news/rss.jsp?pmDiv=entertainment",
        "https://www.sportschosun.com/rss/entertain.xml",
        "https://tenasia.hankyung.com/feed",
    ],
}

# 카테고리별 NewsAPI 검색 키워드
NEWS_API_KEYWORDS = {
    "ai":        "AI OR 인공지능 OR ChatGPT OR 반도체 OR 스타트업 OR 클라우드 OR 빅데이터 OR 사이버보안 OR 메타버스 OR 전기차",
    "economy":   "경제 OR 주식 OR 금리 OR 부동산 OR 가상화폐 OR 환율 OR 코스피 OR 코스닥 OR 무역 OR 기업 OR 취업 OR 고용",
    "sports":    "스포츠 OR 축구 OR 야구 OR 농구 OR 골프 OR 배드민턴 OR 테니스 OR 배구 OR 수영 OR 태권도 OR e스포츠 OR UFC OR F1",
    "culture":   "문화 OR 영화 OR 음악 OR 공연 OR 전시 OR 도서 OR 여행 OR 맛집 OR 패션 OR 게임 OR 미술",
    "politics":  "정치 OR 국회 OR 정부 OR 대통령 OR 선거 OR 외교 OR 북한 OR 정책 OR 여당 OR 야당 OR 검찰 OR 사법",
    "science":   "과학 OR 우주 OR 연구 OR 생명과학 OR 물리 OR 화학 OR 로봇 OR 에너지 OR 기후 OR NASA OR 신소재",
    "health":    "건강 OR 의료 OR 병원 OR 질병 OR 다이어트 OR 운동 OR 정신건강 OR 뷰티 OR 영양 OR 제약 OR 바이오",
    "world":     "국제 OR 해외 OR 미국 OR 중국 OR 일본 OR 유럽 OR 중동 OR 러시아 OR 아시아 OR 외교 OR 전쟁",
    "society":   "사회 OR 사건 OR 사고 OR 교육 OR 복지 OR 노동 OR 인권 OR 재난 OR 환경 OR 미디어 OR 종교",
    "entertain": "연예 OR 드라마 OR 아이돌 OR K-POP OR 영화 OR 예능 OR 배우 OR 가수 OR 넷플릭스 OR 할리우드",
}

# 세부 카테고리 자동 태깅 규칙
SUB_TOPIC_TAGS = {
    # 스포츠
    "football":    ["축구", "손흥민", "월드컵", "K리그", "프리미어리그", "FA컵", "UEFA", "FIFA", "메시", "호날두", "챔피언스리그", "이강인", "황희찬", "김민재", "분데스리가", "라리가", "세리에A", "리그앙", "에레디비지에", "대한축구협회", "국가대표", "A매치", "아시안컵", "AFC", "클럽월드컵", "수페르코파", "코파델레이", "DFB포칼", "맨체스터", "레알마드리드", "바르셀로나", "바이에른", "PSG", "첼시", "아스날", "리버풀", "토트넘"],
    "baseball":    ["야구", "KBO", "MLB", "류현진", "오타니", "홈런", "한국시리즈", "이정후", "김하성", "고우석", "SSG", "LG트윈스", "두산", "롯데", "NC", "KT", "한화", "삼성라이온즈", "기아타이거즈", "월드시리즈", "포스트시즌", "올스타", "사이영상", "MVP야구"],
    "basketball":  ["농구", "NBA", "KBL", "르브론", "커리", "NBA파이널", "야니스", "듀란트", "조던", "코비", "NBA드래프트", "오클라호마", "골든스테이트", "LA레이커스", "보스턴셀틱스", "삼대삼"],
    "golf":        ["골프", "PGA", "LPGA", "마스터스", "골프대회", "임성재", "김주형", "고진영", "박성현", "US오픈골프", "브리티시오픈", "더CJ컵", "THE PLAYERS", "라이더컵", "프레지던츠컵"],
    "esports":     ["e스포츠", "롤", "리그오브레전드", "오버워치", "LCK", "게임대회", "페이커", "T1", "젠지", "담원", "KT롤스터", "배틀그라운드", "발로란트", "LOL월드챔피언십", "MSI", "롤드컵"],
    "volleyball":  ["배구", "V리그", "배구대회", "김연경", "이다영", "박정아", "흥국생명", "현대건설", "세계배구선수권"],
    "badminton":   ["배드민턴", "안세영", "BWF", "배드민턴대회", "김가은", "서승재", "채유정", "전영오픈", "코리아오픈배드민턴"],
    "tabletennis": ["탁구", "신유빈", "WTT", "탁구대회", "장우진", "이상수", "전지희", "세계탁구선수권"],
    "taekwondo":   ["태권도", "세계태권도", "국기원", "태권도대회", "올림픽태권도", "세계선수권태권도"],
    "judo":        ["유도", "유도대회", "IJF", "안바울", "허미미", "이준환", "세계유도선수권"],
    "boxing":      ["복싱", "WBC", "WBA", "IBF", "복싱챔피언", "최현미", "세계챔피언권투"],
    "mma":         ["UFC", "종합격투기", "코리안좀비", "벨라토르", "MMA", "정찬성", "최두호", "김동현", "ONE챔피언십"],
    "tennis":      ["테니스", "ATP", "WTA", "윔블던", "롤랑가로스", "호주오픈", "테니스대회", "정현", "권순우", "나달", "조코비치", "알카라스", "이가스비아텍", "US오픈테니스"],
    "motorsports": ["F1", "모터스포츠", "포뮬러", "NASCAR", "르망", "페레스", "해밀턴", "페르스타펜", "GP", "그랑프리", "모나코GP"],
    "handball":    ["핸드볼", "IHF", "핸드볼대회", "세계핸드볼선수권"],
    "ssireum":     ["씨름", "천하장사", "씨름대회", "전국씨름대회"],
    "swimming":    ["수영", "박태환", "FINA", "수영대회", "황선우", "김우민", "세계수영선수권", "자유형", "평영", "접영"],
    "fencing":     ["펜싱", "오상욱", "FIE", "펜싱대회", "구본길", "김정환", "세계펜싱선수권"],
    "archery":     ["양궁", "김우진", "세계양궁", "양궁대회", "안산", "세계양궁선수권", "올림픽양궁"],

    # 경제
    "stock":       ["주식", "코스피", "코스닥", "증시", "상장", "IPO", "주가", "ETF", "펀드", "배당", "공매도", "선물", "옵션", "증권사", "삼성전자주가", "코스피지수"],
    "realestate":  ["부동산", "아파트", "청약", "전세", "매매", "집값", "재건축", "재개발", "분양", "전월세", "임대차", "오피스텔", "빌라", "토지"],
    "crypto":      ["비트코인", "코인", "가상화폐", "이더리움", "NFT", "암호화폐", "리플", "도지코인", "업비트", "빗썸", "코인베이스", "바이낸스", "블록체인"],
    "finance":     ["금리", "금융", "은행", "대출", "이자", "한국은행", "기준금리", "예금", "적금", "보험", "카드", "핀테크", "인터넷은행", "카카오뱅크", "토스"],
    "trade":       ["무역", "수출", "수입", "관세", "FTA", "무역수지", "무역적자", "반도체수출", "대미무역", "대중무역", "통상"],
    "company":     ["기업", "삼성", "현대", "SK", "LG", "상장사", "대기업", "중소기업", "포스코", "롯데", "한화", "GS", "CJ", "카카오", "네이버", "기업실적", "영업이익", "매출"],
    "exchange":    ["환율", "달러", "원화", "외환", "환전", "엔달러", "위안화", "유로", "원달러", "환헤지"],
    "employment":  ["취업", "고용", "실업", "채용", "일자리", "노동시장", "청년실업", "구직", "이직", "연봉", "최저임금", "비정규직"],

    # IT/기술
    "llm":         ["ChatGPT", "LLM", "생성AI", "GPT", "클로드", "제미나이", "AI모델", "대규모언어모델", "오픈AI", "앤트로픽", "구글AI", "메타AI", "라마", "소라", "AI규제", "딥시크"],
    "semiconductor": ["반도체", "엔비디아", "AI칩", "HBM", "파운드리", "반도체산업", "SK하이닉스", "TSMC", "인텔", "AMD", "삼성파운드리", "시스템반도체", "메모리반도체"],
    "mobile":      ["스마트폰", "아이폰", "갤럭시", "앱", "모바일", "태블릿", "iOS", "안드로이드", "갤럭시S", "폴더블", "웨어러블"],
    "security":    ["보안", "해킹", "사이버", "랜섬웨어", "개인정보", "보안사고", "피싱", "개인정보유출", "DDoS", "보안패치", "제로데이"],
    "startup":     ["스타트업", "창업", "벤처", "유니콘", "투자유치", "시리즈A", "시리즈B", "액셀러레이터", "VC", "투자라운드"],
    "cloud":       ["클라우드", "AWS", "Azure", "구글클라우드", "SaaS", "서버리스", "쿠버네티스", "도커", "마이크로서비스"],
    "internet":    ["인터넷", "SNS", "유튜브", "인스타그램", "틱톡", "카카오", "네이버", "유튜버", "인플루언서", "숏폼", "릴스", "트위터", "X", "스레드"],
    "ev":          ["전기차", "테슬라", "전기자동차", "EV", "자율주행", "현대아이오닉", "기아EV", "전기차보조금", "충전인프라", "배터리팩"],
    "game_tech":   ["게임", "메타버스", "VR", "AR", "가상현실", "로블록스", "제페토", "유니티", "언리얼", "NFT게임"],

    # 정치
    "domestic":    ["국회", "대통령", "정부", "여당", "야당", "총선", "대선", "이재명", "한동훈", "국민의힘", "민주당", "국무총리", "청와대", "용산"],
    "election":    ["선거", "투표", "후보", "당선", "선거운동", "공천", "비례대표", "지역구", "사전투표", "개표", "여론조사", "지지율"],
    "northkorea":  ["북한", "김정은", "평양", "비핵화", "남북", "핵실험", "미사일", "탈북", "대북제재", "남북회담", "통일"],
    "foreign":     ["외교", "정상회담", "대사관", "외무", "외교부", "한미동맹", "한일관계", "한중관계", "G7", "G20", "UN", "외교장관"],
    "policy":      ["정책", "법안", "규제", "입법", "정부정책", "예산안", "세금", "복지정책", "교육정책", "부동산정책"],
    "judiciary":   ["검찰", "법원", "재판", "판결", "사법", "대법원", "헌법재판소", "검사", "기소", "구속영장", "수사", "항소"],

    # 건강
    "disease":     ["질병", "암", "당뇨", "고혈압", "코로나", "독감", "감염", "심장병", "뇌졸중", "폐암", "유방암", "위암", "치매", "파킨슨"],
    "medical":     ["의료", "병원", "의사", "수술", "치료", "의약품", "국민건강보험", "의료비", "한의원", "응급실", "의대정원", "간호사"],
    "fitness":     ["운동", "헬스", "트레이닝", "근육", "피트니스", "필라테스", "요가", "크로스핏", "마라톤", "홈트", "PT"],
    "diet":        ["다이어트", "체중", "식단", "칼로리", "영양식", "간헐적단식", "저탄고지", "단백질", "채식", "비건"],
    "mental":      ["정신건강", "우울", "스트레스", "불안", "심리", "번아웃", "공황장애", "ADHD", "자존감", "상담", "심리치료"],
    "beauty":      ["뷰티", "화장품", "피부", "성형", "미용", "스킨케어", "메이크업", "시술", "보톡스", "필러", "K뷰티"],
    "nutrition":   ["영양", "비타민", "건강식품", "식이요법", "영양제", "오메가3", "프로바이오틱스", "마그네슘", "루테인", "콜라겐"],
    "pharma":      ["제약", "바이오", "신약", "임상시험", "제약회사", "식약처", "허가", "복제약", "바이오시밀러", "임상3상", "항암제"],

    # 문화
    "movie":       ["영화", "박스오피스", "개봉", "감독", "영화제", "칸영화제", "아카데미", "부산국제영화제", "넷플릭스영화", "디즈니", "마블"],
    "music":       ["음악", "앨범", "콘서트", "공연", "뮤지션", "그래미", "빌보드", "스포티파이", "뮤직비디오"],
    "art":         ["미술", "전시", "갤러리", "작품", "아트", "경매", "설치미술", "현대미술", "아트페어"],
    "book":        ["책", "도서", "출판", "베스트셀러", "작가", "소설", "시집", "에세이", "만화", "웹소설"],
    "travel":      ["여행", "관광", "해외여행", "국내여행", "여행지", "유럽여행", "일본여행", "동남아여행", "제주도", "강릉"],
    "food":        ["음식", "맛집", "레스토랑", "요리", "먹방", "한식", "일식", "중식", "카페", "디저트", "배달"],
    "fashion":     ["패션", "의류", "브랜드", "트렌드", "스타일", "명품", "하이패션", "스트릿패션", "패션위크"],
    "game":        ["게임", "플레이스테이션", "닌텐도", "Xbox", "PC게임", "스팀", "PS5", "닌텐도스위치", "모바일게임", "게임출시"],
    "performance": ["공연", "뮤지컬", "연극", "오페라", "콘서트홀", "내한공연", "뮤지컬티켓", "클래식", "발레"],

    # 연예
    "kpop":        ["K-POP", "아이돌", "BTS", "블랙핑크", "뉴진스", "케이팝", "에스파", "아이브", "르세라핌", "세븐틴", "스트레이키즈", "NCT", "엑소", "방탄"],
    "drama":       ["드라마", "넷플릭스", "OTT", "시즌", "드라마시청률", "tvN", "JTBC", "MBC드라마", "KBS드라마", "웨이브", "왓챠"],
    "variety":     ["예능", "유재석", "런닝맨", "무한도전", "버라이어티", "놀면뭐하니", "나혼자산다", "전현무", "신동엽", "강호동"],
    "actor":       ["배우", "주연", "조연", "청룡영화상", "백상예술대상", "송혜교", "이병헌", "공유", "김수현", "전도연", "황정민", "유해진"],
    "kmusic":      ["가요", "발라드", "트로트", "힙합", "멜론차트", "임영웅", "아이유", "이찬원", "나훈아", "뮤직차트", "가온차트"],
    "overseas":    ["할리우드", "빌보드", "그래미", "오스카", "해외연예", "테일러스위프트", "비욘세", "아리아나그란데", "일본연예"],

    # 과학
    "space":       ["우주", "NASA", "로켓", "위성", "블랙홀", "우주탐사", "스페이스X", "아르테미스", "화성탐사", "제임스웹", "누리호", "달탐사"],
    "environment": ["환경", "기후", "탄소", "온실가스", "기후변화", "미세먼지", "산불", "해수면상승", "탄소중립", "RE100", "녹색에너지"],
    "biology":     ["생물", "유전자", "DNA", "줄기세포", "생명과학", "CRISPR", "유전자편집", "단백질", "세포치료"],
    "physics":     ["물리", "화학", "입자", "양자", "핵융합", "레이저", "초전도", "나노", "플라즈마"],
    "medicine":    ["의학", "바이오", "신약개발", "임상", "의료기술", "면역치료", "유전자치료", "로봇수술", "AI진단", "원격의료"],
    "math":        ["수학", "통계", "알고리즘", "데이터", "빅데이터", "머신러닝", "딥러닝", "확률", "최적화"],
    "robot":       ["로봇", "기계", "자동화", "드론", "로보틱스", "산업로봇", "휴머노이드", "보스턴다이나믹스", "자동화공장"],
    "energy":      ["에너지", "신소재", "태양광", "배터리", "수소", "원자력", "풍력", "리튬", "전고체배터리", "그래핀"],

    # 사회
    "education":   ["교육", "학교", "대학", "수능", "입시", "학원", "사교육", "대입", "교원", "학폭", "급식"],
    "crime":       ["사건", "사고", "범죄", "경찰", "검거", "살인", "강도", "사기", "음주운전", "마약", "성범죄", "사이버범죄"],
    "welfare":     ["복지", "연금", "기초생활", "노인", "사회복지", "기초연금", "장애인", "한부모", "아동복지", "돌봄"],
    "labor":       ["노동", "파업", "임금", "근로", "노조", "최저임금인상", "주4일제", "육아휴직", "직장갑질", "산재"],
    "disaster":    ["재난", "재해", "지진", "홍수", "화재", "태풍", "폭설", "가뭄", "폭염", "산사태", "침수"],
    "human_rights":["인권", "차별", "평등", "젠더", "소수자", "성평등", "LGBTQ", "이주민", "난민", "여성폭력", "아동인권"],
    "media":       ["미디어", "언론", "방송", "신문", "뉴스", "가짜뉴스", "유튜브뉴스", "팟캐스트"],
    "religion":    ["종교", "교회", "불교", "이슬람", "종교단체", "가톨릭", "개신교", "원불교", "종교갈등"],
    "local":       ["지역", "지방", "커뮤니티", "지자체", "지역사회", "서울시", "경기도", "부산시", "인천", "대구", "광주", "지방소멸"],

    # 국제
    "us":          ["미국", "바이든", "트럼프", "워싱턴", "백악관", "미국정부", "미국대선", "의회", "연준", "FED", "주한미군"],
    "china":       ["중국", "시진핑", "베이징", "홍콩", "대만", "중국경제", "미중갈등", "중국군", "중국공산당"],
    "japan":       ["일본", "도쿄", "엔화", "일본정부", "일본경제", "엔저", "자민당", "독도", "한일관계"],
    "europe":      ["유럽", "EU", "독일", "프랑스", "영국", "NATO", "우크라이나전쟁", "유럽의회", "ECB", "유로존"],
    "middleeast":  ["중동", "이란", "이스라엘", "사우디", "팔레스타인", "가자지구", "하마스", "원유", "OPEC", "아랍에미리트"],
    "asia":        ["아시아", "동남아", "인도", "태국", "베트남", "북핵", "대만해협", "인도경제", "아세안", "필리핀", "인도네시아"],
    "russia":      ["러시아", "푸틴", "모스크바", "우크라이나", "러시아전쟁", "나토러시아", "에너지제재"],
    "world_economy": ["국제경제", "세계경제", "IMF", "WTO", "글로벌", "달러패권", "BRICS", "공급망", "인플레이션"],
    "world_affairs": ["국제정세", "외교안보", "분쟁", "전쟁", "국제관계", "핵전쟁", "테러", "난민위기", "UN안보리"],
}

def clean_html(text: str) -> str:
    """HTML 태그 제거 후 순수 텍스트 반환"""
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)

def _get_sub_tags(title: str, content: str) -> list:
    """제목 + 내용 기반으로 세부 태그 자동 추출"""
    text = (title + " " + (content or ""))[:500]
    matched = []
    for tag, keywords in SUB_TOPIC_TAGS.items():
        for kw in keywords:
            if kw in text:
                matched.append(tag)
                break
    return matched

def fetch_by_rss(topic: str) -> list:
    """RSS 피드로 기사 수집 (카테고리당 여러 RSS)"""
    feed_urls = RSS_FEEDS.get(topic, [])
    if not feed_urls:
        return []

    headers = {"User-Agent": "Mozilla/5.0 (compatible; CurioBot/1.0)"}
    articles = []

    for feed_url in feed_urls:
        try:
            response = httpx.get(
                feed_url,
                headers=headers,
                timeout=10,
                follow_redirects=True
            )
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                # 썸네일 추출 ← 여기에 추가
                thumbnail = None
                if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                    thumbnail = entry.media_thumbnail[0].get("url", None)
                elif hasattr(entry, "media_content") and entry.media_content:
                    thumbnail = entry.media_content[0].get("url", None)
                    
                articles.append({
                    "title": clean_html(entry.get("title", "")), 
                    "content": clean_html(entry.get("summary", "")),
                    "original_url": entry.get("link", ""),
                    "source_name": feed.feed.get("title", ""),
                    "topic": topic,
                    "published_at": _parse_date(entry.get("published", "")),
                    "thumbnail_url": thumbnail,
                })
        except Exception as e:
            logger.warning(f"RSS 수집 실패 ({feed_url}): {e}")
            continue

    return articles


async def fetch_by_newsapi(topic: str) -> list:
    """NewsAPI로 기사 수집 (하루 100건 제한 주의)"""
    keyword = NEWS_API_KEYWORDS.get(topic, topic)
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": keyword,
        "language": "ko",
        "sortBy": "publishedAt",
        "apiKey": NEWS_API_KEY,
        "pageSize": 10,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return []

        data = response.json()
        articles = []

        for item in data.get("articles", []):
            articles.append({
                "title": clean_html(item.get("title", "")),   
                "content": clean_html(item.get("content") or item.get("description", "")),
                "original_url": item.get("url", ""),
                "source_name": item.get("source", {}).get("name", ""),
                "topic": topic,
                "published_at": _parse_date(item.get("publishedAt", "")),
                "thumbnail_url": item.get("urlToImage", None),
            })

        return articles


def save_articles_to_db(articles: list, db: Session) -> int:
    """수집된 기사를 DB에 저장 — 중복 방지 (original_url UNIQUE)"""
    saved_count = 0
    seen_urls = set()

    for item in articles:
        if not item.get("original_url") or not item.get("title"):
            continue

        url = item["original_url"]
        if url in seen_urls:  # ← 추가
            continue
        seen_urls.add(url)  # ← 추가

        exists = db.query(Article).filter(
            Article.original_url == item["original_url"]
        ).first()

        if exists:
            continue

        # 세부 태그 자동 추출
        sub_tags = _get_sub_tags(item["title"], item.get("content", ""))
        tags = [item.get("topic", "")] + sub_tags

        article = Article(
            id=str(uuid.uuid4()),
            title=item["title"],
            content=item.get("content", ""),
            source_name=item.get("source_name", ""),
            original_url=item["original_url"],
            topic=item.get("topic", ""),
            tags=tags,
            relevance_score=0.5,
            published_at=item.get("published_at"),
            thumbnail_url=item.get("thumbnail_url", None),
        )
        db.add(article)
        saved_count += 1

    db.commit()
    return saved_count


def _parse_date(date_str: str):
    """날짜 문자열을 datetime으로 변환"""
    if not date_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None