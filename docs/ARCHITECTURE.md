# PropLens 아키텍처 설계

## 1. 시스템 개요

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                              │
│                  (Streamlit / React)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      API Layer                               │
│                    (FastAPI)                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Pipeline Orchestrator                       │
│            (Agent 실행 순서 제어)                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│ Parse │→│Normalize│→│ Filter│→│ Score │→│ Risk  │
│ Agent │  │ Agent  │  │ Agent │  │ Agent │  │ Agent │
└───────┘  └────────┘  └───────┘  └───────┘  └───────┘
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                     ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
                     │Question│  │ Report │  │  LLM   │
                     │ Agent  │  │ Agent  │  │ Runner │
                     └────────┘  └────────┘  └────────┘
```

## 2. 핵심 원칙

### 2.1 LLM은 보조 엔진

```
┌─────────────────────────────────────────────┐
│              Domain Logic Layer              │
│  (규칙 기반 - 필터, 점수, 리스크 판단)      │
│                                             │
│  ✓ 예산 체크: if deposit > max_deposit      │
│  ✓ 면적 체크: if area < min_area            │
│  ✓ 점수 계산: 가중치 기반 수식              │
│  ✓ 리스크: 패턴 매칭                        │
└─────────────────────────────────────────────┘
                    │
                    │ LLM은 보조만
                    ▼
┌─────────────────────────────────────────────┐
│               LLM Layer                      │
│  (텍스트 처리 보조)                         │
│                                             │
│  ○ 매물 설명 요약                           │
│  ○ 리스크 신호 추출 (규칙 보완)             │
│  ○ 질문 문장 다듬기                         │
└─────────────────────────────────────────────┘
```

### 2.2 Agent 간 데이터 흐름

```
ParseInput          Listing           FilterResult
    │                  │                   │
    ▼                  ▼                   ▼
┌────────┐        ┌────────┐         ┌────────┐
│ Parse  │───────▶│Normalize│────────▶│ Filter │
│ Agent  │        │ Agent  │         │ Agent  │
└────────┘        └────────┘         └────────┘
                       │
              Listing  │  
                       ▼
                 ┌────────┐
                 │ Score  │──────┐
                 │ Agent  │      │
                 └────────┘      │
                       │         │
         ScoredListing │         │
                       ▼         │
                 ┌────────┐      │
                 │ Risk   │      │
                 │ Agent  │      │
                 └────────┘      │
                       │         │
            RiskResult │         │
                       ▼         ▼
                 ┌────────────────────┐
                 │   Question Agent   │
                 └────────────────────┘
                           │
               QuestionResult
                           ▼
                 ┌────────────────────┐
                 │   Report Agent     │
                 └────────────────────┘
                           │
                       Report
```

## 3. 스키마 설계

### 3.1 입력 스키마

```python
UserInput:
  - transaction_type: 전세/월세/매매
  - max_deposit: int (만원)
  - min_area_sqm: float
  - min_households: int
  - regions: list[str]
  - must_conditions: list[str]  # 필수 조건 필드명
```

### 3.2 매물 스키마

```python
Listing:
  - id: str (소스_해시)
  - source: 네이버/직방/CSV/수동
  - deposit: int
  - area_sqm: float
  - households: int
  - built_year: int
  - region_gu: str
  - description: str
  - ...
```

### 3.3 결과 스키마

```python
Report:
  - total_count: int
  - passed_count: int
  - top_recommendations: list[ListingReport]
  - filtered_out: list[ListingReport]
  - summary: str
  - insights: list[str]

ListingReport:
  - listing: Listing
  - filter_result: FilterResult
  - score_result: ScoredListing
  - risk_result: RiskResult
  - question_result: QuestionResult
```

## 4. 확장 계획

### Phase 1: MVP (현재)
- [x] 텍스트/CSV 입력
- [x] 규칙 기반 필터/점수/리스크
- [x] 기본 질문 생성
- [x] Streamlit UI

### Phase 2: LLM 통합
- [ ] llama.cpp 연동
- [ ] 매물 설명 요약
- [ ] LLM 기반 리스크 추출
- [ ] 맞춤 질문 생성

### Phase 3: 데이터 확장
- [ ] 국토부 실거래가 API
- [ ] 통근 시간 계산
- [ ] 네이버 매물 파서 개선

### Phase 4: 배포
- [ ] llama.cpp 내장 배포
- [ ] Electron/Tauri 패키징
- [ ] 설치 프로그램
