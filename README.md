# PropLens

> AI 기반 부동산 매물 **자동** 검색 및 분석 시스템  
> Rule-based + LLM Hybrid Real Estate Analyzer

## 프로젝트 개요

공인중개사 방문 전, 매물을 **자동으로** 수집하고 분석하는 도구입니다.

### 핵심 기능

1. **자동 매물 수집** - 네이버 부동산에서 조건에 맞는 매물 자동 크롤링
2. **실거래가 검증** - 국토부 실거래가 API로 시세 대비 가격 분석
3. **조건 필터링** - 예산, 면적, 세대수 등 조건 기반 자동 필터링
4. **리스크 분석** - 매물 설명에서 위험 신호 자동 탐지
5. **질문 생성** - 중개사에게 물어볼 질문 자동 생성
6. **리포트 출력** - 추천 매물 순위 및 상세 분석 리포트

## 핵심 원칙

1. **LLM은 보조 엔진** - 판단/필터/점수는 규칙 기반 코드로
2. **llama.cpp (GGUF) 내장형 배포** - 외부 유료 API 의존 금지
3. **자동화 우선** - 수동 입력 최소화, 크롤링 기반 데이터 수집
4. **설명 가능한 결과** - 왜 탈락/추천인지 근거 필수

## 데이터 소스

| 소스 | 용도 | API |
|------|------|-----|
| 네이버 부동산 | 매물 정보 수집 | 내부 API (크롤링) |
| 국토부 실거래가 | 시세 검증 | 공공데이터포털 API |

## 폴더 구조

```
PropLens/
├── app/
│   ├── api/              # FastAPI 엔드포인트
│   ├── pipeline/         # Agent 오케스트레이션
│   ├── domain/           # 규칙 기반 로직 (필터/점수/리스크)
│   ├── agents/           # 개별 Agent
│   │   ├── search_agent.py    # 매물 자동 검색
│   │   ├── enrich_agent.py    # 실거래가 보강
│   │   ├── filter_agent.py    # 조건 필터링
│   │   ├── score_agent.py     # 점수화
│   │   ├── risk_agent.py      # 리스크 분석
│   │   ├── question_agent.py  # 질문 생성
│   │   └── report_agent.py    # 리포트 생성
│   ├── data_sources/     # 외부 데이터 수집
│   │   ├── naver_land.py      # 네이버 부동산 API
│   │   ├── molit_api.py       # 국토부 실거래가 API
│   │   └── region_codes.py    # 지역 코드 관리
│   ├── llm/              # llama.cpp 래퍼 + 프롬프트
│   └── schemas/          # Pydantic 모델
├── models/               # GGUF 모델 파일
├── data/                 # 샘플/테스트 데이터
├── tests/                # 테스트 코드
├── ui/                   # Streamlit UI
└── docs/                 # 설계 문서
```

## 설치 및 실행

```bash
# 가상환경 생성
python -m venv venv
venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 설정 (선택)

# UI 실행
streamlit run ui/app.py

# 또는 API 서버 실행
uvicorn app.api.main:app --reload
```

## 사용 방법

### 1. UI 사용

```bash
streamlit run ui/app.py
```

1. 사이드바에서 검색 조건 설정 (지역, 예산, 면적 등)
2. "자동 검색 시작" 클릭
3. 결과 확인 및 추천 매물 상세 분석

### 2. API 사용

```python
import httpx

response = httpx.post("http://localhost:8000/api/v1/search", json={
    "user_input": {
        "transaction_type": "전세",
        "max_deposit": 45000,
        "regions": ["강서구", "양천구"],
        "min_area_sqm": 84.0,
        "min_households": 1000,
    },
    "max_items_per_region": 30,
})

report = response.json()
print(f"추천 매물: {len(report['top_recommendations'])}개")
```

## 파이프라인 구조

```
UserInput (검색 조건)
    ↓
┌─────────────────┐
│  SearchAgent    │ ← 네이버 부동산 API
│  (자동 수집)    │
└────────┬────────┘
         ↓
┌─────────────────┐
│  EnrichAgent    │ ← 국토부 실거래가 API
│  (데이터 보강)  │
└────────┬────────┘
         ↓
┌─────────────────┐
│  FilterAgent    │ ← 규칙 기반 (코드)
│  (조건 필터링)  │
└────────┬────────┘
         ↓
┌─────────────────┐
│  ScoreAgent     │ ← 규칙 기반 (코드)
│  (점수화)       │
└────────┬────────┘
         ↓
┌─────────────────┐
│  RiskAgent      │ ← 규칙 + LLM
│  (리스크 분석)  │
└────────┬────────┘
         ↓
┌─────────────────┐
│  QuestionAgent  │ ← 규칙 + LLM
│  (질문 생성)    │
└────────┬────────┘
         ↓
┌─────────────────┐
│  ReportAgent    │
│  (리포트 생성)  │
└────────┬────────┘
         ↓
     Report (결과)
```

## API 키 설정 (선택)

국토부 실거래가 데이터를 사용하려면:

1. [공공데이터포털](https://www.data.go.kr) 회원가입
2. "국토교통부_아파트 전월세 실거래가" API 활용 신청
3. 발급받은 API 키를 `.env` 파일에 설정:

```
DATA_GO_KR_API_KEY=your_api_key_here
```

## 주의사항

- 네이버 부동산 API는 과도한 요청 시 차단될 수 있습니다
- 적절한 딜레이(1-2초)가 자동으로 적용됩니다
- 상업적 용도 사용 시 법적 검토가 필요합니다

## 라이선스

MIT License
