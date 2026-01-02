"""
결과 스키마
각 Agent의 출력 결과를 정의합니다.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from .listing import Listing


class FilterStatus(str, Enum):
    """필터 결과 상태"""
    PASS = "통과"
    FAIL = "탈락"
    PARTIAL = "일부충족"


class FilterResult(BaseModel):
    """
    Filter Agent 출력
    각 조건별 통과/탈락 여부와 근거를 포함합니다.
    """
    model_config = ConfigDict(use_enum_values=True)

    listing_id: str
    status: FilterStatus
    passed_conditions: list[str] = Field(
        default_factory=list,
        description="통과한 조건 목록"
    )
    failed_conditions: list[str] = Field(
        default_factory=list,
        description="탈락한 조건 목록"
    )
    failure_reasons: dict[str, str] = Field(
        default_factory=dict,
        description="탈락 사유 (조건명: 사유)",
        examples=[{"max_deposit": "보증금 5억 > 상한 4.5억"}]
    )


class ScoreBreakdown(BaseModel):
    """점수 상세 내역"""
    category: str = Field(description="점수 카테고리")
    score: float = Field(description="획득 점수")
    max_score: float = Field(description="최대 점수")
    reason: str = Field(description="점수 산정 근거")


class ScoredListing(BaseModel):
    """
    Score Agent 출력
    매물별 점수와 상세 내역을 포함합니다.
    """
    model_config = ConfigDict(use_enum_values=True)
    
    listing_id: str
    listing: Listing
    total_score: float = Field(description="총점 (100점 만점)")
    rank: Optional[int] = Field(default=None, description="순위")
    breakdown: list[ScoreBreakdown] = Field(
        default_factory=list,
        description="점수 상세 내역"
    )


class RiskLevel(str, Enum):
    """리스크 수준"""
    HIGH = "높음"
    MEDIUM = "보통"
    LOW = "낮음"
    INFO = "참고"


class RiskItem(BaseModel):
    """개별 리스크 항목"""
    model_config = ConfigDict(use_enum_values=True)
    
    category: str = Field(
        description="리스크 카테고리",
        examples=["보증보험", "권리관계", "건물상태"]
    )
    level: RiskLevel
    title: str = Field(description="리스크 제목")
    description: str = Field(description="상세 설명")
    check_action: str = Field(
        description="확인 방법/조치사항",
        examples=["등기부등본에서 근저당 확인 필요"]
    )
    source: Optional[str] = Field(
        default=None,
        description="근거 출처 (매물 설명 문구 등)"
    )


class RiskResult(BaseModel):
    """
    Risk Agent 출력
    매물별 리스크 체크 결과입니다.
    """
    listing_id: str
    risk_score: int = Field(
        description="리스크 점수 (0-100, 높을수록 위험)",
        ge=0,
        le=100
    )
    risks: list[RiskItem] = Field(default_factory=list)
    summary: str = Field(
        description="리스크 요약",
        examples=["보증보험 가입이 어려울 수 있습니다. 등기부등본 확인이 필요합니다."]
    )


class QuestionResult(BaseModel):
    """
    Question Agent 출력
    중개사에게 물어볼 질문 목록입니다.
    """
    listing_id: str
    questions: list[str] = Field(
        description="질문 목록",
        examples=[[
            "전세보증보험 가입이 가능한가요?",
            "현재 근저당 설정이 있나요?",
            "실제 입주 가능일이 언제인가요?"
        ]]
    )
    question_reasons: dict[str, str] = Field(
        default_factory=dict,
        description="질문별 이유 (질문: 이유)"
    )


class ListingReport(BaseModel):
    """개별 매물 리포트"""
    listing: Listing
    filter_result: Optional[FilterResult] = None
    score_result: Optional[ScoredListing] = None
    risk_result: Optional[RiskResult] = None
    question_result: Optional[QuestionResult] = None


class Report(BaseModel):
    """
    Report Agent 출력
    최종 분석 리포트입니다.
    """
    created_at: datetime = Field(default_factory=datetime.now)
    total_count: int = Field(description="전체 매물 수")
    passed_count: int = Field(description="조건 통과 매물 수")
    
    # 결과 목록
    top_recommendations: list[ListingReport] = Field(
        default_factory=list,
        description="추천 매물 (점수순)"
    )
    filtered_out: list[ListingReport] = Field(
        default_factory=list,
        description="탈락 매물"
    )
    
    # 요약
    summary: str = Field(
        description="전체 요약",
        examples=["10개 매물 중 4개가 조건에 부합합니다. 래미안목동이 가장 추천됩니다."]
    )
    insights: list[str] = Field(
        default_factory=list,
        description="주요 인사이트",
        examples=[["해당 지역 전세가가 상승 추세입니다.", "1000세대 이상 단지는 2개입니다."]]
    )
