"""
Search Agent
조건에 맞는 매물을 자동으로 검색합니다.
"""

from typing import Optional
from loguru import logger

from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.data_sources.naver_land import NaverLandClient
from app.data_sources.region_codes import RegionCodeManager


class SearchAgent(BaseAgent[UserInput, list[Listing]]):
    """
    매물 검색 Agent
    
    사용자 조건을 받아서 네이버 부동산에서 매물을 자동 수집합니다.
    - 지역 조건에 따라 여러 지역 검색
    - 가격, 면적, 세대수 등 조건 적용
    - API 호출 속도 제한 준수
    """
    
    name = "SearchAgent"
    
    def __init__(self, max_items_per_region: int = 50):
        super().__init__()
        self.max_items_per_region = max_items_per_region
        self.region_manager = RegionCodeManager()
    
    def _process(self, user_input: UserInput) -> list[Listing]:
        """매물 검색 실행"""
        
        all_listings = []
        
        # 지역 코드 변환 (5자리 시군구 코드)
        region_codes = self._get_region_codes(user_input)
        
        if not region_codes:
            self.logger.warning("검색할 지역이 없습니다.")
            return []
        
        self.logger.info(f"Searching {len(region_codes)} regions: {region_codes}")
        
        # 네이버 부동산 API로 검색
        with NaverLandClient() as client:
            for code in region_codes:
                try:
                    listings = client.search_by_region(
                        region_code=code,
                        user_input=user_input,
                        max_items=self.max_items_per_region,
                    )
                    all_listings.extend(listings)
                    self.logger.info(f"Region {code}: {len(listings)} listings")
                    
                except Exception as e:
                    self.logger.error(f"Search failed for {code}: {e}")
        
        # 중복 제거 (ID 기준)
        seen_ids = set()
        unique_listings = []
        for listing in all_listings:
            if listing.id not in seen_ids:
                seen_ids.add(listing.id)
                unique_listings.append(listing)
        
        self.logger.info(f"Total unique listings: {len(unique_listings)}")
        
        return unique_listings
    
    def _get_region_codes(self, user_input: UserInput) -> list[str]:
        """사용자 입력에서 지역 코드 추출 (5자리 시군구 코드)"""
        
        if not user_input.regions:
            # 기본 지역: 서울 일부
            self.logger.info("No regions specified, using default regions")
            return ["11500", "11470", "11560"]  # 강서, 양천, 영등포
        
        return self.region_manager.get_codes_for_regions(user_input.regions)
