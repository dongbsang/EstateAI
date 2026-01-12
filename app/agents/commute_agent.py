"""
Commute Agent
필터 통과한 매물에 대해서만 통근 시간을 계산합니다.
"""

from typing import Optional
from .base import BaseAgent
from app.schemas.listing import Listing
from app.data_sources.odsay_api import ODsayClient, get_station_coords


class CommuteInput:
    def __init__(self, listings: list[Listing], destination: str, max_minutes: Optional[int] = None):
        self.listings = listings
        self.destination = destination
        self.max_minutes = max_minutes


class CommuteResult:
    def __init__(self, listing_id: str, commute_minutes: Optional[int], commute_info: Optional[dict], passed: bool):
        self.listing_id = listing_id
        self.commute_minutes = commute_minutes
        self.commute_info = commute_info
        self.passed = passed


class CommuteAgent(BaseAgent[CommuteInput, dict[str, CommuteResult]]):
    name = "CommuteAgent"

    def _process(self, input_data: CommuteInput) -> dict[str, CommuteResult]:
        listings = input_data.listings
        destination = input_data.destination
        max_minutes = input_data.max_minutes

        if not listings:
            return {}

        dest_coords = get_station_coords(destination)
        if not dest_coords:
            return {}

        dest_lat = dest_coords["lat"]
        dest_lng = dest_coords["lng"]

        results = {}

        with ODsayClient() as client:
            if not client.api_key:
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
        if not listing.latitude or not listing.longitude:
            return CommuteResult(listing.id, None, None, True)

        try:
            commute_info = client.get_transit_route(
                start_lat=listing.latitude,
                start_lng=listing.longitude,
                end_lat=dest_lat,
                end_lng=dest_lng,
            )

            if not commute_info:
                return CommuteResult(listing.id, None, None, True)

            commute_minutes = commute_info["total_time"]

            commute_note = f"\n\n[통근 정보] {destination_name}까지 "
            commute_note += f"약 {commute_minutes}분 "
            commute_note += f"({commute_info['path_type']}, 환승 {commute_info['transit_count']}회)"

            if max_minutes:
                if commute_minutes <= max_minutes:
                    commute_note += " ✓"
                else:
                    commute_note += f" ✗ ({max_minutes}분 초과)"

            listing.description = (listing.description or "") + commute_note

            passed = True
            if max_minutes:
                passed = commute_minutes <= max_minutes

            return CommuteResult(listing.id, commute_minutes, commute_info, passed)

        except Exception:
            return CommuteResult(listing.id, None, None, True)
