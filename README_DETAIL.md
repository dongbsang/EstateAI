# PropLens 기술 상세 문서

> 프로젝트 아키텍처, 실행 흐름, 스키마, 모듈 상세

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [실행 흐름](#2-실행-흐름)
3. [디렉토리 구조](#3-디렉토리-구조)
4. [핵심 스키마](#4-핵심-스키마)
5. [Agent 상세](#5-agent-상세)
6. [Data Source 상세](#6-data-source-상세)
7. [Domain 로직](#7-domain-로직)
8. [UI 구조](#8-ui-구조)
9. [CLI 도구](#9-cli-도구)
10. [설정](#10-설정)
11. [향후 확장](#11-향후-확장)

---

## 1. 아키텍처 개요

### 1.1 설계 원칙

```
┌─────────────────────────────────────────────────────────────┐
│                    PropLens Architecture                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │   UI    │  │   CLI   │  │   API   │  │  Test   │        │
│  │Streamlit│  │ Scripts │  │ FastAPI │  │ pytest  │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
│       └────────────┴────────────┴────────────┘              │
│                         │                                   │
│              ┌──────────▼──────────┐                        │
│              │  PipelineOrchestrator│                        │
│              │  (app/pipeline/)    │                        │
│              └──────────┬──────────┘                        │
│                         │                                   │
│    ┌────────────────────┼────────────────────┐              │
│    │                    │                    │              │
│    ▼                    ▼                    ▼              │
│ ┌──────────┐     ┌──────────┐        ┌──────────┐          │
│ │  Agents  │     │  Domain  │        │DataSource│          │
│ │ (9개)    │     │ (Rules)  │        │ (APIs)   │          │
│ └──────────┘     └──────────┘        └──────────┘          │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐│
│ │                    Schemas (Pydantic)                   ││
│ │        UserInput, Listing, FilterResult, Report         ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 1.2 핵심 제약

| 제약 | 설명 |
|------|------|
| LLM은 보조 엔진 | 판단/필터/점수는 규칙 기반 코드로 처리 |
| llama.cpp 내장형 | 외부 유료 API 의존 금지 (향후 GGUF 모델 사용) |
| JSON 스키마 고정 | 모든 Agent는 고정된 입출력 스키마 사용 |
| 설명 가능한 결과 | 모든 결정에 근거 포함 |

---

## 2. 실행 흐름

### 2.1 자동 검색 흐름

```python
# ui/app.py → run_auto_analysis()
def run_auto_analysis(...):
    # 1. UserInput 생성
    user_input = UserInput(
        transaction_type=transaction_type,
        max_deposit=max_deposit,
        regions=regions,
        property_types=property_types,
        ...
    )
    
    # 2. Pipeline 실행
    orchestrator = PipelineOrchestrator()
    report = orchestrator.run(user_input)
    
    return report
```

### 2.2 파이프라인 상세 (PipelineOrchestrator.run)

```python
def run(self, user_input: UserInput) -> Report:
    
    # Step 1: 매물 검색 (주택유형별)
    listings = self.search_agent.run(user_input)
    # → NaverLandClient.search_by_region()
    # → 캐시 확인 → API 호출 → Listing 객체 변환
    
    # Step 2: 데이터 보강 (실거래가)
    listings = self.enrich_agent.run(EnrichInput(listings, user_input))
    # → MolitRealPriceClient.get_complex_price_analysis()
    # → 전세가율 계산, 시세 비교
    
    # Step 3: 데이터 정규화
    for listing in listings:
        listing = self.normalize_agent.run(listing)
        # → 평수 계산, 데이터 정제
    
    # Step 4: 1차 필터링 (통근 시간 제외)
    for listing in listings:
        result = self.filter_agent.run(FilterInput(listing, user_input))
        # → FilterEngine.filter()
        # → must_conditions 체크 → PASS/FAIL/PARTIAL
    
    # Step 5: 통근 시간 계산 (필터 통과 매물만)
    if user_input.commute_destination:
        commute_results = self.commute_agent.run(CommuteInput(...))
        # → ODsayClient.get_transit_route()
        # → 통근 시간 초과 시 필터 결과 업데이트
    
    # Step 6: 점수화
    for listing in passed_listings:
        scored = self.score_agent.run(ScoreInput(listing, user_input))
        # → ScoringEngine.score()
        # → 카테고리별 점수: 가격/면적/단지/위치/옵션/상태
    
    # Step 7: 리스크 분석
    for listing in listings:
        risk = self.risk_agent.run(listing)
        # → RiskEngine.analyze()
        # → 패턴 매칭 + 구조적 리스크 체크
    
    # Step 8: 질문 생성
    for listing in listings:
        questions = self.question_agent.run(QuestionInput(listing, risk))
        # → 리스크 기반 질문 + 기본 질문
    
    # Step 9: 리포트 생성
    report = self.report_agent.run(ReportInput(...))
    # → 점수순 정렬, 요약/인사이트 생성
    
    return report
```

### 2.3 직접 평가 흐름

```python
# ui/app.py → run_single_evaluation_from_listing()

# 1. 단지 목록 조회
complexes = NaverLandClient().get_region_complex_list(sigungu_code)

# 2. 매물 목록 조회
listings = NaverLandClient().get_complex_articles(sigungu_code, complex_name)

# 3. 개별 Agent 실행 (파이프라인 없이)
filter_result = FilterAgent().run(FilterInput(listing, user_input))
scored = ScoreAgent().run(ScoreInput(listing, user_input))
risk = RiskAgent().run(listing)
questions = QuestionAgent().run(QuestionInput(listing, risk))
```

---

## 3. 디렉토리 구조

```
D:\03_AI\EstateAI\
│
├── .cache/                 # 매물 캐시 (24시간 TTL)
├── .env                    # 환경변수 (API 키)
├── .env.example            # 환경변수 예시
├── requirements.txt        # Python 의존성
├── README.md               # 프로젝트 개요
├── README_DETAIL.md        # 기술 상세 (이 문서)
│
├── ui/
│   └── app.py              # Streamlit 메인 UI
│                           # - 자동 검색 탭
│                           # - 직접 평가 탭
│
├── scripts/
│   └── cache_cli.py        # 캐시 관리 CLI
│
├── app/
│   ├── __init__.py
│   ├── config.py           # 설정 관리 (pydantic-settings)
│   │
│   ├── schemas/            # Pydantic 데이터 모델
│   │   ├── __init__.py
│   │   ├── user_input.py   # UserInput, TransactionType, PropertyType
│   │   ├── listing.py      # Listing, ListingSource
│   │   └── results.py      # FilterResult, ScoredListing, RiskResult, Report
│   │
│   ├── data_sources/       # 외부 API 클라이언트
│   │   ├── __init__.py
│   │   ├── naver_land.py   # 네이버 부동산 크롤러
│   │   ├── molit_api.py    # 국토부 실거래가 API
│   │   ├── odsay_api.py    # ODsay 대중교통 API
│   │   ├── region_codes.py # 지역 코드 관리
│   │   └── cache_manager.py # 파일 기반 캐시
│   │
│   ├── agents/             # Agent 구현 (9개)
│   │   ├── __init__.py
│   │   ├── base.py         # BaseAgent 추상 클래스
│   │   ├── search_agent.py
│   │   ├── enrich_agent.py
│   │   ├── commute_agent.py
│   │   ├── normalize_agent.py
│   │   ├── filter_agent.py
│   │   ├── score_agent.py
│   │   ├── risk_agent.py
│   │   ├── question_agent.py
│   │   └── report_agent.py
│   │
│   ├── domain/             # 비즈니스 로직 (규칙 기반)
│   │   ├── __init__.py
│   │   ├── filters.py      # FilterEngine
│   │   ├── scoring.py      # ScoringEngine
│   │   └── risk_rules.py   # RiskEngine
│   │
│   ├── pipeline/           # 오케스트레이션
│   │   ├── __init__.py
│   │   └── orchestrator.py # PipelineOrchestrator
│   │
│   └── api/                # FastAPI 서버
│       ├── __init__.py
│       ├── main.py
│       └── routes.py
│
├── data/                   # 샘플 데이터
├── models/                 # GGUF 모델 (향후)
└── docs/                   # 문서
```

---

## 4. 핵심 스키마

### 4.1 UserInput (`app/schemas/user_input.py`)

```python
class TransactionType(str, Enum):
    JEONSE = "전세"
    MONTHLY = "월세"
    SALE = "매매"

class PropertyType(str, Enum):
    APARTMENT = "아파트"
    OFFICETEL = "오피스텔"
    VILLA = "빌라"

class UserInput(BaseModel):
    # 거래 조건
    transaction_type: TransactionType = "전세"
    
    # 예산
    max_deposit: Optional[int]          # 최대 보증금 (만원)
    max_monthly_rent: Optional[int]     # 최대 월세 (만원)
    max_maintenance_fee: Optional[int]  # 최대 관리비 (만원)
    
    # 위치
    regions: list[str]                  # ["강서구", "양천구"]
    commute_destination: Optional[str]  # "여의도역"
    max_commute_minutes: Optional[int]  # 40
    
    # 주택 조건
    property_types: list[PropertyType]  # ["아파트", "오피스텔"]
    min_area_sqm: Optional[float]       # 84.0
    max_area_sqm: Optional[float]
    min_households: Optional[int]       # 1000
    min_built_year: Optional[int]
    max_built_year: Optional[int]
    
    # 옵션
    require_parking: bool = False
    require_elevator: bool = False
    min_floor: Optional[int]
    max_floor: Optional[int]
    
    # 필수 조건 (미충족 시 탈락)
    must_conditions: list[str]          # ["max_deposit", "min_area_sqm"]
```

### 4.2 Listing (`app/schemas/listing.py`)

```python
class ListingSource(str, Enum):
    NAVER = "네이버부동산"
    ZIGBANG = "직방"
    DABANG = "다방"
    CSV = "CSV"
    MANUAL = "수동입력"

class Listing(BaseModel):
    # 식별
    id: str                     # "naver_2412345678"
    source: ListingSource
    url: Optional[HttpUrl]
    
    # 기본 정보
    title: Optional[str]        # "래미안목동아델리체"
    address: Optional[str]
    region_gu: Optional[str]    # "양천구"
    region_dong: Optional[str]  # "목동"
    
    # 거래 정보
    transaction_type: Optional[str]  # "전세"
    deposit: Optional[int]           # 45000 (만원)
    monthly_rent: Optional[int]
    maintenance_fee: Optional[int]
    
    # 주택 유형
    property_type: Optional[str]     # "아파트"
    
    # 면적
    area_sqm: Optional[float]        # 84.98
    area_pyeong: Optional[float]     # 25.7
    supply_area_sqm: Optional[float]
    
    # 단지 정보
    complex_name: Optional[str]
    households: Optional[int]        # 1500
    buildings: Optional[int]
    built_year: Optional[int]        # 2020
    parking_per_household: Optional[float]
    
    # 위치
    latitude: Optional[float]
    longitude: Optional[float]
    nearest_station: Optional[str]
    station_distance_m: Optional[int]
    
    # 건물 정보
    floor: Optional[int]
    total_floors: Optional[int]
    direction: Optional[str]
    has_elevator: Optional[bool]
    has_parking: Optional[bool]
    
    # 설명 (리스크 분석용)
    description: Optional[str]
```

### 4.3 결과 스키마 (`app/schemas/results.py`)

```python
class FilterStatus(str, Enum):
    PASS = "통과"
    FAIL = "탈락"
    PARTIAL = "일부충족"

class FilterResult(BaseModel):
    listing_id: str
    status: FilterStatus
    passed_conditions: list[str]
    failed_conditions: list[str]
    failure_reasons: dict[str, str]  # {"max_deposit": "보증금 5억 > 상한 4.5억"}

class ScoreBreakdown(BaseModel):
    category: str       # "가격", "면적", "단지", "위치", "옵션", "상태"
    score: float
    max_score: float
    reason: str

class ScoredListing(BaseModel):
    listing_id: str
    listing: Listing
    total_score: float  # 0-100
    rank: Optional[int]
    breakdown: list[ScoreBreakdown]

class RiskLevel(str, Enum):
    HIGH = "높음"
    MEDIUM = "보통"
    LOW = "낮음"
    INFO = "참고"

class RiskItem(BaseModel):
    category: str       # "보증보험", "권리관계", "건물상태", "전세가율"
    level: RiskLevel
    title: str
    description: str
    check_action: str   # 확인 방법/조치사항
    source: Optional[str]

class RiskResult(BaseModel):
    listing_id: str
    risk_score: int     # 0-100
    risks: list[RiskItem]
    summary: str

class QuestionResult(BaseModel):
    listing_id: str
    questions: list[str]
    question_reasons: dict[str, str]

class ListingReport(BaseModel):
    listing: Listing
    filter_result: Optional[FilterResult]
    score_result: Optional[ScoredListing]
    risk_result: Optional[RiskResult]
    question_result: Optional[QuestionResult]

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

## 5. Agent 상세

### 5.1 BaseAgent (`app/agents/base.py`)

```python
class BaseAgent(ABC, Generic[InputT, OutputT]):
    name: str = "BaseAgent"
    
    def run(self, input_data: InputT) -> OutputT:
        """외부 호출 인터페이스"""
        self._validate_input(input_data)
        result = self._process(input_data)
        self._validate_output(result)
        return result
    
    @abstractmethod
    def _process(self, input_data: InputT) -> OutputT:
        """실제 처리 로직 (서브클래스에서 구현)"""
        pass
```

### 5.2 Agent 목록

| Agent | 입력 | 출력 | 역할 |
|-------|------|------|------|
| **SearchAgent** | UserInput | list[Listing] | 네이버 부동산에서 매물 검색 |
| **EnrichAgent** | EnrichInput | list[Listing] | 실거래가 데이터 보강 |
| **NormalizeAgent** | Listing | Listing | 데이터 정규화 (평수 계산 등) |
| **FilterAgent** | FilterInput | FilterResult | 조건 필터링 |
| **CommuteAgent** | CommuteInput | dict[str, CommuteResult] | 통근 시간 계산 |
| **ScoreAgent** | ScoreInput | ScoredListing | 점수화 |
| **RiskAgent** | Listing | RiskResult | 리스크 분석 |
| **QuestionAgent** | QuestionInput | QuestionResult | 질문 생성 |
| **ReportAgent** | ReportInput | Report | 리포트 생성 |

### 5.3 Agent Input 스키마

```python
class EnrichInput(BaseModel):
    listings: list[Listing]
    user_input: UserInput

class FilterInput(BaseModel):
    listing: Listing
    user_input: UserInput

class CommuteInput(BaseModel):
    listings: list[Listing]
    destination: str
    max_minutes: Optional[int]

class ScoreInput(BaseModel):
    listing: Listing
    user_input: UserInput

class QuestionInput(BaseModel):
    listing: Listing
    risk_result: Optional[RiskResult]

class ReportInput(BaseModel):
    listings: list[Listing]
    user_input: UserInput
    filter_results: dict[str, FilterResult]
    score_results: dict[str, ScoredListing]
    risk_results: dict[str, RiskResult]
    question_results: dict[str, QuestionResult]
```

---

## 6. Data Source 상세

### 6.1 NaverLandClient (`app/data_sources/naver_land.py`)

```python
class NaverLandClient:
    """네이버 부동산 모바일 API 클라이언트"""
    
    # 주택 유형 코드 매핑
    PROPERTY_TYPE_CODES = {
        "아파트": "APT",
        "오피스텔": "OPST",
        "빌라": "VL",
    }
    
    def search_by_region(
        self,
        region_code: str,      # 시군구 코드 (5자리)
        user_input: UserInput,
        max_items: int = 50,
    ) -> list[Listing]:
        """
        지역 코드로 매물 검색 (캐시 적용)
        
        - 24시간 캐시
        - 2-3초 딜레이 (차단 방지)
        - 429/403 감지 시 BlockedError 발생
        """
    
    def get_complex_list(
        self,
        cortarNo: str,        # 법정동 코드 (10자리)
        trade_type: str,      # "B1"(전세), "B2"(월세), "A1"(매매)
    ) -> dict[str, dict]:
        """
        지역 내 단지 목록 조회 (세대수 포함)
        
        Returns:
            {
                "래미안목동": {
                    "hscpNo": "12345",
                    "complex_name": "래미안목동",
                    "households": 1500,
                    "buildings": 15,
                    "built_year": 2020,
                },
                ...
            }
        """
    
    def get_complex_articles(
        self,
        sigungu_code: str,
        complex_name: str,
        trade_type: str,
        property_type: str,
    ) -> list[Listing]:
        """특정 단지의 매물 목록 조회"""
```

### 6.2 RegionCodeManager (`app/data_sources/region_codes.py`)

```python
class RegionCodeManager:
    """지역 코드 관리자"""
    
    # 서울시 25개 구
    SEOUL_GU_CODES = {
        "종로구": "11110",
        "강남구": "11680",
        "강서구": "11500",
        # ... 25개 구
    }
    
    # 경기도 주요 지역
    GYEONGGI_CODES = {
        "성남 분당구": "41135",
        "수원 영통구": "41117",
        "용인 수지구": "41465",
        # ... 경기도 지역
    }
    
    def get_sigungu_code(self, region_name: str) -> Optional[str]:
        """지역명 → 시군구 코드 (5자리)"""
    
    def get_codes_for_regions(self, regions: list[str]) -> list[str]:
        """지역 목록 → 코드 목록"""

def get_name_by_code(code: str) -> str:
    """코드 → 지역명 (역방향 조회)"""
```

### 6.3 MolitRealPriceClient (`app/data_sources/molit_api.py`)

```python
class MolitRealPriceClient:
    """국토부 실거래가 API 클라이언트"""
    
    def get_complex_price_analysis(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        current_deposit: int,
        months: int = 3,
    ) -> Optional[dict]:
        """
        단지 실거래가 분석
        
        Returns:
            {
                "rent_analysis": {
                    "avg_deposit": 45000,
                    "min_deposit": 42000,
                    "max_deposit": 48000,
                    "count": 5,
                },
                "trade_analysis": {
                    "avg_price": 85000,
                    "min_price": 82000,
                    "max_price": 88000,
                    "count": 3,
                },
                "jeonse_ratio_analysis": {
                    "jeonse_ratio": 52.9,
                    "risk_level": "안전",  # 안전/보통/주의/위험
                },
            }
        """
```

### 6.4 ODsayClient (`app/data_sources/odsay_api.py`)

```python
class ODsayClient:
    """ODsay 대중교통 API 클라이언트"""
    
    def get_transit_route(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
    ) -> Optional[dict]:
        """
        대중교통 경로 검색
        
        Returns:
            {
                "total_time": 35,       # 총 소요시간(분)
                "walk_time": 10,        # 도보 시간(분)
                "transit_count": 1,     # 환승 횟수
                "path_type": "지하철",  # "지하철" | "버스" | "지하철+버스"
            }
        """

# 주요 지하철역 좌표 (21개)
STATION_COORDS = {
    "여의도역": {"lat": 37.5216, "lng": 126.9243},
    "강남역": {"lat": 37.4979, "lng": 127.0276},
    "판교역": {"lat": 37.3948, "lng": 127.1112},
    # ...
}
```

### 6.5 CacheManager (`app/data_sources/cache_manager.py`)

```python
class CacheManager:
    """파일 기반 캐시 (24시간 TTL)"""
    
    def get(self, params: dict) -> Optional[Any]:
        """캐시 조회 (만료 시 None)"""
    
    def set(self, params: dict, data: Any):
        """캐시 저장"""
    
    def clear(self) -> int:
        """전체 삭제 → 삭제된 개수"""
    
    def clear_expired(self) -> int:
        """만료된 캐시만 삭제"""
    
    def clear_by_region(self, region: str) -> int:
        """특정 지역 캐시 삭제"""
    
    def get_stats(self) -> dict:
        """{"count": 5, "size_kb": 125.3}"""
    
    def get_detailed_stats(self) -> list[dict]:
        """지역별 캐시 상세 정보"""
```

---

## 7. Domain 로직

### 7.1 FilterEngine (`app/domain/filters.py`)

```python
class FilterEngine:
    """규칙 기반 필터 엔진"""
    
    # 지원하는 필터 조건
    _filters = {
        "max_deposit": _check_max_deposit,
        "max_monthly_rent": _check_max_monthly_rent,
        "max_maintenance_fee": _check_max_maintenance_fee,
        "min_area_sqm": _check_min_area,
        "max_area_sqm": _check_max_area,
        "min_households": _check_min_households,
        "min_built_year": _check_min_built_year,
        "max_built_year": _check_max_built_year,
        "min_floor": _check_min_floor,
        "max_floor": _check_max_floor,
        "require_parking": _check_parking,
        "require_elevator": _check_elevator,
        "regions": _check_regions,
        "property_types": _check_property_types,
    }
    
    def filter(self, listing: Listing, user_input: UserInput) -> FilterResult:
        """
        필터링 로직:
        1. 각 조건 체크 → passed/failed 분류
        2. must_conditions에 있는 조건이 failed면 → FAIL
        3. must_conditions 외 조건만 failed면 → PARTIAL
        4. 전부 통과 → PASS
        """
```

### 7.2 ScoringEngine (`app/domain/scoring.py`)

```python
class ScoringEngine:
    """규칙 기반 점수화 엔진"""
    
    # 카테고리별 가중치 (합계 100)
    WEIGHTS = {
        "price": 25,     # 예산 대비 가격 (저렴할수록 높음)
        "size": 15,      # 희망 면적 충족도
        "complex": 20,   # 세대수/연식/주차
        "location": 20,  # 역세권/희망지역
        "options": 10,   # 엘리베이터/옵션/층수
        "condition": 10, # 상태 (키워드 기반, LLM 연동 예정)
    }
    
    def score(self, listing: Listing, user_input: UserInput) -> ScoredListing:
        """100점 만점 점수 산정"""
```

### 7.3 RiskEngine (`app/domain/risk_rules.py`)

```python
class RiskEngine:
    """규칙 기반 리스크 탐지 엔진"""
    
    RISK_PATTERNS = [
        # (패턴, 카테고리, 레벨, 제목, 설명, 조치)
        (r"보증보험\s*(불가|어려)", "보증보험", HIGH, ...),
        (r"근저당|담보", "권리관계", HIGH, ...),
        (r"전세가율.{0,10}(위험|80%)", "전세가율", HIGH, ...),
        (r"누수|습기|곰팡이", "건물상태", HIGH, ...),
        (r"급매", "계약조건", MEDIUM, ...),
        # ...
    ]
    
    def analyze(self, listing: Listing) -> RiskResult:
        """
        리스크 분석:
        1. 패턴 매칭 (description, title)
        2. 구조적 리스크 (세대수, 연식, 층수, 주차)
        3. 리스크 점수 계산 (HIGH: 25, MEDIUM: 15, LOW: 5)
        4. 요약 생성
        """
```

---

## 8. UI 구조

### 8.1 메인 구조 (`ui/app.py`)

```python
def main():
    st.title("🏠 PropLens")
    
    tab1, tab2 = st.tabs(["🔍 자동 검색", "📝 직접 평가"])
    
    with tab1:
        render_auto_search_tab()    # 조건 검색 + 파이프라인
    
    with tab2:
        render_single_evaluation_tab()  # 단지/매물 선택 평가
```

### 8.2 자동 검색 탭

```
┌─────────────────────┬──────────────────────────────────────┐
│     사이드바        │            결과 영역                 │
├─────────────────────┼──────────────────────────────────────┤
│ 🔍 검색 조건        │ 📊 분석 결과                         │
│ - 거래 유형         │                                      │
│ - 예산              │ 요약: "10개 중 4개 조건 충족"        │
│ - 지역 (다중선택)   │                                      │
│ - 출퇴근 설정       │ 💡 인사이트                          │
│ - 주거 유형         │ - 해당 지역 전세가 상승 추세         │
│ - 면적/세대수       │                                      │
│ - 필수 조건         │ ⭐ 추천 매물 (10/30)                 │
│                     │ ┌─────────────────────────────┐      │
│ ────────────────    │ │ #1 래미안목동 | 4.5억 | 85㎡│      │
│ 📦 캐시 관리        │ │ 🟢 리스크 낮음              │      │
│ - 전체 삭제         │ └─────────────────────────────┘      │
│ - 만료만 삭제       │                                      │
└─────────────────────┴──────────────────────────────────────┘
```

### 8.3 직접 평가 탭

```
┌─────────────────────┬──────────────────────────────────────┐
│     입력 영역       │            결과 영역                 │
├─────────────────────┼──────────────────────────────────────┤
│ Step 1️⃣ 기본 정보   │ 📊 평가 결과                         │
│ - 지역 선택         │                                      │
│ - 거래/주거 유형    │ ✅ 조건 충족!                        │
│                     │                                      │
│ Step 2️⃣ 단지 선택   │ ⚖️ 내 기준과 비교                    │
│ - 단지 목록 조회    │ ✅ 예산: 4.2억 ≤ 4.5억              │
│ - 단지명 직접 입력  │ ✅ 면적: 85㎡ ≥ 59㎡                │
│                     │                                      │
│ Step 3️⃣ 매물 선택   │ 📈 실거래가 분석                     │
│ - 매물 목록         │ - 전세 평균: 4.3억                   │
│ - 필터링 옵션       │ - 전세가율: 52% (안전)              │
│                     │                                      │
│ ⚖️ 내 평가 기준     │ ⚠️ 리스크                            │
│ - 최대 예산         │ - 소규모 단지 (주의)                 │
│ - 최소 면적         │                                      │
│                     │ ❓ 중개사 질문                       │
│ [📊 매물 평가]      │ 1. 보증보험 가입 가능?              │
└─────────────────────┴──────────────────────────────────────┘
```

---

## 9. CLI 도구

### 9.1 cache_cli.py (`scripts/cache_cli.py`)

```bash
# 사용법
python scripts/cache_cli.py <command> [options]

# 명령어
status          # 캐시 상태 요약
detail          # 캐시 상세 정보 (지역별)
clear           # 전체 삭제
clear-expired   # 만료된 캐시만 삭제
clear <code>    # 특정 지역 삭제 (예: clear 11500)
help            # 도움말
```

**출력 예시:**

```
$ python scripts/cache_cli.py detail

============================================================
📊 PropLens 캐시 상세 정보
============================================================
지역         유형   매물수   저장시간          남은시간
------------------------------------------------------------
✅ 강서구     전세   30       2025-01-06 10:30  23시간 30분
✅ 양천구     전세   25       2025-01-06 10:32  23시간 28분
❌ 영등포구   전세   40       2025-01-05 08:00  만료됨
============================================================
```

---

## 10. 설정

### 10.1 config.py (`app/config.py`)

```python
class Settings(BaseSettings):
    """pydantic-settings 기반 설정"""
    
    # 환경
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # LLM (향후)
    MODEL_PATH: str = "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    
    # 공공데이터 API
    DATA_GO_KR_API_KEY: str = ""
    
    # ODsay API
    ODSAY_API_KEY: str = ""
    
    # 네이버 부동산
    NAVER_LAND_TIMEOUT: int = 30
    NAVER_LAND_HEADERS: dict = {...}  # User-Agent 등
    
    # 크롤링 설정
    CRAWL_DELAY_MIN: float = 1.5  # 요청 간 최소 딜레이
    CRAWL_DELAY_MAX: float = 3.0  # 요청 간 최대 딜레이
    MAX_ITEMS_PER_REGION: int = 50
    
    # 코드 매핑
    PROPERTY_TYPE_CODES: dict = {
        "아파트": "APT",
        "오피스텔": "OPST",
        "빌라": "VL",
    }
    TRADE_TYPE_CODES: dict = {
        "매매": "A1",
        "전세": "B1",
        "월세": "B2",
    }

settings = Settings()  # 싱글톤
```

### 10.2 .env 예시

```ini
# 환경
ENV=development
LOG_LEVEL=INFO

# 국토부 실거래가 API (선택)
DATA_GO_KR_API_KEY=your_api_key_here

# ODsay 대중교통 API (선택)
ODSAY_API_KEY=your_api_key_here

# 크롤링 설정 (선택)
CRAWL_DELAY_MIN=2.0
CRAWL_DELAY_MAX=3.0
MAX_ITEMS_PER_REGION=50
```

---

## 11. 향후 확장

### 11.1 LLM 통합 (계획)

```python
# app/llm/client.py (향후 구현)
class LlamaClient:
    """llama.cpp GGUF 모델 래퍼"""
    
    def __init__(self, model_path: str):
        self.model = Llama(model_path=model_path)
    
    def generate(self, prompt: str, **kwargs) -> str:
        """텍스트 생성"""
```

**활용 예정 영역:**
- 매물 설명 분석 (상태 점수화)
- 리스크 설명 자연어 생성
- 중개사 질문 개인화

### 11.2 추가 데이터 소스 (계획)

- 직방 API
- 다방 API
- 호갱노노 (시세 비교)

### 11.3 추가 기능 (계획)

- 매물 즐겨찾기
- 검색 조건 저장
- 알림 (신규 매물)
- PDF 리포트 출력
