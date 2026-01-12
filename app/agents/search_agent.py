"""
Search Agent
조건에 맞는 매물을 자동으로 검색합니다.
"""

from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.data_sources.naver_land import NaverLandClient
from app.data_sources.region_codes import RegionCodeManager


class SearchAgent(BaseAgent[UserInput, list[Listing]]):
    """
    매물 검색 Agent
    """

    name = "SearchAgent"

    def __init__(self, max_items_per_region: int = 50):
        super().__init__()
        self.max_items_per_region = max_items_per_region
        self.region_manager = RegionCodeManager()

    def _process(self, user_input: UserInput) -> list[Listing]:
        """매물 검색 실행"""

        all_listings = []
        region_codes = self._get_region_codes(user_input)

        if not region_codes:
            return []

        with NaverLandClient() as client:
            for code in region_codes:
                try:
                    listings = client.search_by_region(
                        region_code=code,
                        user_input=user_input,
                        max_items=self.max_items_per_region,
                    )
                    all_listings.extend(listings)
                except Exception as e:
                    self.logger.error(f"검색 실패 ({code}): {e}")

        # ID 기준 중복 제거
        seen_ids = set()
        unique_listings = []
        for listing in all_listings:
            if listing.id not in seen_ids:
                seen_ids.add(listing.id)
                unique_listings.append(listing)

        return unique_listings

    def _get_region_codes(self, user_input: UserInput) -> list[str]:
        """사용자 입력에서 지역 코드 추출"""
        if not user_input.regions:
            return ["11500", "11470", "11560"]
        return self.region_manager.get_codes_for_regions(user_input.regions)
