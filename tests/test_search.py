"""
PropLens 테스트 - Search Agent
"""


import pytest
import sys
sys.path.insert(0, ".")
from app.data_sources.region_codes import RegionCodeManager


class TestRegionCodeManager:
    """RegionCodeManager 테스트"""

    def setup_method(self):
        self.manager = RegionCodeManager()

    def test_get_gu_code(self):
        """구 코드 조회"""
        code = self.manager.get_sigungu_code("강서구")
        assert code == "11500"

        code = self.manager.get_sigungu_code("양천구")
        assert code == "11470"

    def test_get_gu_code_without_suffix(self):
        """'구' 없이 조회"""
        code = self.manager.get_sigungu_code("강서")
        assert code == "11500"

    def test_get_dong_code(self):
        """동 코드 조회"""
        code = self.manager.get_dong_code("목동")
        assert code == "1147010100"

    def test_get_codes_for_regions(self):
        """여러 지역 코드 조회"""
        regions = ["강서구", "양천구", "목동"]
        codes = self.manager.get_codes_for_regions(regions)

        assert len(codes) == 3
        assert "1150000000" in codes  # 강서구
        assert "1147000000" in codes  # 양천구
        assert "1147010100" in codes  # 목동


class TestNaverLandClient:
    """NaverLandClient 테스트 (실제 API 호출)"""

    @pytest.mark.skip(reason="실제 API 호출 - 필요시 활성화")
    def test_search_by_region(self):
        """지역 검색 테스트"""
        from app.data_sources.naver_land import NaverLandClient
        from app.schemas.user_input import UserInput

        user_input = UserInput(
            transaction_type="전세",
            max_deposit=50000,
            min_area_sqm=80,
        )

        with NaverLandClient() as client:
            listings = client.search_by_region(
                region_code="1147010100",  # 목동
                user_input=user_input,
                max_items=5,
            )

        assert len(listings) > 0
        assert listings[0].source == "네이버부동산"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
