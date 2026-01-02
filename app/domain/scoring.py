"""
점수화 엔진
규칙 기반으로 매물 점수를 산정합니다.
"""

from loguru import logger

from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.schemas.results import ScoredListing, ScoreBreakdown


class ScoringEngine:
    """
    규칙 기반 점수화 엔진

    각 카테고리별 점수를 산정하고 합산합니다.
    점수는 100점 만점으로 정규화됩니다.
    """

    # 카테고리별 가중치 (합계 100)
    WEIGHTS = {
        "price": 25,        # 가격 적정성
        "size": 15,         # 면적
        "complex": 20,      # 단지 규모/연식
        "location": 20,     # 위치/통근
        "options": 10,      # 옵션/편의
        "condition": 10,    # 상태/기타
    }

    def score(self, listing: Listing, user_input: UserInput) -> ScoredListing:
        """
        매물 점수를 산정합니다.

        Args:
            listing: 매물 정보
            user_input: 사용자 조건

        Returns:
            ScoredListing: 점수화된 매물
        """
        breakdowns = []

        # 각 카테고리별 점수 계산
        breakdowns.append(self._score_price(listing, user_input))
        breakdowns.append(self._score_size(listing, user_input))
        breakdowns.append(self._score_complex(listing, user_input))
        breakdowns.append(self._score_location(listing, user_input))
        breakdowns.append(self._score_options(listing, user_input))
        breakdowns.append(self._score_condition(listing, user_input))

        # 총점 계산
        total = sum(b.score for b in breakdowns)

        result = ScoredListing(
            listing_id=listing.id,
            listing=listing,
            total_score=round(total, 1),
            breakdown=breakdowns,
        )

        logger.debug(f"Score for {listing.id}: {total:.1f}")
        return result

    def _score_price(
        self, listing: Listing, user_input: UserInput
    ) -> ScoreBreakdown:
        """가격 점수: 예산 대비 저렴할수록 높음"""
        max_score = self.WEIGHTS["price"]

        if listing.deposit is None or user_input.max_deposit is None:
            return ScoreBreakdown(
                category="가격",
                score=max_score * 0.5,
                max_score=max_score,
                reason="가격 정보 부족으로 중간 점수 부여"
            )

        # 예산 대비 비율 (낮을수록 좋음)
        ratio = listing.deposit / user_input.max_deposit

        if ratio <= 0.7:
            score = max_score
            reason = f"예산의 {ratio*100:.0f}% (매우 저렴)"
        elif ratio <= 0.85:
            score = max_score * 0.9
            reason = f"예산의 {ratio*100:.0f}% (적정)"
        elif ratio <= 1.0:
            score = max_score * 0.7
            reason = f"예산의 {ratio*100:.0f}% (예산 근접)"
        else:
            score = max_score * 0.3
            reason = f"예산의 {ratio*100:.0f}% (예산 초과)"

        return ScoreBreakdown(
            category="가격",
            score=round(score, 1),
            max_score=max_score,
            reason=reason
        )

    def _score_size(
        self, listing: Listing, user_input: UserInput
    ) -> ScoreBreakdown:
        """면적 점수: 희망 면적에 가까울수록 높음"""
        max_score = self.WEIGHTS["size"]

        if listing.area_sqm is None:
            return ScoreBreakdown(
                category="면적",
                score=max_score * 0.5,
                max_score=max_score,
                reason="면적 정보 부족"
            )

        min_area = user_input.min_area_sqm or 0
        max_area = user_input.max_area_sqm or 200

        if listing.area_sqm < min_area:
            score = max_score * 0.3
            reason = f"{listing.area_sqm}㎡ (희망보다 좁음)"
        elif listing.area_sqm > max_area:
            score = max_score * 0.5
            reason = f"{listing.area_sqm}㎡ (희망보다 넓음)"
        else:
            # 범위 내에서 중간값에 가까울수록 높음
            score = max_score
            reason = f"{listing.area_sqm}㎡ (희망 범위 내)"

        return ScoreBreakdown(
            category="면적",
            score=round(score, 1),
            max_score=max_score,
            reason=reason
        )

    def _score_complex(
        self, listing: Listing, user_input: UserInput
    ) -> ScoreBreakdown:
        """단지 점수: 세대수, 연식, 주차 등"""
        max_score = self.WEIGHTS["complex"]
        score = 0
        reasons = []

        # 세대수 (40%)
        if listing.households:
            if listing.households >= 1500:
                score += max_score * 0.4
                reasons.append(f"{listing.households:,}세대 (대단지)")
            elif listing.households >= 1000:
                score += max_score * 0.35
                reasons.append(f"{listing.households:,}세대 (중대형)")
            elif listing.households >= 500:
                score += max_score * 0.25
                reasons.append(f"{listing.households:,}세대 (중형)")
            else:
                score += max_score * 0.1
                reasons.append(f"{listing.households:,}세대 (소형)")
        else:
            score += max_score * 0.15
            reasons.append("세대수 정보 없음")

        # 연식 (30%)
        if listing.built_year:
            age = 2025 - listing.built_year
            if age <= 5:
                score += max_score * 0.3
                reasons.append(f"{listing.built_year}년 준공 (신축)")
            elif age <= 10:
                score += max_score * 0.25
                reasons.append(f"{listing.built_year}년 준공 (준신축)")
            elif age <= 20:
                score += max_score * 0.15
                reasons.append(f"{listing.built_year}년 준공")
            else:
                score += max_score * 0.05
                reasons.append(f"{listing.built_year}년 준공 (노후)")

        # 주차 (30%)
        if listing.parking_per_household:
            if listing.parking_per_household >= 1.5:
                score += max_score * 0.3
                reasons.append(f"주차 {listing.parking_per_household}대/세대")
            elif listing.parking_per_household >= 1.0:
                score += max_score * 0.2
                reasons.append(f"주차 {listing.parking_per_household}대/세대")
            else:
                score += max_score * 0.1
                reasons.append(f"주차 {listing.parking_per_household}대/세대 (부족)")

        return ScoreBreakdown(
            category="단지",
            score=round(score, 1),
            max_score=max_score,
            reason=", ".join(reasons) if reasons else "정보 부족"
        )

    def _score_location(
        self, listing: Listing, user_input: UserInput
    ) -> ScoreBreakdown:
        """위치 점수: 통근, 역세권 등"""
        max_score = self.WEIGHTS["location"]
        score = max_score * 0.5  # 기본점
        reasons = []

        # 역 거리 (50%)
        if listing.station_distance_m is not None:
            if listing.station_distance_m <= 300:
                score = max_score * 0.5
                reasons.append(f"역 {listing.station_distance_m}m (초역세권)")
            elif listing.station_distance_m <= 500:
                score = max_score * 0.4
                reasons.append(f"역 {listing.station_distance_m}m (역세권)")
            elif listing.station_distance_m <= 1000:
                score = max_score * 0.25
                reasons.append(f"역 {listing.station_distance_m}m")
            else:
                score = max_score * 0.1
                reasons.append(f"역 {listing.station_distance_m}m (도보 어려움)")
        else:
            reasons.append("역 거리 정보 없음")

        # 지역 매칭 보너스 (추가 50%)
        if user_input.regions and listing.region_gu:
            if listing.region_gu in user_input.regions:
                score += max_score * 0.5
                reasons.append(f"{listing.region_gu} (희망지역)")

        return ScoreBreakdown(
            category="위치",
            score=min(round(score, 1), max_score),
            max_score=max_score,
            reason=", ".join(reasons) if reasons else "위치 정보 부족"
        )

    def _score_options(
        self, listing: Listing, user_input: UserInput
    ) -> ScoreBreakdown:
        """옵션 점수: 엘리베이터, 옵션 등"""
        max_score = self.WEIGHTS["options"]
        score = 0
        reasons = []

        # 엘리베이터
        if listing.has_elevator:
            score += max_score * 0.3
            reasons.append("엘리베이터 있음")

        # 옵션 개수
        if listing.options:
            option_score = min(len(listing.options) * 0.1, 0.5) * max_score
            score += option_score
            reasons.append(f"옵션 {len(listing.options)}개")

        # 층/향
        if listing.floor and listing.total_floors:
            floor_ratio = listing.floor / listing.total_floors
            if 0.3 <= floor_ratio <= 0.8:
                score += max_score * 0.2
                reasons.append(f"{listing.floor}/{listing.total_floors}층 (중층)")

        return ScoreBreakdown(
            category="옵션",
            score=min(round(score, 1), max_score),
            max_score=max_score,
            reason=", ".join(reasons) if reasons else "옵션 정보 없음"
        )

    def _score_condition(
        self, listing: Listing, user_input: UserInput
    ) -> ScoreBreakdown:
        """상태 점수: 매물 설명 기반 (추후 LLM 연동)"""
        max_score = self.WEIGHTS["condition"]

        # 기본 점수 (LLM 연동 전까지)
        score = max_score * 0.6
        reason = "상태 정보 분석 예정"

        # 간단한 키워드 체크
        if listing.description:
            desc = listing.description.lower()
            positive = ["올수리", "풀옵션", "깨끗", "신축", "리모델링"]
            negative = ["급매", "협의", "현상태"]

            for kw in positive:
                if kw in desc:
                    score = min(score + max_score * 0.1, max_score)
            for kw in negative:
                if kw in desc:
                    score = max(score - max_score * 0.1, 0)

        return ScoreBreakdown(
            category="상태",
            score=round(score, 1),
            max_score=max_score,
            reason=reason
        )
