"""
매물 정보 스키마
파싱된 매물 데이터를 구조화합니다.
"""

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, HttpUrl


class ListingSource(str, Enum):
    """매물 데이터 소스"""
    NAVER = "네이버부동산"
    ZIGBANG = "직방"
    DABANG = "다방"
    CSV = "CSV"
    MANUAL = "수동입력"


class Listing(BaseModel):
    """
    매물 정보 스키마

    Parse Agent의 출력이자 이후 모든 Agent의 기본 입력입니다.
    필드가 없거나 파싱 실패 시 None으로 유지됩니다.
    """
    model_config = ConfigDict(use_enum_values=True)

    # === 식별 정보 ===
    id: str = Field(
        description="매물 고유 ID (소스_매물번호 형식)",
        examples=["naver_2412345678"]
    )
    source: ListingSource = Field(
        default=ListingSource.MANUAL,
        description="데이터 소스"
    )
    url: Optional[HttpUrl] = Field(
        default=None,
        description="매물 원본 URL"
    )

    # === 기본 정보 ===
    title: Optional[str] = Field(
        default=None,
        description="매물 제목/단지명",
        examples=["래미안목동아델리체"]
    )
    address: Optional[str] = Field(
        default=None,
        description="주소",
        examples=["서울특별시 양천구 목동 123"]
    )
    region_gu: Optional[str] = Field(
        default=None,
        description="구",
        examples=["양천구"]
    )
    region_dong: Optional[str] = Field(
        default=None,
        description="동",
        examples=["목동"]
    )

    # === 거래 정보 ===
    transaction_type: Optional[str] = Field(
        default=None,
        description="거래 유형",
        examples=["전세", "월세", "매매"]
    )
    deposit: Optional[int] = Field(
        default=None,
        description="보증금 (만원)",
        examples=[45000]
    )
    monthly_rent: Optional[int] = Field(
        default=None,
        description="월세 (만원, 전세는 0)",
        examples=[0]
    )
    maintenance_fee: Optional[int] = Field(
        default=None,
        description="관리비 (만원)",
        examples=[25]
    )
    maintenance_includes: list[str] = Field(
        default_factory=list,
        description="관리비 포함 항목",
        examples=[["수도", "인터넷", "TV"]]
    )

    # === 면적 정보 ===
    area_sqm: Optional[float] = Field(
        default=None,
        description="전용면적 (㎡)",
        examples=[84.98]
    )
    area_pyeong: Optional[float] = Field(
        default=None,
        description="전용면적 (평)",
        examples=[25.7]
    )
    supply_area_sqm: Optional[float] = Field(
        default=None,
        description="공급면적 (㎡)"
    )

    # === 건물 정보 ===
    property_type: Optional[str] = Field(
        default=None,
        description="주택 유형",
        examples=["아파트"]
    )
    floor: Optional[int] = Field(
        default=None,
        description="해당 층",
        examples=[15]
    )
    total_floors: Optional[int] = Field(
        default=None,
        description="건물 총 층수",
        examples=[25]
    )
    direction: Optional[str] = Field(
        default=None,
        description="향",
        examples=["남향"]
    )
    room_count: Optional[int] = Field(
        default=None,
        description="방 수"
    )
    bathroom_count: Optional[int] = Field(
        default=None,
        description="화장실 수"
    )

    # === 단지 정보 ===
    complex_name: Optional[str] = Field(
        default=None,
        description="단지명"
    )
    households: Optional[int] = Field(
        default=None,
        description="총 세대수",
        examples=[1500]
    )
    buildings: Optional[int] = Field(
        default=None,
        description="동 수"
    )
    built_year: Optional[int] = Field(
        default=None,
        description="준공연도",
        examples=[2020]
    )
    parking_per_household: Optional[float] = Field(
        default=None,
        description="세대당 주차대수",
        examples=[1.5]
    )
    heating_type: Optional[str] = Field(
        default=None,
        description="난방 방식",
        examples=["지역난방"]
    )

    # === 옵션 정보 ===
    has_elevator: Optional[bool] = Field(
        default=None,
        description="엘리베이터 유무"
    )
    has_parking: Optional[bool] = Field(
        default=None,
        description="주차 가능 여부"
    )
    options: list[str] = Field(
        default_factory=list,
        description="옵션 목록",
        examples=[["에어컨", "냉장고", "세탁기"]]
    )

    # === 위치 정보 ===
    nearest_station: Optional[str] = Field(
        default=None,
        description="최근접 지하철역"
    )
    station_distance_m: Optional[int] = Field(
        default=None,
        description="역까지 거리 (m)"
    )
    latitude: Optional[float] = Field(
        default=None,
        description="위도"
    )
    longitude: Optional[float] = Field(
        default=None,
        description="경도"
    )

    # === 메타 정보 ===
    description: Optional[str] = Field(
        default=None,
        description="매물 설명 원문"
    )
    agent_name: Optional[str] = Field(
        default=None,
        description="중개사 이름"
    )
    agent_phone: Optional[str] = Field(
        default=None,
        description="중개사 연락처"
    )
    listed_date: Optional[date] = Field(
        default=None,
        description="등록일"
    )
    updated_date: Optional[date] = Field(
        default=None,
        description="수정일"
    )

    # === 파싱 메타 ===
    raw_text: Optional[str] = Field(
        default=None,
        description="파싱 원본 텍스트 (디버깅용)"
    )
    parse_warnings: list[str] = Field(
        default_factory=list,
        description="파싱 경고 메시지"
    )

    def to_summary(self) -> str:
        """매물 요약 문자열 생성"""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.transaction_type and self.deposit:
            if self.monthly_rent:
                parts.append(f"{self.transaction_type} {self.deposit}/{self.monthly_rent}만")
            else:
                parts.append(f"{self.transaction_type} {self.deposit}만")
        if self.area_pyeong:
            parts.append(f"{self.area_pyeong}평")
        if self.floor:
            parts.append(f"{self.floor}층")
        return " | ".join(parts) if parts else self.id
