"""
필터 엔진
규칙 기반으로 매물을 필터링합니다.
"""

from typing import Callable
from loguru import logger

from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.schemas.results import FilterResult, FilterStatus


class FilterEngine:
    """
    규칙 기반 필터 엔진

    사용자 조건에 따라 매물을 필터링하고,
    각 조건별 통과/탈락 여부와 근거를 반환합니다.
    """

    def __init__(self):
        # 필터 함수 레지스트리: 필드명 -> (체크함수, 실패메시지 포맷)
        self._filters: dict[str, Callable] = {
            "max_deposit": self._check_max_deposit,
            "max_monthly_rent": self._check_max_monthly_rent,
            "max_maintenance_fee": self._check_max_maintenance_fee,
            "min_area_sqm": self._check_min_area,
            "max_area_sqm": self._check_max_area,
            "min_households": self._check_min_households,
            "min_built_year": self._check_min_built_year,
            "max_built_year": self._check_max_built_year,
            "min_floor": self._check_min_floor,
            "max_floor": self._check_max_floor,
            "require_parking": self._check_parking,
            "require_elevator": self._check_elevator,
            "regions": self._check_regions,
            "property_types": self._check_property_types,
        }

    def filter(self, listing: Listing, user_input: UserInput) -> FilterResult:
        """
        매물을 사용자 조건으로 필터링합니다.

        Args:
            listing: 매물 정보
            user_input: 사용자 입력 조건

        Returns:
            FilterResult: 필터링 결과 (통과/탈락 여부, 근거)
        """
        passed = []
        failed = []
        failure_reasons = {}

        # 각 필터 체크
        for field_name, check_func in self._filters.items():
            condition_value = getattr(user_input, field_name, None)

            # 조건이 설정되지 않았으면 스킵
            if condition_value is None:
                continue
            if isinstance(condition_value, list) and len(condition_value) == 0:
                continue
            if isinstance(condition_value, bool) and not condition_value:
                continue

            # 필터 체크 실행
            is_pass, reason = check_func(listing, condition_value)

            if is_pass:
                passed.append(field_name)
            else:
                failed.append(field_name)
                failure_reasons[field_name] = reason

        # 최종 상태 결정
        # must_conditions에 있는 조건이 실패하면 탈락
        must_failed = [f for f in failed if f in user_input.must_conditions]

        if must_failed:
            status = FilterStatus.FAIL
        elif failed:
            status = FilterStatus.PARTIAL
        else:
            status = FilterStatus.PASS

        result = FilterResult(
            listing_id=listing.id,
            status=status,
            passed_conditions=passed,
            failed_conditions=failed,
            failure_reasons=failure_reasons,
        )

        logger.debug(f"Filter result for {listing.id}: {status}")
        return result

    # === 개별 필터 함수들 ===

    def _check_max_deposit(
        self, listing: Listing, max_val: int
    ) -> tuple[bool, str]:
        if listing.deposit is None:
            return True, ""  # 정보 없으면 통과 (보수적)
        if listing.deposit <= max_val:
            return True, ""
        return False, f"보증금 {listing.deposit:,}만원 > 상한 {max_val:,}만원"

    def _check_max_monthly_rent(
        self, listing: Listing, max_val: int
    ) -> tuple[bool, str]:
        if listing.monthly_rent is None:
            return True, ""
        if listing.monthly_rent <= max_val:
            return True, ""
        return False, f"월세 {listing.monthly_rent:,}만원 > 상한 {max_val:,}만원"

    def _check_max_maintenance_fee(
        self, listing: Listing, max_val: int
    ) -> tuple[bool, str]:
        if listing.maintenance_fee is None:
            return True, ""
        if listing.maintenance_fee <= max_val:
            return True, ""
        return False, f"관리비 {listing.maintenance_fee:,}만원 > 상한 {max_val:,}만원"

    def _check_min_area(
        self, listing: Listing, min_val: float
    ) -> tuple[bool, str]:
        if listing.area_sqm is None:
            return False, "전용면적 정보 없음"
        if listing.area_sqm >= min_val:
            return True, ""
        return False, f"전용면적 {listing.area_sqm}㎡ < 최소 {min_val}㎡"

    def _check_max_area(
        self, listing: Listing, max_val: float
    ) -> tuple[bool, str]:
        if listing.area_sqm is None:
            return True, ""
        if listing.area_sqm <= max_val:
            return True, ""
        return False, f"전용면적 {listing.area_sqm}㎡ > 최대 {max_val}㎡"

    def _check_min_households(
        self, listing: Listing, min_val: int
    ) -> tuple[bool, str]:
        if listing.households is None:
            return False, "세대수 정보 없음"
        if listing.households >= min_val:
            return True, ""
        return False, f"세대수 {listing.households:,} < 최소 {min_val:,}"

    def _check_min_built_year(
        self, listing: Listing, min_val: int
    ) -> tuple[bool, str]:
        if listing.built_year is None:
            return False, "준공연도 정보 없음"
        if listing.built_year >= min_val:
            return True, ""
        return False, f"준공연도 {listing.built_year}년 < 최소 {min_val}년"

    def _check_max_built_year(
        self, listing: Listing, max_val: int
    ) -> tuple[bool, str]:
        if listing.built_year is None:
            return True, ""
        if listing.built_year <= max_val:
            return True, ""
        return False, f"준공연도 {listing.built_year}년 > 최대 {max_val}년"

    def _check_min_floor(
        self, listing: Listing, min_val: int
    ) -> tuple[bool, str]:
        if listing.floor is None:
            return False, "층수 정보 없음"
        if listing.floor >= min_val:
            return True, ""
        return False, f"{listing.floor}층 < 최소 {min_val}층"

    def _check_max_floor(
        self, listing: Listing, max_val: int
    ) -> tuple[bool, str]:
        if listing.floor is None:
            return True, ""
        if listing.floor <= max_val:
            return True, ""
        return False, f"{listing.floor}층 > 최대 {max_val}층"

    def _check_parking(
        self, listing: Listing, required: bool
    ) -> tuple[bool, str]:
        if not required:
            return True, ""
        if listing.has_parking is True:
            return True, ""
        if listing.parking_per_household and listing.parking_per_household > 0:
            return True, ""
        return False, "주차 불가 또는 정보 없음"

    def _check_elevator(
        self, listing: Listing, required: bool
    ) -> tuple[bool, str]:
        if not required:
            return True, ""
        if listing.has_elevator is True:
            return True, ""
        return False, "엘리베이터 없음 또는 정보 없음"

    def _check_regions(
        self, listing: Listing, regions: list[str]
    ) -> tuple[bool, str]:
        if not regions:
            return True, ""

        # 주소에서 구/동 매칭
        listing_regions = []
        if listing.region_gu:
            listing_regions.append(listing.region_gu)
        if listing.region_dong:
            listing_regions.append(listing.region_dong)
        if listing.address:
            listing_regions.append(listing.address)

        listing_text = " ".join(listing_regions).lower()

        for region in regions:
            if region.lower() in listing_text:
                return True, ""

        return False, f"지역 불일치 (희망: {regions})"

    def _check_property_types(
        self, listing: Listing, types: list[str]
    ) -> tuple[bool, str]:
        if not types:
            return True, ""
        if listing.property_type is None:
            return False, "주택유형 정보 없음"

        # 주택유형 매칭 (값 또는 enum 값)
        listing_type = listing.property_type.lower()
        for t in types:
            t_lower = t.lower() if isinstance(t, str) else t.value.lower()
            if t_lower in listing_type or listing_type in t_lower:
                return True, ""

        return False, f"주택유형 불일치 (희망: {types}, 실제: {listing.property_type})"
