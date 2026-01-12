"""
국토교통부 실거래가 API 클라이언트
공공데이터포털에서 제공하는 실거래가 API를 호출합니다.
- 전월세 실거래가
- 매매 실거래가
- 전세가율 계산

최적화:
- 지역별 실거래가 캐싱 (동일 지역 중복 호출 방지)
- API 호출 최소화
"""

from typing import Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta
from loguru import logger

from app.config import settings
import httpx
import xml.etree.ElementTree as ET


class MolitRealPriceClient:
    """
    국토교통부 실거래가 API 클라이언트 (캐싱 지원)

    필요한 API 신청:
    - 아파트 전월세: https://www.data.go.kr/data/15126474/openapi.do
    - 아파트 매매: https://www.data.go.kr/data/15126469/openapi.do

    환경변수:
    - DATA_GO_KR_API_KEY: 공공데이터포털 API 키
    """

    BASE_URL = settings.DATA_GO_KR_BASE_URL

    API_PATHS = {
        "apt_trade": "/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
        "apt_rent": "/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
        "offi_trade": "/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
        "offi_rent": "/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DATA_GO_KR_API_KEY
        self.client = httpx.Client(timeout=settings.DATA_GO_KR_TIMEOUT)
        self.logger = logger.bind(source="MolitAPI")

        # 캐시: {지역코드: {"rent": [...], "trade": [...]}}
        self._cache: dict[str, dict[str, list]] = {}

        if not self.api_key:
            self.logger.warning("API 키가 설정되지 않았습니다.")

    # ==================== 캐시 관리 ====================
    def _get_cached_data(self, sigungu_code: str, data_type: str) -> Optional[list]:
        """캐시된 데이터 조회"""
        if sigungu_code in self._cache:
            return self._cache[sigungu_code].get(data_type)
        return None

    def _set_cached_data(self, sigungu_code: str, data_type: str, data: list):
        """데이터 캐시 저장"""
        if sigungu_code not in self._cache:
            self._cache[sigungu_code] = {}
        self._cache[sigungu_code][data_type] = data

    def preload_region_data(self, sigungu_code: str, months: int = 3):
        """
        지역 데이터 미리 로드 (전세 + 매매)
        
        동일 지역 매물 여러 개 분석 시 한 번만 호출하면 됨
        """
        # 이미 캐시되어 있으면 스킵
        if sigungu_code in self._cache:
            return
        
        self.logger.info(f"Preloading data for region: {sigungu_code}")
        
        # 전세 데이터 로드
        rent_data = self._fetch_recent_prices(sigungu_code, months, "rent")
        self._set_cached_data(sigungu_code, "rent", rent_data)
        
        # 매매 데이터 로드
        trade_data = self._fetch_recent_prices(sigungu_code, months, "trade")
        self._set_cached_data(sigungu_code, "trade", trade_data)
        
        self.logger.info(f"Preloaded: {len(rent_data)} rent, {len(trade_data)} trade records")

    # ==================== API 호출 ====================
    def _fetch_prices(self, sigungu_code: str, year_month: str, price_type: str) -> list[dict]:
        """단일 월 실거래가 조회"""
        if not self.api_key:
            return []

        api_path = self.API_PATHS[f"apt_{price_type}"]
        url = f"{self.BASE_URL}{api_path}"
        params = {
            "serviceKey": self.api_key,
            "LAWD_CD": sigungu_code,
            "DEAL_YMD": year_month,
        }

        try:
            response = self.client.get(url, params=params)
            if response.status_code != 200:
                self.logger.error(f"API error: {response.status_code}")
                return []
            return self._parse_xml_response(response.text)
        except Exception as e:
            self.logger.error(f"API call failed: {e}")
            return []

    def _fetch_recent_prices(self, sigungu_code: str, months: int, price_type: str) -> list[dict]:
        """최근 N개월 실거래가 조회 (API 직접 호출)"""
        all_items = []
        current = datetime.now()

        for i in range(months):
            target = current - relativedelta(months=i)
            year_month = target.strftime("%Y%m")
            self.logger.debug(f"Fetching {price_type}: {sigungu_code}/{year_month}")
            items = self._fetch_prices(sigungu_code, year_month, price_type)
            all_items.extend(items)

        return all_items

    # ==================== 데이터 조회 (캐시 우선) ====================
    def get_recent_rent_prices(self, sigungu_code: str, months: int = 3) -> list[dict]:
        """최근 N개월 전월세 실거래가 (캐시 사용)"""
        cached = self._get_cached_data(sigungu_code, "rent")
        if cached is not None:
            return cached
        
        data = self._fetch_recent_prices(sigungu_code, months, "rent")
        self._set_cached_data(sigungu_code, "rent", data)
        return data

    def get_recent_trade_prices(self, sigungu_code: str, months: int = 3) -> list[dict]:
        """최근 N개월 매매 실거래가 (캐시 사용)"""
        cached = self._get_cached_data(sigungu_code, "trade")
        if cached is not None:
            return cached
        
        data = self._fetch_recent_prices(sigungu_code, months, "trade")
        self._set_cached_data(sigungu_code, "trade", data)
        return data

    # ==================== 단지별 분석 ====================
    def get_complex_rent_avg(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        months: int = 3,
    ) -> Optional[dict]:
        """특정 단지의 전세 평균 실거래가"""
        items = self.get_recent_rent_prices(sigungu_code, months)

        # 필터링: 단지명 + 면적 ±5㎡ + 전세만
        deposits = []
        for item in items:
            apt_name = item.get("aptNm", "") or item.get("아파트", "")
            if complex_name not in apt_name:
                continue

            item_area = float(item.get("excluUseAr", 0) or item.get("전용면적", 0) or 0)
            if abs(item_area - area_sqm) > 5:
                continue

            # 전세만 (월세 = 0)
            monthly = item.get("monthlyRent", "0") or item.get("월세금액", "0")
            if str(monthly).strip() not in ["", "0"]:
                continue

            deposit_str = item.get("deposit", "0") or item.get("보증금액", "0")
            deposit = int(str(deposit_str).replace(",", "").strip() or "0")
            if deposit > 0:
                deposits.append(deposit)

        if not deposits:
            return None

        return {
            "avg_deposit": sum(deposits) // len(deposits),
            "min_deposit": min(deposits),
            "max_deposit": max(deposits),
            "count": len(deposits),
        }

    def get_complex_trade_avg(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        months: int = 3,
    ) -> Optional[dict]:
        """특정 단지의 매매 평균 실거래가"""
        items = self.get_recent_trade_prices(sigungu_code, months)

        # 필터링: 단지명 + 면적 ±5㎡
        prices = []
        for item in items:
            apt_name = item.get("aptNm", "") or item.get("아파트", "")
            if complex_name not in apt_name:
                continue

            item_area = float(item.get("excluUseAr", 0) or item.get("전용면적", 0) or 0)
            if abs(item_area - area_sqm) > 5:
                continue

            price_str = item.get("dealAmount", "0") or item.get("거래금액", "0")
            price = int(str(price_str).replace(",", "").strip() or "0")
            if price > 0:
                prices.append(price)

        if not prices:
            return None

        return {
            "avg_price": sum(prices) // len(prices),
            "min_price": min(prices),
            "max_price": max(prices),
            "count": len(prices),
        }

    # ==================== 전세가율 ====================
    def get_complex_price_analysis(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        current_deposit: int,
        months: int = 3,
    ) -> Optional[dict]:
        """
        단지 종합 가격 분석 (최적화됨)
        
        - 캐시 사용으로 중복 API 호출 방지
        - 전세 분석 + 매매 분석 + 전세가율 한 번에
        """
        result = {
            "rent_analysis": None,
            "trade_analysis": None,
            "jeonse_ratio_analysis": None,
            "price_evaluation": None,
        }

        # 전세 분석
        rent_info = self.get_complex_rent_avg(sigungu_code, complex_name, area_sqm, months)
        if rent_info:
            result["rent_analysis"] = rent_info
            avg_rent = rent_info["avg_deposit"]
            if avg_rent > 0:
                diff_percent = ((current_deposit - avg_rent) / avg_rent) * 100
                if diff_percent < -5:
                    result["price_evaluation"] = "저렴"
                elif diff_percent > 5:
                    result["price_evaluation"] = "비쌈"
                else:
                    result["price_evaluation"] = "적정"

        # 매매 분석
        trade_info = self.get_complex_trade_avg(sigungu_code, complex_name, area_sqm, months)
        if trade_info:
            result["trade_analysis"] = trade_info

            # 전세가율 계산 (매매 데이터가 있을 때만)
            avg_trade = trade_info["avg_price"]
            if avg_trade > 0:
                jeonse_ratio = (current_deposit / avg_trade) * 100
                
                if jeonse_ratio <= 60:
                    risk_level = "안전"
                elif jeonse_ratio <= 70:
                    risk_level = "보통"
                elif jeonse_ratio <= 80:
                    risk_level = "주의"
                else:
                    risk_level = "위험"

                result["jeonse_ratio_analysis"] = {
                    "jeonse_ratio": round(jeonse_ratio, 1),
                    "avg_trade_price": avg_trade,
                    "avg_rent_deposit": rent_info["avg_deposit"] if rent_info else 0,
                    "current_deposit": current_deposit,
                    "risk_level": risk_level,
                    "trade_count": trade_info["count"],
                    "rent_count": rent_info["count"] if rent_info else 0,
                }

        return result

    # ==================== 헬퍼 ====================
    def _parse_xml_response(self, xml_text: str) -> list[dict]:
        """XML 응답 파싱"""
        items = []
        try:
            root = ET.fromstring(xml_text)

            result_code = root.find(".//resultCode")
            if result_code is not None and result_code.text not in ["00", "000"]:
                result_msg = root.find(".//resultMsg")
                self.logger.error(f"API error [{result_code.text}]: {result_msg.text if result_msg else 'Unknown'}")
                return []

            for item in root.findall(".//item"):
                item_dict = {}
                for child in item:
                    text = child.text.strip() if child.text else ""
                    item_dict[child.tag] = text
                items.append(item_dict)

        except ET.ParseError as e:
            self.logger.error(f"XML parse error: {e}")

        return items

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
