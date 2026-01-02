"""
네이버 부동산 API 클라이언트 (안전 모드)
- 요청 딜레이 (2-3초)
- 차단 감지 (429/403)
- 캐시 (24시간)
"""

import time
import random
import re
from typing import Optional
from datetime import datetime
from loguru import logger
import httpx

from app.schemas.listing import Listing, ListingSource
from app.schemas.user_input import UserInput
from app.data_sources.cache_manager import get_cache_manager


class BlockedError(Exception):
    """API 차단 감지 예외"""
    pass


class NaverLandClient:
    """
    네이버 부동산 API 클라이언트 (안전 모드)
    
    안전 장치:
    - 요청 간 2-3초 딜레이
    - 429/403 차단 감지 시 즉시 중단
    - 24시간 캐시로 중복 요청 방지
    """
    
    MOBILE_URL = "https://m.land.naver.com"
    
    PROPERTY_TYPE_CODES = {
        "아파트": "APT",
        "오피스텔": "OPST",
        "빌라": "VL",
        "원룸": "OR",
    }
    
    TRADE_TYPE_CODES = {
        "매매": "A1",
        "전세": "B1",
        "월세": "B2",
    }
    
    DEFAULT_HEADERS = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://m.land.naver.com/",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    }
    
    REGION_COORDS = {
        "11500": {"lat": 37.5509, "lng": 126.8495, "name": "강서구"},
        "11470": {"lat": 37.5270, "lng": 126.8561, "name": "양천구"},
        "11560": {"lat": 37.5263, "lng": 126.8963, "name": "영등포구"},
        "11440": {"lat": 37.5538, "lng": 126.9084, "name": "마포구"},
        "11530": {"lat": 37.4954, "lng": 126.8581, "name": "구로구"},
        "11680": {"lat": 37.5172, "lng": 127.0473, "name": "강남구"},
        "11650": {"lat": 37.4837, "lng": 127.0324, "name": "서초구"},
        "11710": {"lat": 37.5145, "lng": 127.1059, "name": "송파구"},
        "11740": {"lat": 37.5301, "lng": 127.1238, "name": "강동구"},
        "11590": {"lat": 37.5124, "lng": 126.9393, "name": "동작구"},
        "11620": {"lat": 37.4784, "lng": 126.9516, "name": "관악구"},
        "11545": {"lat": 37.4569, "lng": 126.8958, "name": "금천구"},
        "11170": {"lat": 37.5384, "lng": 126.9654, "name": "용산구"},
        "11140": {"lat": 37.5641, "lng": 126.9979, "name": "중구"},
        "11110": {"lat": 37.5735, "lng": 126.9788, "name": "종로구"},
        "11200": {"lat": 37.5634, "lng": 127.0369, "name": "성동구"},
        "11215": {"lat": 37.5385, "lng": 127.0823, "name": "광진구"},
        "11230": {"lat": 37.5744, "lng": 127.0396, "name": "동대문구"},
        "11290": {"lat": 37.5894, "lng": 127.0167, "name": "성북구"},
        "11350": {"lat": 37.6542, "lng": 127.0568, "name": "노원구"},
        "11380": {"lat": 37.6027, "lng": 126.9291, "name": "은평구"},
        "11410": {"lat": 37.5791, "lng": 126.9368, "name": "서대문구"},
        "11305": {"lat": 37.6396, "lng": 127.0257, "name": "강북구"},
        "11320": {"lat": 37.6688, "lng": 127.0472, "name": "도봉구"},
        "11260": {"lat": 37.6063, "lng": 127.0926, "name": "중랑구"},
    }
    
    # 차단 감지 코드
    BLOCK_STATUS_CODES = [403, 429, 503]
    
    def __init__(self, delay_range: tuple[float, float] = (2.0, 3.0)):
        """
        Args:
            delay_range: 요청 간 딜레이 범위 (초) - 기본 2-3초
        """
        self.delay_range = delay_range
        self.client = httpx.Client(headers=self.DEFAULT_HEADERS, timeout=30.0)
        self.logger = logger.bind(source="NaverLand")
        self.cache = get_cache_manager()
        
        # 차단 상태
        self._is_blocked = False
        
        # 단지 정보 캐시 (메모리)
        self._complex_cache: dict[str, dict[str, dict]] = {}
    
    def _delay(self):
        """요청 간 랜덤 딜레이"""
        delay = random.uniform(*self.delay_range)
        self.logger.debug(f"Waiting {delay:.1f}s...")
        time.sleep(delay)
    
    def _check_blocked(self):
        """차단 상태 확인"""
        if self._is_blocked:
            raise BlockedError("API 차단 상태입니다. 잠시 후 다시 시도하세요.")
    
    def _safe_request(self, url: str, params: dict) -> Optional[dict]:
        """
        안전한 API 요청
        - 차단 감지
        - 자동 딜레이
        """
        self._check_blocked()
        
        # 딜레이 적용
        self._delay()
        
        try:
            response = self.client.get(url, params=params)
            
            # 차단 감지
            if response.status_code in self.BLOCK_STATUS_CODES:
                self._is_blocked = True
                self.logger.error(f"🚫 차단 감지! Status: {response.status_code}")
                self.logger.error("30분 후 다시 시도하세요.")
                raise BlockedError(f"API 차단됨 (HTTP {response.status_code})")
            
            if response.status_code != 200:
                self.logger.warning(f"HTTP error: {response.status_code}")
                return None
            
            # HTML 반환 감지 (차단 징후)
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                self.logger.warning("HTML 응답 감지 (차단 가능성)")
                return None
            
            return response.json()
            
        except BlockedError:
            raise
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            return None
    
    # ==================== 단지 목록 조회 ====================
    
    def get_complex_list(self, cortarNo: str, trade_type: str = "B1") -> dict[str, dict]:
        """
        지역 내 단지 목록 조회 (세대수 포함)
        """
        cache_key = f"{cortarNo}_{trade_type}"
        
        # 메모리 캐시 확인
        if cache_key in self._complex_cache:
            return self._complex_cache[cache_key]
        
        self.logger.info(f"Fetching complex list: {cortarNo}")
        
        url = f"{self.MOBILE_URL}/cluster/ajax/complexList"
        params = {
            "cortarNo": cortarNo,
            "rletTpCd": "APT",
            "tradTpCd": trade_type,
        }
        
        data = self._safe_request(url, params)
        
        if not data:
            return {}
        
        result = data.get("result", [])
        
        complex_map = {}
        for item in result:
            name = item.get("hscpNm", "")
            if not name:
                continue
            
            complex_map[name] = {
                "hscpNo": item.get("hscpNo"),
                "complex_name": name,
                "households": item.get("totHsehCnt"),
                "buildings": item.get("totDongCnt"),
                "built_year": self._parse_built_year(item.get("useAprvYmd")),
            }
        
        self._complex_cache[cache_key] = complex_map
        self.logger.info(f"Loaded {len(complex_map)} complexes")
        
        return complex_map
    
    # ==================== 매물 검색 ====================
    
    def search_by_region(
        self,
        region_code: str,
        user_input: UserInput,
        max_items: int = 50,
    ) -> list[Listing]:
        """
        지역 코드로 매물 검색 (캐시 적용)
        """
        sigungu_code = region_code[:5] if len(region_code) > 5 else region_code
        
        coords = self.REGION_COORDS.get(sigungu_code)
        if not coords:
            self.logger.warning(f"Unknown region: {sigungu_code}")
            return []
        
        # 캐시 확인
        cache_params = {
            "region": sigungu_code,
            "type": user_input.transaction_type,
            "max_deposit": user_input.max_deposit,
            "min_area": user_input.min_area_sqm,
        }
        
        cached_data = self.cache.get(cache_params)
        if cached_data:
            # 캐시된 데이터를 Listing 객체로 변환
            listings = [Listing(**item) for item in cached_data]
            self.logger.info(f"Using cached data: {len(listings)} listings")
            return listings[:max_items]
        
        self.logger.info(f"Searching: {coords['name']} ({sigungu_code})")
        
        trade_type = self.TRADE_TYPE_CODES.get(user_input.transaction_type, "B1")
        
        property_types = []
        for pt in user_input.property_types:
            code = self.PROPERTY_TYPE_CODES.get(pt, "APT")
            property_types.append(code)
        real_estate_type = ":".join(property_types) if property_types else "APT"
        
        listings = []
        page = 1
        collected_cortarNos = set()
        
        lat, lng = coords["lat"], coords["lng"]
        delta = 0.02
        
        while len(listings) < max_items:
            try:
                url = f"{self.MOBILE_URL}/cluster/ajax/articleList"
                params = {
                    "rletTpCd": real_estate_type,
                    "tradTpCd": trade_type,
                    "z": 14,
                    "lat": lat,
                    "lng": lng,
                    "btm": lat - delta,
                    "lft": lng - delta,
                    "top": lat + delta,
                    "rgt": lng + delta,
                    "cortarNo": f"{sigungu_code}00000",
                    "page": page,
                    "totCnt": 0,
                }
                
                if user_input.max_deposit:
                    params["dprcMax"] = user_input.max_deposit
                
                if user_input.min_area_sqm:
                    params["spcMin"] = int(user_input.min_area_sqm)
                if user_input.max_area_sqm:
                    params["spcMax"] = int(user_input.max_area_sqm)
                
                data = self._safe_request(url, params)
                
                if not data or data.get("code") != "success":
                    break
                
                articles = data.get("body", [])
                
                if not articles:
                    break
                
                for article in articles:
                    listing = self._parse_article(article)
                    if listing:
                        listings.append(listing)
                        cortarNo = article.get("cortarNo")
                        if cortarNo:
                            collected_cortarNos.add(cortarNo)
                
                self.logger.info(f"Page {page}: {len(articles)} items")
                
                if not data.get("more", False):
                    break
                
                page += 1
                
                # 페이지 제한 (안전)
                if page > 5:
                    self.logger.info("Page limit reached")
                    break
                
            except BlockedError:
                raise
            except Exception as e:
                self.logger.error(f"Search error: {e}")
                break
        
        # 단지 정보 보강
        self._enrich_with_complex_info(listings, collected_cortarNos, trade_type)
        
        # 캐시 저장
        if listings:
            cache_data = [listing.model_dump() for listing in listings]
            self.cache.set(cache_params, cache_data)
        
        self.logger.info(f"Total: {len(listings)} listings")
        return listings[:max_items]
    
    def _enrich_with_complex_info(
        self,
        listings: list[Listing],
        cortarNos: set[str],
        trade_type: str,
    ):
        """매물에 단지 정보(세대수) 매칭"""
        if not cortarNos:
            return
        
        self.logger.info(f"Enriching from {len(cortarNos)} dong codes")
        
        all_complexes = {}
        for cortarNo in cortarNos:
            try:
                complexes = self.get_complex_list(cortarNo, trade_type)
                all_complexes.update(complexes)
            except BlockedError:
                raise
            except Exception as e:
                self.logger.warning(f"Complex fetch error: {e}")
        
        matched = 0
        for listing in listings:
            complex_name = listing.complex_name or listing.title or ""
            
            complex_info = all_complexes.get(complex_name)
            
            if not complex_info:
                complex_info = self._find_similar_complex(complex_name, all_complexes)
            
            if complex_info:
                matched += 1
                if listing.households is None:
                    listing.households = complex_info.get("households")
                if listing.buildings is None:
                    listing.buildings = complex_info.get("buildings")
                if listing.built_year is None:
                    listing.built_year = complex_info.get("built_year")
        
        self.logger.info(f"Matched: {matched}/{len(listings)}")
    
    def _find_similar_complex(self, name: str, complexes: dict) -> Optional[dict]:
        """유사한 단지명 찾기"""
        if not name:
            return None
        
        normalized = re.sub(r'[\s\-_]', '', name.lower())
        
        for complex_name, info in complexes.items():
            normalized_complex = re.sub(r'[\s\-_]', '', complex_name.lower())
            
            if normalized in normalized_complex or normalized_complex in normalized:
                return info
            
            min_len = min(len(normalized), len(normalized_complex))
            if min_len >= 4 and normalized[:min_len-1] == normalized_complex[:min_len-1]:
                return info
        
        return None
    
    # ==================== 파싱 헬퍼 ====================
    
    def _parse_article(self, article: dict) -> Optional[Listing]:
        """API 응답을 Listing 객체로 변환"""
        try:
            article_id = str(article.get("atclNo", ""))
            if not article_id:
                return None
            
            prc = article.get("prc", 0)
            rent_prc = article.get("rentPrc", 0)
            spc1 = article.get("spc1", 0)
            spc2 = article.get("spc2", 0)
            
            floor_info = article.get("flrInfo", "")
            floor, total_floors = self._parse_floor(floor_info)
            
            listing = Listing(
                id=f"naver_{article_id}",
                source=ListingSource.NAVER,
                url=f"https://m.land.naver.com/article/info/{article_id}",
                title=article.get("atclNm", ""),
                complex_name=article.get("atclNm", ""),
                region_gu=article.get("rletTpNm", ""),
                transaction_type=article.get("tradTpNm", ""),
                deposit=int(prc) if prc else None,
                monthly_rent=int(rent_prc) if rent_prc else 0,
                area_sqm=float(spc2) if spc2 else None,
                supply_area_sqm=float(spc1) if spc1 else None,
                property_type=article.get("rletTpNm", ""),
                floor=floor,
                total_floors=total_floors,
                direction=article.get("direction", ""),
                description=article.get("atclFetrDesc", ""),
                agent_name=article.get("rltrNm", ""),
                latitude=article.get("lat"),
                longitude=article.get("lng"),
                listed_date=self._parse_date(article.get("atclCfmYmd", "")),
            )
            
            if listing.area_sqm:
                listing.area_pyeong = round(listing.area_sqm * 0.3025, 1)
            
            tags = article.get("tagList", [])
            if tags:
                listing.options = tags
            
            return listing
            
        except Exception as e:
            self.logger.warning(f"Parse error: {e}")
            return None
    
    def _parse_built_year(self, date_str: str) -> Optional[int]:
        if not date_str:
            return None
        try:
            return int(str(date_str)[:4])
        except:
            return None
    
    def _parse_floor(self, floor_info: str) -> tuple[Optional[int], Optional[int]]:
        if not floor_info:
            return None, None
        try:
            if "/" in floor_info:
                parts = floor_info.replace("층", "").split("/")
                floor = int(parts[0]) if parts[0] else None
                total = int(parts[1]) if len(parts) > 1 and parts[1] else None
                return floor, total
            floor = int(floor_info.replace("층", ""))
            return floor, None
        except:
            return None, None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            clean = date_str.replace(".", "").strip()
            if len(clean) == 6:
                return datetime.strptime(clean, "%y%m%d").date()
            return None
        except:
            return None
    
    def close(self):
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
