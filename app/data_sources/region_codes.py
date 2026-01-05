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

    # 경기도 주요 도시 코드
    GYEONGGI_CODES = {
        # 성남시
        "성남시 수정구": "41131",
        "성남시 중원구": "41133",
        "성남시 분당구": "41135",
        "성남 수정구": "41131",
        "성남 중원구": "41133",
        "성남 분당구": "41135",
        "분당구": "41135",
        "분당": "41135",
        # 수원시
        "수원시 장안구": "41111",
        "수원시 권선구": "41113",
        "수원시 팔달구": "41115",
        "수원시 영통구": "41117",
        "수원 장안구": "41111",
        "수원 권선구": "41113",
        "수원 팔달구": "41115",
        "수원 영통구": "41117",
        "영통구": "41117",
        # 용인시
        "용인시 처인구": "41461",
        "용인시 기흥구": "41463",
        "용인시 수지구": "41465",
        "용인 처인구": "41461",
        "용인 기흥구": "41463",
        "용인 수지구": "41465",
        "수지구": "41465",
        "기흥구": "41463",
        # 고양시
        "고양시 덕양구": "41281",
        "고양시 일산동구": "41285",
        "고양시 일산서구": "41287",
        "고양 덕양구": "41281",
        "고양 일산동구": "41285",
        "고양 일산서구": "41287",
        "일산동구": "41285",
        "일산서구": "41287",
        "일산": "41285",  # 일산동구 기본
        # 안양시
        "안양시 만안구": "41171",
        "안양시 동안구": "41173",
        "안양 만안구": "41171",
        "안양 동안구": "41173",
        "동안구": "41173",
        "만안구": "41171",
        "평촌": "41173",  # 동안구
        # 부천시
        "부천시": "41190",
        "부천": "41190",
        # 광명시
        "광명시": "41210",
        "광명": "41210",
        # 안산시
        "안산시 상록구": "41271",
        "안산시 단원구": "41273",
        "안산 상록구": "41271",
        "안산 단원구": "41273",
        "상록구": "41271",
        "단원구": "41273",
        # 화성시
        "화성시": "41590",
        "화성": "41590",
        "동탄": "41590",
        # 평택시
        "평택시": "41220",
        "평택": "41220",
        # 시흥시
        "시흥시": "41390",
        "시흥": "41390",
        # 김포시
        "김포시": "41570",
        "김포": "41570",
        # 광주시 (경기)
        "광주시": "41610",
        "경기광주": "41610",
        # 하남시
        "하남시": "41450",
        "하남": "41450",
        # 구리시
        "구리시": "41310",
        "구리": "41310",
        # 남양주시
        "남양주시": "41360",
        "남양주": "41360",
        # 의정부시
        "의정부시": "41150",
        "의정부": "41150",
        # 파주시
        "파주시": "41480",
        "파주": "41480",
        # 과천시
        "과천시": "41290",
        "과천": "41290",
        # 의왕시
        "의왕시": "41430",
        "의왕": "41430",
        # 군포시
        "군포시": "41410",
        "군포": "41410",
    }

    def __init__(self):
        self.logger = logger.bind(source="RegionCode")

    def get_sigungu_code(self, region_name: str) -> Optional[str]:
        """
        지역명으로 시군구 코드 조회

        Args:
            region_name: 지역명 (예: "강서구", "분당구", "수원시 영통구")

        Returns:
            시군구 코드 (5자리)
        """
        # 1. 정확한 이름으로 경기도 먼저 검색 (우선순위 높음)
        if region_name in self.GYEONGGI_CODES:
            return self.GYEONGGI_CODES[region_name]

        # 2. 서울 구 검색
        # "구" 접미사 처리
        search_name = region_name
        if not search_name.endswith("구") and not search_name.endswith("시"):
            search_name = region_name + "구"

        if search_name in self.SEOUL_GU_CODES:
            return self.SEOUL_GU_CODES[search_name]

        # 3. 원본 이름으로 서울 검색
        if region_name in self.SEOUL_GU_CODES:
            return self.SEOUL_GU_CODES[region_name]

        return None

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


# 지역 코드 매니저 싱글톤 인스턴스
_region_manager: Optional[RegionCodeManager] = None


def get_region_code(gu_name: str) -> Optional[str]:
    """
    구 이름으로 시군구 코드 조회 (편의 함수)

    Args:
        gu_name: 구 이름 (예: "강서구", "양천구")

    Returns:
        시군구 코드 (5자리) 또는 None
    """
    global _region_manager
    if _region_manager is None:
        _region_manager = RegionCodeManager()
    return _region_manager.get_sigungu_code(gu_name)
