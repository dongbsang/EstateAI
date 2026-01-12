"""
사용자 입력 스키마
사용자가 입력하는 조건을 구조화합니다.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TransactionType(str, Enum):
    """거래 유형"""
    JEONSE = "전세"
    MONTHLY = "월세"
    SALE = "매매"


class PropertyType(str, Enum):
    """주택 유형"""
    APARTMENT = "아파트"
    OFFICETEL = "오피스텔"
    VILLA = "빌라"


class UserInput(BaseModel):
    """
    사용자 입력 스키마
    
    모든 조건은 optional이며, 입력된 조건만 필터링에 사용됩니다.
    must_conditions에 포함된 조건은 미충족 시 탈락,
    그 외 조건은 점수 계산에만 반영됩니다.
    """
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "transaction_type": "전세",
                "max_deposit": 45000,
                "regions": ["강서구", "양천구"],
                "commute_destination": "여의도역",
                "max_commute_minutes": 40,
                "property_types": ["아파트"],
                "min_area_sqm": 84.0,
                "min_households": 1000,
                "require_parking": True,
                "must_conditions": ["max_deposit", "min_area_sqm"]
            }
        }
    )
    
    # === 거래 조건 ===
    transaction_type: TransactionType = Field(
        default=TransactionType.JEONSE,
        description="거래 유형: 전세/월세/매매"
    )
    
    # === 예산 조건 ===
    max_deposit: Optional[int] = Field(
        default=None,
        description="최대 보증금 (만원 단위)",
        examples=[45000]
    )
    max_monthly_rent: Optional[int] = Field(
        default=None,
        description="최대 월세 (만원 단위)",
        examples=[100]
    )
    max_maintenance_fee: Optional[int] = Field(
        default=None,
        description="최대 관리비 (만원 단위)",
        examples=[30]
    )
    
    # === 위치 조건 ===
    regions: list[str] = Field(
        default_factory=list,
        description="선호 지역 (구/동 단위)",
        examples=[["강서구", "양천구", "영등포구"]]
    )
    commute_destination: Optional[str] = Field(
        default=None,
        description="출퇴근 목적지",
        examples=["여의도역"]
    )
    max_commute_minutes: Optional[int] = Field(
        default=None,
        description="최대 통근 시간 (분)",
        examples=[40]
    )
    
    # === 주택 조건 ===
    property_types: list[PropertyType] = Field(
        default_factory=lambda: [PropertyType.APARTMENT],
        description="주택 유형"
    )
    min_area_sqm: Optional[float] = Field(
        default=None,
        description="최소 전용면적 (㎡)",
        examples=[84.0]
    )
    max_area_sqm: Optional[float] = Field(
        default=None,
        description="최대 전용면적 (㎡)"
    )
    min_households: Optional[int] = Field(
        default=None,
        description="최소 세대수",
        examples=[1000]
    )
    min_built_year: Optional[int] = Field(
        default=None,
        description="최소 준공연도",
        examples=[2010]
    )
    max_built_year: Optional[int] = Field(
        default=None,
        description="최대 준공연도"
    )
    
    # === 옵션 조건 ===
    require_parking: bool = Field(
        default=False,
        description="주차 필수 여부"
    )
    require_elevator: bool = Field(
        default=False,
        description="엘리베이터 필수 여부"
    )
    min_floor: Optional[int] = Field(
        default=None,
        description="최소 층수"
    )
    max_floor: Optional[int] = Field(
        default=None,
        description="최대 층수"
    )
    preferred_direction: Optional[str] = Field(
        default=None,
        description="선호 향",
        examples=["남향", "남동향"]
    )
    
    # === 조건 우선순위 ===
    must_conditions: list[str] = Field(
        default_factory=list,
        description="반드시 충족해야 하는 조건 필드명",
        examples=[["max_deposit", "min_area_sqm", "min_households"]]
    )
