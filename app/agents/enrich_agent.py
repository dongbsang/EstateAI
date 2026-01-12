"""
Enrich Agent
실거래가, 전세가율 등 추가 데이터로 매물 정보를 보강합니다.

거래 유형별 분석:
- 전세: 전세가율 계산 (전세 + 매매 실거래가 필요)
- 월세: API 호출 생략 (보증금 낮아 리스크 낮음)
- 매매: 시세 대비 적정가 판단 (매매 실거래가만 필요)

최적화:
- 지역별 실거래가 미리 로드 (중복 API 호출 방지)
"""

import os
from typing import Optional
from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.data_sources.molit_api import MolitRealPriceClient
from app.data_sources.region_codes import RegionCodeManager


class EnrichInput:
    def __init__(self, listings: list[Listing], user_input: Optional[UserInput] = None):
        self.listings = listings
        self.user_input = user_input


class EnrichAgent(BaseAgent[EnrichInput, list[Listing]]):
    name = "EnrichAgent"

    def __init__(self):
        super().__init__()
        self.region_manager = RegionCodeManager()

    def _process(self, input_data: EnrichInput) -> list[Listing]:
        listings = input_data.listings
        user_input = input_data.user_input
        
        if not listings:
            return []
        
        # 거래 유형 확인
        transaction_type = "전세"
        if user_input:
            transaction_type = user_input.transaction_type
        
        # 월세는 실거래가 분석 스킵
        if transaction_type == "월세":
            print("\n" + "-" * 50)
            print("📊 공공데이터 API 분석")
            print("-" * 50)
            print("⏭️ 월세 거래 - 전세가율 분석 불필요 (스킵)")
            print("-" * 50)
            return listings
        
        self._enrich_price_analysis(listings, transaction_type)
        return listings

    def _enrich_price_analysis(self, listings: list[Listing], transaction_type: str):
        """거래 유형별 실거래가 분석 (최적화됨)"""
        api_key = os.getenv("DATA_GO_KR_API_KEY", "")

        print("\n" + "-" * 50)
        if transaction_type == "전세":
            print("📊 공공데이터 API (전세가율 분석)")
        else:
            print("📊 공공데이터 API (매매 시세 분석)")
        print("-" * 50)

        if not api_key:
            print("⏭️ API 키 없음 - 실거래가 분석 스킵")
            print("-" * 50)
            return

        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"🔑 API 키: {masked_key}")

        with MolitRealPriceClient() as client:
            if not client.api_key:
                return

            # 1. 지역별로 그룹핑
            region_listings = self._group_by_region(listings)
            print(f"📍 분석 대상: {len(region_listings)}개 지역, {len(listings)}개 매물")

            # 2. 지역별로 데이터 미리 로드 (핵심 최적화!)
            print("⏳ 실거래가 데이터 로딩 중...")
            for sigungu_code in region_listings.keys():
                client.preload_region_data(sigungu_code, months=3)
            print("✅ 데이터 로딩 완료")

            # 3. 매물별 분석
            success_count = 0
            skip_count = 0
            error_count = 0

            for listing in listings:
                try:
                    if transaction_type == "전세":
                        result = self._add_jeonse_analysis(listing, client)
                    else:
                        result = self._add_trade_analysis(listing, client)
                    
                    if result:
                        success_count += 1
                    else:
                        skip_count += 1
                except Exception:
                    error_count += 1

            print(f"📈 결과: 성공 {success_count}건 | 스킵 {skip_count}건 | 오류 {error_count}건")
            print("-" * 50)

    def _group_by_region(self, listings: list[Listing]) -> dict[str, list[Listing]]:
        """매물을 지역별로 그룹핑"""
        groups = {}
        for listing in listings:
            if not listing.region_gu:
                continue
            sigungu_code = self.region_manager.get_sigungu_code(listing.region_gu)
            if not sigungu_code:
                continue
            if sigungu_code not in groups:
                groups[sigungu_code] = []
            groups[sigungu_code].append(listing)
        return groups

    def _add_jeonse_analysis(self, listing: Listing, client: MolitRealPriceClient) -> bool:
        """전세 분석: 전세가율 계산"""
        if not listing.region_gu:
            return False

        sigungu_code = self.region_manager.get_sigungu_code(listing.region_gu)
        if not sigungu_code:
            return False

        complex_name = listing.complex_name or listing.title or ""
        if not complex_name:
            return False

        area = listing.area_sqm or 84.0
        current_deposit = listing.deposit or 0
        if current_deposit == 0:
            return False

        analysis = client.get_complex_price_analysis(
            sigungu_code=sigungu_code,
            complex_name=complex_name,
            area_sqm=area,
            current_deposit=current_deposit,
            months=3,
        )
        if not analysis:
            return False

        notes = []
        
        # 전세 시세
        rent_analysis = analysis.get("rent_analysis")
        if rent_analysis:
            avg_rent = rent_analysis["avg_deposit"]
            diff_percent = ((current_deposit - avg_rent) / avg_rent) * 100 if avg_rent > 0 else 0
            note = f"[전세 시세] 최근 3개월 평균: {avg_rent:,}만원"
            if diff_percent < -5:
                note += f" → 현재 매물 {abs(diff_percent):.1f}% 저렴"
            elif diff_percent > 5:
                note += f" → 현재 매물 {diff_percent:.1f}% 비쌈"
            else:
                note += " → 시세 수준"
            notes.append(note)

        # 매매 시세
        trade_analysis = analysis.get("trade_analysis")
        if trade_analysis:
            avg_trade = trade_analysis["avg_price"]
            notes.append(f"[매매 시세] 최근 3개월 평균: {avg_trade:,}만원")

        # 전세가율
        jeonse_analysis = analysis.get("jeonse_ratio_analysis")
        if jeonse_analysis:
            ratio = jeonse_analysis["jeonse_ratio"]
            risk = jeonse_analysis["risk_level"]
            note = f"[전세가율] {ratio:.1f}% ({risk})"
            if risk == "위험":
                note += " ⚠️ 깡통전세 위험!"
            elif risk == "주의":
                note += " ⚠️ 주의 필요"
            notes.append(note)

        if notes:
            price_note = "\n\n" + "\n".join(notes)
            listing.description = (listing.description or "") + price_note
            return True

        return False

    def _add_trade_analysis(self, listing: Listing, client: MolitRealPriceClient) -> bool:
        """매매 분석: 시세 대비 적정가 판단"""
        if not listing.region_gu:
            return False

        sigungu_code = self.region_manager.get_sigungu_code(listing.region_gu)
        if not sigungu_code:
            return False

        complex_name = listing.complex_name or listing.title or ""
        if not complex_name:
            return False

        area = listing.area_sqm or 84.0
        current_price = listing.deposit or 0
        if current_price == 0:
            return False

        trade_info = client.get_complex_trade_avg(
            sigungu_code=sigungu_code,
            complex_name=complex_name,
            area_sqm=area,
            months=3,
        )
        
        if not trade_info:
            return False

        notes = []
        
        avg_trade = trade_info["avg_price"]
        min_trade = trade_info["min_price"]
        max_trade = trade_info["max_price"]
        count = trade_info["count"]
        
        diff_percent = ((current_price - avg_trade) / avg_trade) * 100 if avg_trade > 0 else 0
        
        notes.append(f"[매매 시세] 최근 3개월 평균: {avg_trade:,}만원 (거래 {count}건)")
        notes.append(f"[시세 범위] {min_trade:,}만원 ~ {max_trade:,}만원")
        
        if diff_percent < -10:
            evaluation, emoji = "매우 저렴", "🟢"
        elif diff_percent < -5:
            evaluation, emoji = "저렴", "🟢"
        elif diff_percent <= 5:
            evaluation, emoji = "적정", "🟡"
        elif diff_percent <= 10:
            evaluation, emoji = "다소 비쌈", "🟠"
        else:
            evaluation, emoji = "비쌈", "🔴"
        
        notes.append(f"[가격 평가] {emoji} {evaluation} (시세 대비 {diff_percent:+.1f}%)")

        if notes:
            price_note = "\n\n" + "\n".join(notes)
            listing.description = (listing.description or "") + price_note
            return True

        return False
