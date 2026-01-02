"""
Commute Agent
필터 통과한 매물에 대해서만 통근 시간을 계산합니다.
(ODsay API 호출 최소화)
"""

from typing import Optional
from loguru import logger

from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.data_sources.odsay_api import ODsayClient, get_station_coords


class CommuteInput:
    """Commute Agent 입력"""
    def __init__(
        self,
        listings: list[Listing],
        destination: str,
        max_minutes: Optional[int] = None,
    ):
        self.listings = listings
        self.destination = destination
        self.max_minutes = max_minutes


class CommuteResult:
    """Commute Agent 출력"""
    def __init__(
        self,
        listing_id: str,
        commute_minutes: Optional[int],
        commute_info: Optional[dict],
        passed: bool,
    ):
        self.listing_id = listing_id
        self.commute_minutes = commute_minutes
        self.commute_info = commute_info
        self.passed = passed  # max_minutes 조건 통과 여부


class CommuteAgent(BaseAgent[CommuteInput, dict[str, CommuteResult]]):
    """
    통근 시간 계산 Agent
    
    ※ 필터 통과한 매물에 대해서만 실행 (ODsay API 절약)
    
    - 대중교통 기준 출퇴근 시간 계산
    - 매물 description에 통근 정보 추가
    - max_minutes 초과 시 탈락 처리 가능
    """
    
    name = "CommuteAgent"
    
    def _process(self, input_data: CommuteInput) -> dict[str, CommuteResult]:
        """통근 시간 계산 실행"""
        
        listings = input_data.listings
        destination = input_data.destination
        max_minutes = input_data.max_minutes
        
        if not listings:
            return {}
        
        # 목적지 좌표 조회
        dest_coords = get_station_coords(destination)
        if not dest_coords:
            self.logger.warning(f"Unknown destination: {destination}")
            return {}
        
        dest_lat = dest_coords["lat"]
        dest_lng = dest_coords["lng"]
        
        self.logger.info(f"Calculating commute to {destination} for {len(listings)} listings")
        
        results = {}
        
        with ODsayClient() as client:
            if not client.api_key:
                self.logger.warning("ODsay API 키가 없습니다. 통근 시간 계산 스킵.")
                return {}
            
            for listing in listings:
                result = self._calculate_commute(
                    listing=listing,
                    client=client,
                    dest_lat=dest_lat,
                    dest_lng=dest_lng,
                    destination_name=destination,
                    max_minutes=max_minutes,
                )
                results[listing.id] = result
        
        # 통계 출력
        calculated = sum(1 for r in results.values() if r.commute_minutes is not None)
        passed = sum(1 for r in results.values() if r.passed)
        self.logger.info(f"Commute calculated: {calculated}/{len(listings)}, passed: {passed}")
        
        return results
    
    def _calculate_commute(
        self,
        listing: Listing,
        client: ODsayClient,
        dest_lat: float,
        dest_lng: float,
        destination_name: str,
        max_minutes: Optional[int],
    ) -> CommuteResult:
        """개별 매물 통근 시간 계산"""
        
        # 좌표 없으면 계산 불가
        if not listing.latitude or not listing.longitude:
            return CommuteResult(
                listing_id=listing.id,
                commute_minutes=None,
                commute_info=None,
                passed=True,  # 좌표 없으면 일단 통과
            )
        
        try:
            commute_info = client.get_transit_route(
                start_lat=listing.latitude,
                start_lng=listing.longitude,
                end_lat=dest_lat,
                end_lng=dest_lng,
            )
            
            if not commute_info:
                return CommuteResult(
                    listing_id=listing.id,
                    commute_minutes=None,
                    commute_info=None,
                    passed=True,
                )
            
            commute_minutes = commute_info["total_time"]
            
            # description에 통근 정보 추가
            commute_note = f"\n\n[통근 정보] {destination_name}까지 "
            commute_note += f"약 {commute_minutes}분 "
            commute_note += f"({commute_info['path_type']}, 환승 {commute_info['transit_count']}회)"
            
            if max_minutes:
                if commute_minutes <= max_minutes:
                    commute_note += " ✅"
                else:
                    commute_note += f" ⚠️ ({max_minutes}분 초과)"
            
            listing.description = (listing.description or "") + commute_note
            
            # 조건 통과 여부
            passed = True
            if max_minutes:
                passed = commute_minutes <= max_minutes
            
            return CommuteResult(
                listing_id=listing.id,
                commute_minutes=commute_minutes,
                commute_info=commute_info,
                passed=passed,
            )
            
        except Exception as e:
            self.logger.warning(f"Commute calc failed for {listing.id}: {e}")
            return CommuteResult(
                listing_id=listing.id,
                commute_minutes=None,
                commute_info=None,
                passed=True,
            )
