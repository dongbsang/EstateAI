"""
Enrich Agent
실거래가, 전세가율 등 추가 데이터로 매물 정보를 보강합니다.

※ 단지 정보(세대수, 준공연도)는 SearchAgent에서 이미 추가됨
"""

from typing import Optional
from loguru import logger

from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.data_sources.molit_api import MolitRealPriceClient
from app.data_sources.region_codes import RegionCodeManager


class EnrichInput:
    """Enrich Agent 입력"""
    def __init__(
        self,
        listings: list[Listing],
        user_input: Optional[UserInput] = None,
    ):
        self.listings = listings
        self.user_input = user_input


class EnrichAgent(BaseAgent[EnrichInput, list[Listing]]):
    """
    데이터 보강 Agent
    
    매물 정보에 추가 데이터를 병합합니다:
    - 국토부 실거래가 (전세/매매)
    - 전세가율 분석 (깡통전세 위험도)
    
    ※ 단지 정보(세대수, 준공연도)는 SearchAgent에서 이미 추가됨
    ※ 통근 시간은 CommuteAgent에서 별도 처리 (필터 통과 후)
    """
    
    name = "EnrichAgent"
    
    def __init__(self):
        super().__init__()
        self.region_manager = RegionCodeManager()
    
    def _process(self, input_data: EnrichInput) -> list[Listing]:
        """데이터 보강 실행"""
        
        listings = input_data.listings
        
        if not listings:
            return []
        
        self.logger.info(f"Enriching {len(listings)} listings")
        
        # 실거래가 + 전세가율 분석 (API 키 있는 경우)
        self._enrich_price_analysis(listings)
        
        return listings
    
    def _enrich_price_analysis(self, listings: list[Listing]):
        """실거래가 + 전세가율 분석"""
        with MolitRealPriceClient() as client:
            if not client.api_key:
                self.logger.info("Skipping price analysis (no API key)")
                return
            
            self.logger.info("Enriching with price analysis (rent + trade + jeonse ratio)...")
            
            for listing in listings:
                try:
                    self._add_price_analysis(listing, client)
                except Exception as e:
                    self.logger.warning(f"Price analysis failed for {listing.id}: {e}")
    
    def _add_price_analysis(
        self,
        listing: Listing,
        client: MolitRealPriceClient,
    ):
        """개별 매물에 가격 분석 추가"""
        # 필수 정보 체크
        if not listing.region_gu:
            return
        
        sigungu_code = self.region_manager.get_sigungu_code(listing.region_gu)
        if not sigungu_code:
            return
        
        complex_name = listing.complex_name or listing.title or ""
        if not complex_name:
            return
        
        area = listing.area_sqm or 84.0
        current_deposit = listing.deposit or 0
        
        if current_deposit == 0:
            return
        
        # 종합 가격 분석
        analysis = client.get_complex_price_analysis(
            sigungu_code=sigungu_code,
            complex_name=complex_name,
            area_sqm=area,
            current_deposit=current_deposit,
            months=6,
        )
        
        if not analysis:
            return
        
        # description에 분석 결과 추가
        notes = []
        
        # 전세 시세 비교
        rent_analysis = analysis.get("rent_analysis")
        if rent_analysis:
            avg_rent = rent_analysis["avg_deposit"]
            diff_percent = ((current_deposit - avg_rent) / avg_rent) * 100 if avg_rent > 0 else 0
            
            note = f"[전세 시세] 최근 6개월 평균: {avg_rent:,}만원"
            if diff_percent < -5:
                note += f" → 현재 매물 {abs(diff_percent):.1f}% 저렴 ✅"
            elif diff_percent > 5:
                note += f" → 현재 매물 {diff_percent:.1f}% 비쌈 ⚠️"
            else:
                note += f" → 시세 수준"
            notes.append(note)
        
        # 매매 시세
        trade_analysis = analysis.get("trade_analysis")
        if trade_analysis:
            avg_trade = trade_analysis["avg_price"]
            notes.append(f"[매매 시세] 최근 6개월 평균: {avg_trade:,}만원")
        
        # 전세가율 (핵심!)
        jeonse_analysis = analysis.get("jeonse_ratio_analysis")
        if jeonse_analysis:
            ratio = jeonse_analysis["jeonse_ratio"]
            risk = jeonse_analysis["risk_level"]
            
            risk_emoji = {
                "안전": "🟢",
                "보통": "🟡", 
                "주의": "🟠",
                "위험": "🔴",
            }.get(risk, "⚪")
            
            note = f"[전세가율] {ratio:.1f}% {risk_emoji} {risk}"
            
            if risk == "위험":
                note += " ⚠️ 깡통전세 위험!"
            elif risk == "주의":
                note += " (주의 필요)"
            
            notes.append(note)
        
        # description 업데이트
        if notes:
            price_note = "\n\n" + "\n".join(notes)
            listing.description = (listing.description or "") + price_note
