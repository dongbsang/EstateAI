# PropLens 기술 상세 문서

> 프로젝트 실행 흐름, 파일 구조, 메서드 상세

## 목차

1. [실행 흐름](#1-실행-흐름)
2. [디렉토리 구조](#2-디렉토리-구조)
3. [핵심 스키마](#3-핵심-스키마)
4. [Agent 상세](#4-agent-상세)
5. [Data Source 상세](#5-data-source-상세)
6. [Domain 로직](#6-domain-로직)
7. [UI 구조](#7-ui-구조)

---

## 1. 실행 흐름

### 1.1 진입점

```
ui/app.py::main()
    │
    ├─ Streamlit UI 렌더링
    │
    └─ "검색 시작" 버튼 클릭
        │
        └─ run_analysis() 호출
            │
            ├─ load_dotenv()  # .env 환경변수 로드
            │
            ├─ UserInput 생성
            │
            └─ PipelineOrchestrator.run()
```

### 1.2 파이프라인 실행 순서

```python
# app/pipeline/orchestrator.py::PipelineOrchestrator.run()

def run(self, user_input: UserInput) -> Report:
    
    # Step 1: 매물 검색
    listings = self.search_agent.run(user_input)
    # → NaverLandClient.search_by_region()
    
    # Step 2: 데이터 보강 (실거래가)
    listings = self.enrich_agent.run(EnrichInput(listings, user_input))
    # → MolitRealPriceClient.get_complex_price_analysis()
    
    # Step 3: 데이터 정규화
    for listing in listings:
        listing = self.normalize_agent.run(listing)
    
    # Step 4: 1차 필터링 (기본 조건)
    for listing in listings:
        result = self.filter_agent.run(FilterInput(listing, user_input))
        # → FilterEngine.filter()
    
    # Step 5: 통근 시간 계산 (필터 통과 매물만)
    if user_input.commute_destination:
        commute_results = self.commute_agent.run(CommuteInput(...))
        # → ODsayClient.get_commute_time()
    
    # Step 6: 점수화
    for listing in passed_listings:
        score = self.score_agent.run(ScoreInput(listing, user_input))
        # → ScoreEngine.score()
    
    # Step 7: 리스크 분석
    for listing in listings:
        risk = self.risk_agent.run(listing)
        # → RiskEngine.analyze()
    
    # Step 8: 질문 생성
    for listing in listings:
        questions = self.question_agent.run(QuestionInput(listing, risk))
        # → QuestionEngine.generate()
    
    # Step 9: 리포트 생성
    report = self.report_agent.run(ReportInput(...))
    
    return report
```

---

## 2. 디렉토리 구조

```
D:\03_AI\EstateAI\
│
├── .env                    # 환경변수 (API 키)
├── .env.example            # 환경변수 예시
├── requirements.txt        # Python 의존성
├── README.md               # 프로젝트 개요
├── README_DETAIL.md        # 기술 상세
│
├── ui/
│   └── app.py              # Streamlit 메인 UI
│
├── app/
│   ├── __init__.py
│   │
│   ├── schemas/            # Pydantic 데이터 모델
│   │   ├── __init__.py
│   │   ├── user_input.py   # UserInput - 사용자 입력
│   │   ├── listing.py      # Listing - 매물 정보
│   │   └── results.py      # FilterResult, RiskResult, Report 등
│   │
│   ├── data_sources/       # 외부 API 클라이언트
│   │   ├── __init__.py
│   │   ├── naver_land.py   # 네이버 부동산 크롤러
│   │   ├── molit_api.py    # 국토부 실거래가 API
│   │   ├── odsay_api.py    # ODsay 대중교통 API
│   │   ├── region_codes.py # 지역 코드 관리
│   │   └── cache_manager.py # 캐시 관리
│   │
│   ├── agents/             # Agent 구현
│   │   ├── __init__.py
│   │   ├── base.py         # BaseAgent 추상 클래스
│   │   ├── search_agent.py # 매물 검색
│   │   ├── enrich_agent.py # 데이터 보강
│   │   ├── commute_agent.py # 통근 시간
│   │   ├── normalize_agent.py # 정규화
│   │   ├── filter_agent.py # 필터링
│   │   ├── score_agent.py  # 점수화
│   │   ├── risk_agent.py   # 리스크 분석
│   │   ├── question_agent.py # 질문 생성
│   │   └── report_agent.py # 리포트 생성
│   │
│   ├── domain/             # 비즈니스 로직 (규칙 기반)
│   │   ├── __init__.py
│   │   ├── filters.py      # FilterEngine
│   │   ├── scoring.py      # ScoreEngine
│   │   ├── risk_rules.py   # RiskEngine
│   │   └── questions.py    # QuestionEngine
│   │
│   ├── pipeline/           # 오케스트레이션
│   │   ├── __init__.py
│   │   └── orchestrator.py # PipelineOrchestrator
│   │
│   └── llm/                # LLM 관련 (향후 확장)
│       └── __init__.py
│
├── data/                   # 데이터 디렉토리
│   └── cache/              # API 응답 캐시
│
├── models/                 # GGUF 모델 (향후)
│
└── tests/                  # 테스트 코드
```

---

## 3. 핵심 스키마

### 3.1 UserInput (`app/schemas/user_input.py`)
사용자가 입력하는 검색 조건

```python
class UserInput(BaseModel):
    # 거래 조건
    transaction_type: TransactionType = "전세"  # 전세/월세/매매
    
    # 예산
    max_deposit: Optional[int]          # 최대 보증금 (만원)
    max_monthly_rent: Optional[int]     # 최대 월세 (만원)
    
    # 위치
    regions: list[str]                  # 지역 ["강서구", "양천구"]
    commute_destination: Optional[str]  # 출퇴근 목적지 "여의도역"
    max_commute_minutes: Optional[int]  # 최대 통근 시간 (분)
    
    # 주택 조건
    property_types: list[PropertyType]  # ["아파트"]
    min_area_sqm: Optional[float]       # 최소 전용면적 (㎡)
    min_households: Optional[int]       # 최소 세대수
    
    # 필수 조건 지정
    must_conditions: list[str]          # ["max_deposit", "min_area_sqm"]
```

### 3.2 Listing (`app/schemas/listing.py`)

파싱된 매물 정보

```python
class Listing(BaseModel):
    # 식별
    id: str                     # "naver_2412345678"
    source: ListingSource       # NAVER, CSV 등
    url: Optional[HttpUrl]
    
    # 기본 정보
    title: Optional[str]        # "래미안목동아델리체"
    address: Optional[str]
    region_gu: Optional[str]    # "양천구"
    region_dong: Optional[str]  # "목동"
    
    # 거래 정보
    transaction_type: Optional[str]  # "전세"
    deposit: Optional[int]           # 45000 (만원)
    monthly_rent: Optional[int]      # 0
    
    # 면적
    area_sqm: Optional[float]   # 84.98
    area_pyeong: Optional[float] # 25.7
    
    # 단지 정보
    complex_name: Optional[str]
    households: Optional[int]   # 1500
    built_year: Optional[int]   # 2020
    
    # 위치
    latitude: Optional[float]
    longitude: Optional[float]
    
    # 설명 (리스크 분석용)
    description: Optional[str]
```

### 3.3 주요 Result 스키마 (`app/schemas/results.py`)

```python
class FilterResult(BaseModel):
    listing_id: str
    status: FilterStatus        # PASS, FAIL, PARTIAL
    passed_conditions: list[str]
    failed_conditions: list[str]
    failure_reasons: dict[str, str]  # {"max_deposit": "보증금 5억 > 상한 4.5억"}

class RiskResult(BaseModel):
    listing_id: str
    risk_score: int             # 0-100
    risks: list[RiskItem]
    summary: str

class Report(BaseModel):
    created_at: datetime
    total_count: int
    passed_count: int
    top_recommendations: list[ListingReport]
    filtered_out: list[ListingReport]
    summary: str
    insights: list[str]
```

---

## 4. Agent 상세

### 4.1 BaseAgent (`app/agents/base.py`)

모든 Agent의 부모 클래스

```python
class BaseAgent(Generic[TInput, TOutput]):
    name: str = "BaseAgent"
    
    def run(self, input_data: TInput) -> TOutput:
        """외부 호출 인터페이스"""
        self.logger.info(f"Running {self.name}")
        return self._process(input_data)
    
    def _process(self, input_data: TInput) -> TOutput:
        """실제 처리 로직 (서브클래스에서 구현)"""
        raise NotImplementedError
```

### 4.2 SearchAgent (`app/agents/search_agent.py`)

```python
class SearchAgent(BaseAgent[UserInput, list[Listing]]):
    """네이버 부동산에서 매물 자동 검색"""
    
    def _process(self, user_input: UserInput) -> list[Listing]:
        # 1. 지역 코드 변환
        region_codes = self._get_region_codes(user_input)
        # ["11500", "11470"]  # 강서구, 양천구
        
        # 2. 각 지역별 검색
        with NaverLandClient() as client:
            for code in region_codes:
                listings = client.search_by_region(
                    region_code=code,
                    user_input=user_input,
                    max_items=50
                )
        
        # 3. 중복 제거 후 반환
        return unique_listings
```

### 4.3 EnrichAgent (`app/agents/enrich_agent.py`)

```python
class EnrichAgent(BaseAgent[EnrichInput, list[Listing]]):
    """실거래가 + 전세가율 분석"""
    
    def _process(self, input_data: EnrichInput) -> list[Listing]:
        with MolitRealPriceClient() as client:
            for listing in input_data.listings:
                # 가격 분석 추가
                analysis = client.get_complex_price_analysis(
                    sigungu_code=sigungu_code,
                    complex_name=listing.complex_name,
                    area_sqm=listing.area_sqm,
                    current_deposit=listing.deposit
                )
                # listing.description에 분석 결과 추가
```

### 4.4 FilterAgent (`app/agents/filter_agent.py`)

```python
class FilterAgent(BaseAgent[FilterInput, FilterResult]):
    """규칙 기반 필터링 - LLM 사용 안함"""
    
    def __init__(self):
        self.engine = FilterEngine()
    
    def _process(self, input_data: FilterInput) -> FilterResult:
        return self.engine.filter(
            listing=input_data.listing,
            user_input=input_data.user_input
        )
```

### 4.5 RiskAgent (`app/agents/risk_agent.py`)

```python
class RiskAgent(BaseAgent[Listing, RiskResult]):
    """리스크 패턴 탐지"""
    
    def __init__(self):
        self.engine = RiskEngine()
    
    def _process(self, listing: Listing) -> RiskResult:
        return self.engine.analyze(listing)
```

---

## 5. Data Source 상세

### 5.1 NaverLandClient (`app/data_sources/naver_land.py`)

```python
class NaverLandClient:
    """네이버 부동산 모바일 API 클라이언트"""
    
    MOBILE_URL = "https://m.land.naver.com"
    
    def __init__(self, delay_range=(2.0, 3.0)):
        self.delay_range = delay_range  # 차단 방지 딜레이
        self.cache = get_cache_manager()
    
    def search_by_region(
        self,
        region_code: str,       # "11500" (강서구)
        user_input: UserInput,
        max_items: int = 50
    ) -> list[Listing]:
        """지역 코드로 매물 검색"""
        
        # 1. 캐시 확인
        cache_key = f"search_{region_code}_{trade_type}_{property_type}"
        if cached := self.cache.get(cache_key):
            return cached
        
        # 2. 클러스터 조회
        clusters = self._get_clusters(region_code, ...)
        
        # 3. 각 클러스터에서 매물 조회
        for cluster in clusters:
            articles = self._get_articles(cluster['lgeo'], ...)
            for article in articles:
                listing = self._parse_article(article)
                listings.append(listing)
        
        # 4. 단지 정보 보강
        for listing in listings:
            complex_info = self._get_complex_info(listing.complex_id)
            listing.households = complex_info.get('households')
            listing.built_year = complex_info.get('built_year')
        
        # 5. 캐시 저장 (24시간)
        self.cache.set(cache_key, listings)
        
        return listings
    
    def _safe_request(self, url: str, params: dict) -> dict:
        """안전한 API 요청 (차단 감지 + 딜레이)"""
        self._delay()  # 2-3초 대기
        
        response = self.client.get(url, params=params)
        
        # 차단 감지
        if response.status_code in [403, 429, 503]:
            raise BlockedError(f"API 차단됨 (HTTP {response.status_code})")
        
        return response.json()
```

### 5.2 MolitRealPriceClient (`app/data_sources/molit_api.py`)

```python
class MolitRealPriceClient:
    """국토교통부 실거래가 API"""
    
    BASE_URL = "http://openapi.molit.go.kr"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("DATA_GO_KR_API_KEY")
    
    def get_apt_rent_prices(
        self,
        sigungu_code: str,  # "11500"
        year_month: str     # "202401"
    ) -> list[dict]:
        """아파트 전월세 실거래가 조회"""
        
    def get_apt_trade_prices(
        self,
        sigungu_code: str,
        year_month: str
    ) -> list[dict]:
        """아파트 매매 실거래가 조회"""
    
    def calculate_jeonse_ratio(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        current_deposit: int
    ) -> dict:
        """
        전세가율 계산
        
        Returns:
            {
                "jeonse_ratio": 75.5,      # 전세가율 (%)
                "risk_level": "주의",       # 안전/보통/주의/위험
                "avg_trade_price": 60000,   # 평균 매매가
            }
        """
    
    def get_complex_price_analysis(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        current_deposit: int
    ) -> dict:
        """단지 종합 가격 분석"""
```

### 5.3 RegionCodeManager (`app/data_sources/region_codes.py`)

```python
class RegionCodeManager:
    """지역 코드 관리"""
    
    SEOUL_GU_CODES = {
        "강서구": "11500",
        "양천구": "11470",
        "영등포구": "11560",
        # ... 서울 25개 구
    }
    
    def get_sigungu_code(self, gu_name: str) -> Optional[str]:
        """구 이름 → 시군구 코드"""
        return self.SEOUL_GU_CODES.get(gu_name)
    
    def get_codes_for_regions(self, regions: list[str]) -> list[str]:
        """지역 목록 → 코드 목록"""

# 편의 함수
def get_region_code(gu_name: str) -> Optional[str]:
    """싱글톤 패턴 편의 함수"""
```

### 5.4 CacheManager (`app/data_sources/cache_manager.py`)

```python
class CacheManager:
    """파일 기반 캐시 (24시간 TTL)"""
    
    def __init__(self, cache_dir: str = "data/cache", ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
    
    def get(self, key: str) -> Optional[Any]:
        """캐시 조회 (TTL 체크)"""
    
    def set(self, key: str, value: Any):
        """캐시 저장"""
    
    def clear(self):
        """캐시 전체 삭제"""
```

---

## 6. Domain 로직

### 6.1 FilterEngine (`app/domain/filters.py`)

```python
class FilterEngine:
    """규칙 기반 필터 엔진"""
    
    def __init__(self):
        # 필터 함수 레지스트리
        self._filters = {
            "max_deposit": self._check_max_deposit,
            "min_area_sqm": self._check_min_area,
            "min_households": self._check_min_households,
            # ...
        }
    
    def filter(self, listing: Listing, user_input: UserInput) -> FilterResult:
        """
        매물 필터링
        
        1. 각 조건 체크
        2. must_conditions 실패 → FAIL
        3. 일부 실패 → PARTIAL
        4. 전체 통과 → PASS
        """
    
    # 개별 필터 함수
    def _check_max_deposit(self, listing, max_val) -> tuple[bool, str]:
        if listing.deposit <= max_val:
            return True, ""
        return False, f"보증금 {listing.deposit:,}만원 > 상한 {max_val:,}만원"
```

### 6.2 RiskEngine (`app/domain/risk_rules.py`)

```python
class RiskEngine:
    """규칙 기반 리스크 탐지"""
    
    # 리스크 패턴 (정규식)
    RISK_PATTERNS = [
        (r"보증보험\s*(불가|어려)", "보증보험", RiskLevel.HIGH, 
         "전세보증보험 가입 불가 가능성", ...),
        (r"근저당|담보", "권리관계", RiskLevel.HIGH,
         "근저당 설정 가능성", ...),
        (r"전세가율.{0,10}(위험|80%)", "전세가율", RiskLevel.HIGH,
         "깡통전세 위험", ...),
        # ...
    ]
    
    def analyze(self, listing: Listing) -> RiskResult:
        """
        리스크 분석
        
        1. description 텍스트에서 패턴 매칭
        2. 구조적 리스크 체크 (세대수, 연식, 층수 등)
        3. 리스크 점수 계산 (HIGH=25, MEDIUM=15, LOW=5)
        """
    
    def _check_structural_risks(self, listing) -> list[RiskItem]:
        """구조적 데이터 기반 리스크"""
        # 100세대 미만 → 소규모 단지 리스크
        # 30년 이상 → 노후 건물 리스크
        # 1층/최상층 → 층수 리스크
```

---

## 7. UI 구조

### 7.1 app.py (`ui/app.py`)

```python
# 진입점
def main():
    st.title("🏠 PropLens")
    
    # 사이드바: 검색 조건
    with st.sidebar:
        transaction_type = st.selectbox("거래 유형", ["전세", "월세", "매매"])
        max_deposit = st.number_input("최대 보증금", value=45000)
        selected_regions = st.multiselect("지역", [...])
        # ...
    
    # 검색 버튼
    if st.button("검색 시작"):
        result, error = run_analysis(...)
        st.session_state.analysis_result = result
    
    # 결과 표시
    if st.session_state.analysis_result:
        display_result(st.session_state.analysis_result)

def run_analysis(...) -> tuple[dict, str]:
    """분석 실행"""
    load_dotenv()  # .env 로드
    
    user_input = UserInput(...)
    orchestrator = PipelineOrchestrator()
    report = orchestrator.run(user_input)
    
    return report.model_dump(), None

def display_result(result: dict):
    """결과 렌더링"""
    # 요약 메트릭
    st.metric("전체 매물", result["total_count"])
    st.metric("조건 충족", result["passed_count"])
    
    # 추천 매물 상세
    for rec in result["top_recommendations"]:
        with st.expander(f"#{i} {title}"):
            display_listing_detail(rec)

def display_listing_detail(rec: dict):
    """매물 상세 정보"""
    # 기본 정보
    # 전세가율 분석
    # 리스크 목록
    # 중개사 질문
```

---

## 8. 환경 설정

### 8.1 .env 파일

```ini
# 개발 환경
ENV=development

# 국토부 실거래가 API (전세가율 분석용)
# https://www.data.go.kr/data/15126474/openapi.do
DATA_GO_KR_API_KEY=your_api_key_here

# ODsay 대중교통 API (출퇴근 시간 계산용)
# https://lab.odsay.com
ODSAY_API_KEY=your_api_key_here

# 크롤링 설정
CRAWL_DELAY_MIN=2.0
CRAWL_DELAY_MAX=3.0
MAX_ITEMS_PER_REGION=50

# 로깅
LOG_LEVEL=INFO
```

### 8.2 requirements.txt

```
streamlit>=1.28.0
httpx>=0.25.0
pydantic>=2.0.0
python-dotenv>=1.0.0
loguru>=0.7.0
python-dateutil>=2.8.0
```

---

## 9. 데이터 흐름 다이어그램

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              UI Layer                                      │
│                         ui/app.py::main()                                  │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ UserInput
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         Pipeline Layer                                     │
│                 app/pipeline/orchestrator.py                               │
│                    PipelineOrchestrator.run()                              │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  SearchAgent    │    │  EnrichAgent    │    │  FilterAgent    │
│  search_agent.py│    │  enrich_agent.py│    │  filter_agent.py│
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ NaverLandClient │    │MolitRealPrice   │    │  FilterEngine   │
│ naver_land.py   │    │Client           │    │  filters.py     │
│                 │    │molit_api.py     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 네이버 부동산    │    │ 국토부 API      │    │ 규칙 기반 로직   │
│ (외부 API)      │    │ (외부 API)      │    │ (코드)          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 10. 향후 확장 포인트

### 10.1 LLM 통합

```python
# app/llm/client.py (향후 구현)
class LlamaClient:
    """llama.cpp GGUF 모델 래퍼"""
    
    def __init__(self, model_path: str):
        self.model = Llama(model_path=model_path)
    
    def generate(self, prompt: str) -> str:
        """텍스트 생성"""
```

### 10.2 추가 데이터 소스

- 직방 API
- 다방 API
- 호갱노노 (시세 비교)

### 10.3 API 서버

```python
# app/api/main.py (향후 구현)
from fastapi import FastAPI

app = FastAPI()

@app.post("/api/v1/search")
def search(request: SearchRequest):
    orchestrator = PipelineOrchestrator()
    report = orchestrator.run(request.user_input)
    return report
```
