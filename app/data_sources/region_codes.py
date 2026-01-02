"""
지역 코드 관리
법정동 코드, 시군구 코드 등을 관리합니다.
"""

from typing import Optional
from loguru import logger


class RegionCodeManager:
    """
    지역 코드 관리자

    네이버 부동산과 공공데이터 API에서 사용하는 지역 코드를 관리합니다.
    """

    # 서울시 구별 코드 (법정동 코드 앞 5자리 = 시군구 코드)
    SEOUL_GU_CODES = {
        "종로구": "11110",
        "중구": "11140",
        "용산구": "11170",
        "성동구": "11200",
        "광진구": "11215",
        "동대문구": "11230",
        "중랑구": "11260",
        "성북구": "11290",
        "강북구": "11305",
        "도봉구": "11320",
        "노원구": "11350",
        "은평구": "11380",
        "서대문구": "11410",
        "마포구": "11440",
        "양천구": "11470",
        "강서구": "11500",
        "구로구": "11530",
        "금천구": "11545",
        "영등포구": "11560",
        "동작구": "11590",
        "관악구": "11620",
        "서초구": "11650",
        "강남구": "11680",
        "송파구": "11710",
        "강동구": "11740",
    }

    def __init__(self):
        self.logger = logger.bind(source="RegionCode")

    def get_sigungu_code(self, gu_name: str) -> Optional[str]:
        """
        구 이름으로 시군구 코드 조회

        Args:
            gu_name: 구 이름 (예: "강서구", "양천구")

        Returns:
            시군구 코드 (5자리)
        """
        # "구" 접미사 처리
        if not gu_name.endswith("구"):
            gu_name = gu_name + "구"

        return self.SEOUL_GU_CODES.get(gu_name)

    def get_codes_for_regions(self, regions: list[str]) -> list[str]:
        """
        지역 목록에서 코드 추출

        Args:
            regions: 지역명 목록 (구 단위)

        Returns:
            시군구 코드 목록 (5자리)
        """
        codes = []

        for region in regions:
            code = self.get_sigungu_code(region)
            if code:
                codes.append(code)
            else:
                self.logger.warning(f"Unknown region: {region}")

        return codes

    def get_gu_from_code(self, code: str) -> Optional[str]:
        """코드에서 구 이름 추출"""
        sigungu = code[:5]

        for gu_name, gu_code in self.SEOUL_GU_CODES.items():
            if gu_code == sigungu:
                return gu_name

        return None

    def get_all_seoul_gu_codes(self) -> dict[str, str]:
        """서울시 전체 구 코드 반환"""
        return self.SEOUL_GU_CODES.copy()
