"""
Normalize Agent
매물 정보의 단위와 형식을 통일합니다.
"""

from .base import BaseAgent
from app.schemas.listing import Listing


class NormalizeAgent(BaseAgent[Listing, Listing]):
    """
    정규화 Agent

    - 면적: ㎡ ↔ 평 변환
    - 가격: 만원 단위 통일
    - 문자열: 공백/특수문자 정리
    """

    name = "NormalizeAgent"

    # 변환 상수
    SQM_TO_PYEONG = 0.3025  # 1㎡ = 0.3025평
    PYEONG_TO_SQM = 3.305785  # 1평 = 3.305785㎡

    def _process(self, listing: Listing) -> Listing:
        """정규화 처리"""

        # 면적 통일
        listing = self._normalize_area(listing)

        # 주소 정리
        listing = self._normalize_address(listing)

        # 주택유형 정리
        listing = self._normalize_property_type(listing)

        return listing

    def _normalize_area(self, listing: Listing) -> Listing:
        """면적 단위 통일"""

        # ㎡가 있으면 평 계산
        if listing.area_sqm and not listing.area_pyeong:
            listing.area_pyeong = round(listing.area_sqm * self.SQM_TO_PYEONG, 1)

        # 평만 있으면 ㎡ 계산
        elif listing.area_pyeong and not listing.area_sqm:
            listing.area_sqm = round(listing.area_pyeong * self.PYEONG_TO_SQM, 2)

        return listing

    def _normalize_address(self, listing: Listing) -> Listing:
        """주소 정리"""

        # 주소에서 구/동 추출
        if listing.address and not listing.region_gu:
            import re
            gu_match = re.search(r"([가-힣]+구)", listing.address)
            if gu_match:
                listing.region_gu = gu_match.group(1)

            dong_match = re.search(r"([가-힣]+동)", listing.address)
            if dong_match:
                listing.region_dong = dong_match.group(1)

        return listing

    def _normalize_property_type(self, listing: Listing) -> Listing:
        """주택유형 정규화"""

        if listing.property_type:
            pt = listing.property_type.lower()

            # 표준화
            type_map = {
                "아파트": "아파트",
                "apt": "아파트",
                "오피스텔": "오피스텔",
                "officetel": "오피스텔",
                "빌라": "빌라",
                "연립": "빌라",
                "다세대": "빌라",
                "단독": "단독주택",
                "다가구": "다가구",
            }

            for key, value in type_map.items():
                if key in pt:
                    listing.property_type = value
                    break

        return listing
