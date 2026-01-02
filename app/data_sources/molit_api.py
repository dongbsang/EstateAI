"""
국토교통부 실거래가 API 클라이언트
공공데이터포털에서 제공하는 실거래가 API를 호출합니다.
- 전월세 실거래가
- 매매 실거래가
- 전세가율 계산
"""

import os
from typing import Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta
from loguru import logger
import httpx
import xml.etree.ElementTree as ET


class MolitRealPriceClient:
    """
    국토교통부 실거래가 API 클라이언트
    
    필요한 API 신청:
    - 아파트 전월세: https://www.data.go.kr/data/15126474/openapi.do
    - 아파트 매매: https://www.data.go.kr/data/15126469/openapi.do
    
    환경변수:
    - DATA_GO_KR_API_KEY: 공공데이터포털 API 키 (두 API 모두 같은 키 사용)
    """
    
    # API 엔드포인트
    BASE_URL = "http://openapi.molit.go.kr"
    
    # API 경로
    API_PATHS = {
        # 아파트
        "apt_trade": "/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev",  # 매매
        "apt_rent": "/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptRent",  # 전월세
        # 오피스텔
        "offi_trade": "/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcOffiTradeDev",
        "offi_rent": "/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcOffiRent",
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: 공공데이터포털 API 키 (없으면 환경변수에서 로드)
        """
        self.api_key = api_key or os.getenv("DATA_GO_KR_API_KEY", "")
        self.client = httpx.Client(timeout=30.0)
        self.logger = logger.bind(source="MolitAPI")
        
        if not self.api_key:
            self.logger.warning("API 키가 설정되지 않았습니다. DATA_GO_KR_API_KEY 환경변수를 설정하세요.")
    
    # ==================== 전월세 API ====================
    
    def get_apt_rent_prices(
        self,
        sigungu_code: str,
        year_month: str,
    ) -> list[dict]:
        """
        아파트 전월세 실거래가 조회
        
        Args:
            sigungu_code: 시군구 코드 (5자리, 예: "11110" 서울 종로구)
            year_month: 계약년월 (6자리, 예: "202401")
            
        Returns:
            실거래가 목록
        """
        if not self.api_key:
            return []
        
        self.logger.info(f"Fetching rent prices: {sigungu_code} / {year_month}")
        
        try:
            url = f"{self.BASE_URL}{self.API_PATHS['apt_rent']}"
            params = {
                "serviceKey": self.api_key,
                "LAWD_CD": sigungu_code,
                "DEAL_YMD": year_month,
            }
            
            response = self.client.get(url, params=params)
            
            if response.status_code != 200:
                self.logger.error(f"API error: {response.status_code}")
                return []
            
            items = self._parse_xml_response(response.text)
            self.logger.info(f"Found {len(items)} rent records")
            
            return items
            
        except Exception as e:
            self.logger.error(f"Rent API call failed: {e}")
            return []
    
    # ==================== 매매 API ====================
    
    def get_apt_trade_prices(
        self,
        sigungu_code: str,
        year_month: str,
    ) -> list[dict]:
        """
        아파트 매매 실거래가 조회
        
        Args:
            sigungu_code: 시군구 코드
            year_month: 계약년월
            
        Returns:
            매매 실거래가 목록
        """
        if not self.api_key:
            return []
        
        self.logger.info(f"Fetching trade prices: {sigungu_code} / {year_month}")
        
        try:
            url = f"{self.BASE_URL}{self.API_PATHS['apt_trade']}"
            params = {
                "serviceKey": self.api_key,
                "LAWD_CD": sigungu_code,
                "DEAL_YMD": year_month,
            }
            
            response = self.client.get(url, params=params)
            
            if response.status_code != 200:
                self.logger.error(f"API error: {response.status_code}")
                return []
            
            items = self._parse_xml_response(response.text)
            self.logger.info(f"Found {len(items)} trade records")
            
            return items
            
        except Exception as e:
            self.logger.error(f"Trade API call failed: {e}")
            return []
    
    # ==================== 기간 조회 ====================
    
    def get_recent_rent_prices(
        self,
        sigungu_code: str,
        months: int = 6,
    ) -> list[dict]:
        """최근 N개월 전월세 실거래가 조회"""
        return self._get_recent_prices(sigungu_code, months, "rent")
    
    def get_recent_trade_prices(
        self,
        sigungu_code: str,
        months: int = 6,
    ) -> list[dict]:
        """최근 N개월 매매 실거래가 조회"""
        return self._get_recent_prices(sigungu_code, months, "trade")
    
    def _get_recent_prices(
        self,
        sigungu_code: str,
        months: int,
        price_type: str,
    ) -> list[dict]:
        """최근 N개월 실거래가 조회"""
        all_items = []
        current = datetime.now()
        
        for i in range(months):
            target = current - relativedelta(months=i)
            year_month = target.strftime("%Y%m")
            
            if price_type == "rent":
                items = self.get_apt_rent_prices(sigungu_code, year_month)
            else:
                items = self.get_apt_trade_prices(sigungu_code, year_month)
            
            all_items.extend(items)
        
        return all_items
    
    # ==================== 단지별 분석 ====================
    
    def get_complex_rent_avg(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        months: int = 6,
    ) -> Optional[dict]:
        """
        특정 단지의 전월세 평균 실거래가 조회
        
        Returns:
            {
                "avg_deposit": 평균 전세보증금,
                "min_deposit": 최소,
                "max_deposit": 최대,
                "count": 거래 건수,
            }
        """
        items = self.get_recent_rent_prices(sigungu_code, months)
        
        # 필터링: 단지명 + 면적 ±5㎡ + 전세만
        filtered = []
        for item in items:
            apt_name = item.get("아파트", "") or item.get("aptNm", "")
            if complex_name not in apt_name:
                continue
            
            item_area = float(item.get("전용면적", 0) or item.get("excluUseAr", 0))
            if abs(item_area - area_sqm) > 5:
                continue
            
            # 전세만 (월세금액 = 0)
            monthly = item.get("월세금액", "0") or item.get("monthlyRent", "0")
            if str(monthly).strip() not in ["", "0"]:
                continue
            
            filtered.append(item)
        
        if not filtered:
            return None
        
        # 보증금 추출
        deposits = []
        for item in filtered:
            deposit_str = item.get("보증금액", "0") or item.get("deposit", "0")
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
        months: int = 6,
    ) -> Optional[dict]:
        """
        특정 단지의 매매 평균 실거래가 조회
        
        Returns:
            {
                "avg_price": 평균 매매가,
                "min_price": 최소,
                "max_price": 최대,
                "count": 거래 건수,
            }
        """
        items = self.get_recent_trade_prices(sigungu_code, months)
        
        # 필터링: 단지명 + 면적 ±5㎡
        filtered = []
        for item in items:
            apt_name = item.get("아파트", "") or item.get("aptNm", "")
            if complex_name not in apt_name:
                continue
            
            item_area = float(item.get("전용면적", 0) or item.get("excluUseAr", 0))
            if abs(item_area - area_sqm) > 5:
                continue
            
            filtered.append(item)
        
        if not filtered:
            return None
        
        # 거래금액 추출
        prices = []
        for item in filtered:
            price_str = item.get("거래금액", "0") or item.get("dealAmount", "0")
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
    
    # ==================== 전세가율 계산 ====================
    
    def calculate_jeonse_ratio(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        current_deposit: int,
        months: int = 6,
    ) -> Optional[dict]:
        """
        전세가율 계산
        
        전세가율 = (전세가 / 매매가) × 100%
        
        Args:
            sigungu_code: 시군구 코드
            complex_name: 단지명
            area_sqm: 전용면적
            current_deposit: 현재 전세 보증금 (만원)
            months: 조회 개월 수
            
        Returns:
            {
                "jeonse_ratio": 전세가율 (%),
                "avg_trade_price": 평균 매매가,
                "avg_rent_deposit": 평균 전세가,
                "current_deposit": 현재 매물 보증금,
                "risk_level": "안전" | "보통" | "주의" | "위험",
                "trade_count": 매매 거래 건수,
                "rent_count": 전세 거래 건수,
            }
        """
        # 매매 평균가 조회
        trade_info = self.get_complex_trade_avg(sigungu_code, complex_name, area_sqm, months)
        
        if not trade_info or trade_info["avg_price"] == 0:
            self.logger.warning(f"No trade data for {complex_name}")
            return None
        
        avg_trade = trade_info["avg_price"]
        
        # 전세 평균가 조회 (참고용)
        rent_info = self.get_complex_rent_avg(sigungu_code, complex_name, area_sqm, months)
        avg_rent = rent_info["avg_deposit"] if rent_info else 0
        
        # 전세가율 계산 (현재 매물 기준)
        jeonse_ratio = (current_deposit / avg_trade) * 100
        
        # 리스크 레벨 판정
        if jeonse_ratio <= 60:
            risk_level = "안전"
        elif jeonse_ratio <= 70:
            risk_level = "보통"
        elif jeonse_ratio <= 80:
            risk_level = "주의"
        else:
            risk_level = "위험"
        
        return {
            "jeonse_ratio": round(jeonse_ratio, 1),
            "avg_trade_price": avg_trade,
            "avg_rent_deposit": avg_rent,
            "current_deposit": current_deposit,
            "risk_level": risk_level,
            "trade_count": trade_info["count"],
            "rent_count": rent_info["count"] if rent_info else 0,
        }
    
    # ==================== 통합 분석 ====================
    
    def get_complex_price_analysis(
        self,
        sigungu_code: str,
        complex_name: str,
        area_sqm: float,
        current_deposit: int,
        months: int = 6,
    ) -> Optional[dict]:
        """
        단지 종합 가격 분석
        
        Returns:
            {
                "rent_analysis": 전세 분석,
                "trade_analysis": 매매 분석,
                "jeonse_ratio": 전세가율 분석,
                "price_evaluation": 가격 평가 ("저렴" | "적정" | "비쌈"),
            }
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
            
            # 가격 평가
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
        
        # 전세가율 분석
        if trade_info and trade_info["avg_price"] > 0:
            jeonse_analysis = self.calculate_jeonse_ratio(
                sigungu_code, complex_name, area_sqm, current_deposit, months
            )
            result["jeonse_ratio_analysis"] = jeonse_analysis
        
        return result
    
    # ==================== 헬퍼 ====================
    
    def _parse_xml_response(self, xml_text: str) -> list[dict]:
        """XML 응답 파싱"""
        items = []
        
        try:
            root = ET.fromstring(xml_text)
            
            # 에러 체크
            result_code = root.find(".//resultCode")
            if result_code is not None and result_code.text != "00":
                result_msg = root.find(".//resultMsg")
                self.logger.error(f"API error: {result_msg.text if result_msg else 'Unknown'}")
                return []
            
            # 아이템 추출
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
        """클라이언트 종료"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
