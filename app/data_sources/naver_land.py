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

from app.config import settings
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

    # 지역별 좌표
    REGION_COORDS = {
        # === 서울시 ===
        "11500": {"lat": 37.5509, "lng": 126.8495},
        "11470": {"lat": 37.5270, "lng": 126.8561},
        "11560": {"lat": 37.5263, "lng": 126.8963},
        "11440": {"lat": 37.5538, "lng": 126.9084},
        "11530": {"lat": 37.4954, "lng": 126.8581},
        "11680": {"lat": 37.5172, "lng": 127.0473},
        "11650": {"lat": 37.4837, "lng": 127.0324},
        "11710": {"lat": 37.5145, "lng": 127.1059},
        "11740": {"lat": 37.5301, "lng": 127.1238},
        "11590": {"lat": 37.5124, "lng": 126.9393},
        "11620": {"lat": 37.4784, "lng": 126.9516},
        "11545": {"lat": 37.4569, "lng": 126.8958},
        "11170": {"lat": 37.5384, "lng": 126.9654},
        "11140": {"lat": 37.5641, "lng": 126.9979},
        "11110": {"lat": 37.5735, "lng": 126.9788},
        "11200": {"lat": 37.5634, "lng": 127.0369},
        "11215": {"lat": 37.5385, "lng": 127.0823},
        "11230": {"lat": 37.5744, "lng": 127.0396},
        "11290": {"lat": 37.5894, "lng": 127.0167},
        "11350": {"lat": 37.6542, "lng": 127.0568},
        "11380": {"lat": 37.6027, "lng": 126.9291},
        "11410": {"lat": 37.5791, "lng": 126.9368},
        "11305": {"lat": 37.6396, "lng": 127.0257},
        "11320": {"lat": 37.6688, "lng": 127.0472},
        "11260": {"lat": 37.6063, "lng": 127.0926},
        # === 경기도 ===
        "41131": {"lat": 37.4380, "lng": 127.1378},
        "41133": {"lat": 37.4321, "lng": 127.1193},
        "41135": {"lat": 37.3825, "lng": 127.1152},
        "41111": {"lat": 37.3030, "lng": 127.0100},
        "41113": {"lat": 37.2574, "lng": 126.9716},
        "41115": {"lat": 37.2850, "lng": 127.0200},
        "41117": {"lat": 37.2596, "lng": 127.0465},
        "41461": {"lat": 37.2342, "lng": 127.2020},
        "41463": {"lat": 37.2800, "lng": 127.1150},
        "41465": {"lat": 37.3220, "lng": 127.0980},
        "41281": {"lat": 37.6376, "lng": 126.8320},
        "41285": {"lat": 37.6586, "lng": 126.7742},
        "41287": {"lat": 37.6759, "lng": 126.7511},
        "41171": {"lat": 37.3943, "lng": 126.9320},
        "41173": {"lat": 37.3897, "lng": 126.9533},
        "41190": {"lat": 37.5034, "lng": 126.7660},
        "41210": {"lat": 37.4786, "lng": 126.8644},
        "41271": {"lat": 37.3180, "lng": 126.8468},
        "41273": {"lat": 37.3188, "lng": 126.8105},
        "41590": {"lat": 37.1995, "lng": 127.0985},
        "41220": {"lat": 36.9908, "lng": 127.0858},
        "41390": {"lat": 37.3800, "lng": 126.8028},
        "41570": {"lat": 37.6152, "lng": 126.7156},
        "41610": {"lat": 37.4095, "lng": 127.2550},
        "41450": {"lat": 37.5393, "lng": 127.2148},
        "41310": {"lat": 37.5943, "lng": 127.1295},
        "41360": {"lat": 37.6360, "lng": 127.2165},
        "41150": {"lat": 37.7381, "lng": 127.0337},
        "41480": {"lat": 37.7599, "lng": 126.7800},
        "41290": {"lat": 37.4292, "lng": 126.9876},
        "41430": {"lat": 37.3449, "lng": 126.9685},
        "41410": {"lat": 37.3617, "lng": 126.9352},
    }

    BLOCK_STATUS_CODES = [403, 429, 503]

    def __init__(self, delay_range: tuple[float, float] = None):
        if delay_range is None:
            delay_range = (settings.CRAWL_DELAY_MIN, settings.CRAWL_DELAY_MAX)
        self.delay_range = delay_range
        self.client = httpx.Client(
            headers=settings.NAVER_LAND_HEADERS,
            timeout=settings.NAVER_LAND_TIMEOUT
        )
        self.logger = logger.bind(source="NaverLand")
        self.cache = get_cache_manager()
        self._is_blocked = False
        self._complex_cache: dict[str, dict[str, dict]] = {}

    def _delay(self):
        delay = random.uniform(*self.delay_range)
        self.logger.debug(f"Waiting {delay:.1f}s...")
        time.sleep(delay)

    def _check_blocked(self):
        if self._is_blocked:
            raise BlockedError("API 차단 상태입니다. 잠시 후 다시 시도하세요.")

    def _safe_request(self, url: str, params: dict) -> Optional[dict]:
        self._check_blocked()
        self._delay()

        try:
            response = self.client.get(url, params=params)

            if response.status_code in self.BLOCK_STATUS_CODES:
                self._is_blocked = True
                self.logger.error(f"🚫 차단 감지! Status: {response.status_code}")
                raise BlockedError(f"API 차단됨 (HTTP {response.status_code})")

            if response.status_code != 200:
                self.logger.warning(f"HTTP error: {response.status_code}")
                return None

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
    def get_complex_list(self, cortarNo: str, trade_type: str = "B1",
                         max_pages: int = 10) -> dict[str, dict]:
        """지역 내 단지 목록 조회 (페이지네이션 적용)"""
        cache_key = f"{cortarNo}_{trade_type}_full"

        if cache_key in self._complex_cache:
            return self._complex_cache[cache_key]

        self.logger.info(f"Fetching complex list: {cortarNo} (with pagination)")

        url = f"{settings.NAVER_LAND_MOBILE_URL}/cluster/ajax/complexList"
        complex_map = {}
        page = 1

        while page <= max_pages:
            params = {
                "cortarNo": cortarNo,
                "rletTpCd": "APT",
                "tradTpCd": trade_type,
                "page": page,
            }

            data = self._safe_request(url, params)
            if not data:
                break

            result = data.get("result", [])
            if not result:
                break

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

            self.logger.info(f"Complex list page {page}: {len(result)} complexes (total: {len(complex_map)})")

            if not data.get("more", False):
                break
            page += 1

        self._complex_cache[cache_key] = complex_map
        self.logger.info(f"Loaded {len(complex_map)} complexes total")
        return complex_map

    # ==================== 단지별 매물 조회 ====================
    def get_complex_articles(
        self,
        sigungu_code: str,
        complex_name: str,
        trade_type: str = "B1",
        property_type: str = "APT",
    ) -> list[Listing]:
        """특정 단지의 매물 목록 조회 (hscpNo 기반)"""
        self.logger.info(f"Searching complex: '{complex_name}' in {sigungu_code}")

        # 1. 단지 목록에서 hscpNo 찾기
        cortarNo = f"{sigungu_code}00000"
        complexes = self.get_complex_list(cortarNo, trade_type)

        normalized_input = self._normalize_complex_name(complex_name)
        self.logger.info(f"Normalized: '{complex_name}' -> '{normalized_input}'")

        # 매칭되는 단지 찾기
        matched_complex = None
        for name, info in complexes.items():
            normalized_name = self._normalize_complex_name(name)
            if self._is_complex_match(normalized_input, normalized_name):
                matched_complex = info
                self.logger.info(f"Found complex: '{name}' (hscpNo: {info.get('hscpNo')})")
                break

        if not matched_complex:
            self.logger.warning(f"Complex not found: '{complex_name}'")
            return self._search_articles_by_coords(sigungu_code, complex_name, trade_type, property_type)

        # 2. hscpNo로 매물 조회
        hscpNo = matched_complex.get("hscpNo")
        if not hscpNo:
            return []

        listings = self._get_articles_by_hscpNo(hscpNo, trade_type, matched_complex)

        if listings:
            self.logger.info(f"Found {len(listings)} articles for '{complex_name}'")
        else:
            self.logger.warning(f"No articles found for hscpNo: {hscpNo}")

        return listings

    def _get_articles_by_hscpNo(
        self,
        hscpNo: str,
        trade_type: str,
        complex_info: dict,
    ) -> list[Listing]:
        """단지 코드(hscpNo)로 매물 직접 조회"""
        self.logger.info(f"Fetching articles for hscpNo: {hscpNo}")

        url = f"{settings.NAVER_LAND_MOBILE_URL}/complex/getComplexArticleList"
        listings = []
        page = 1
        max_pages = 5

        while page <= max_pages:
            params = {
                "hscpNo": hscpNo,
                "tradTpCd": trade_type,
                "page": page,
            }

            data = self._safe_request(url, params)
            if not data:
                break

            # 응답 구조: result.list
            result = data.get("result", {})
            if isinstance(result, dict):
                articles = result.get("list", [])
            else:
                articles = result if isinstance(result, list) else []

            if not articles:
                break

            for article in articles:
                listing = self._parse_complex_article(article, complex_info)
                if listing:
                    listings.append(listing)

            self.logger.info(f"hscpNo {hscpNo} page {page}: {len(articles)} articles")

            # 더 이상 페이지 확인
            if isinstance(result, dict) and result.get("moreDataYn", "N") != "Y":
                break
            page += 1

        return listings

    def _parse_complex_article(self, article: dict, complex_info: dict) -> Optional[Listing]:
        """단지 매물 API 응답 파싱"""
        try:
            article_id = str(article.get("atclNo", ""))
            if not article_id:
                return None

            # 가격 파싱 - prcInfo 필드 사용 (예: '6억 5,000')
            prc_info = article.get("prcInfo", "0")
            deposit = self._parse_price(prc_info)

            # 월세의 경우 rentPrc 필드
            rent_prc = article.get("rentPrc", 0)
            monthly_rent = int(rent_prc) if rent_prc else 0

            # 면적
            spc1 = article.get("spc1", 0)
            spc2 = article.get("spc2", 0)

            # 층수
            floor_info = article.get("flrInfo", "")
            floor, total_floors = self._parse_floor(floor_info)

            listing = Listing(
                id=f"naver_{article_id}",
                source=ListingSource.NAVER,
                url=f"https://m.land.naver.com/article/info/{article_id}",
                title=complex_info.get("complex_name", ""),
                complex_name=complex_info.get("complex_name", ""),
                transaction_type=article.get("tradTpNm", ""),
                deposit=deposit,
                monthly_rent=monthly_rent,
                area_sqm=float(spc2) if spc2 else None,
                supply_area_sqm=float(spc1) if spc1 else None,
                property_type=article.get("rletTpNm", "아파트"),
                floor=floor,
                total_floors=total_floors,
                direction=article.get("direction", ""),
                description=article.get("atclFetrDesc", ""),
                agent_name=article.get("rltrNm", ""),
                households=complex_info.get("households"),
                buildings=complex_info.get("buildings"),
                built_year=complex_info.get("built_year"),
            )

            if listing.area_sqm:
                listing.area_pyeong = round(listing.area_sqm * 0.3025, 1)

            return listing

        except Exception as e:
            self.logger.warning(f"Parse complex article error: {e}")
            return None

    def _parse_price(self, price_str: str) -> int:
        """가격 문자열 파싱 (예: '4억 5,000' -> 45000)"""
        if not price_str:
            return 0

        try:
            price_str = str(price_str).strip()

            if '억' in price_str:
                parts = price_str.split('억')
                billions = int(parts[0].replace(',', '').strip()) * 10000

                if len(parts) > 1 and parts[1].strip():
                    remainder = parts[1].replace(',', '').replace(' ', '').strip()
                    if remainder:
                        billions += int(remainder)

                return billions
            else:
                return int(price_str.replace(',', '').replace(' ', ''))
        except:
            return 0

    def _search_articles_by_coords(
        self,
        sigungu_code: str,
        complex_name: str,
        trade_type: str,
        property_type: str,
    ) -> list[Listing]:
        """좌표 기반 매물 검색 (폴백)"""
        coords = self.REGION_COORDS.get(sigungu_code)
        if not coords:
            return []

        normalized_input = self._normalize_complex_name(complex_name)
        listings = []
        lat, lng = coords["lat"], coords["lng"]

        for page in range(1, 6):
            url = f"{settings.NAVER_LAND_MOBILE_URL}/cluster/ajax/articleList"
            params = {
                "rletTpCd": property_type,
                "tradTpCd": trade_type,
                "z": 14,
                "lat": lat,
                "lng": lng,
                "btm": lat - 0.05,
                "lft": lng - 0.05,
                "top": lat + 0.05,
                "rgt": lng + 0.05,
                "cortarNo": f"{sigungu_code}00000",
                "page": page,
                "totCnt": 0,
            }

            data = self._safe_request(url, params)
            if not data or data.get("code") != "success":
                break

            articles = data.get("body", [])
            if not articles:
                break

            for article in articles:
                article_name = article.get("atclNm", "")
                normalized_article = self._normalize_complex_name(article_name)

                if self._is_complex_match(normalized_input, normalized_article):
                    listing = self._parse_article(article)
                    if listing:
                        listings.append(listing)

            if listings:
                break

            if not data.get("more", False):
                break

        return listings

    def _normalize_complex_name(self, name: str) -> str:
        """단지명 정규화: 공백, 특수문자 제거, 소문자화"""
        if not name:
            return ""
        normalized = re.sub(r'[\s\-_]', '', name)
        return normalized.lower()

    def _is_complex_match(self, input_name: str, article_name: str) -> bool:
        """단지명 매칭 확인 (유연한 매칭)"""
        if not input_name or not article_name:
            return False

        if input_name == article_name:
            return True

        if input_name in article_name or article_name in input_name:
            return True

        min_len = min(len(input_name), len(article_name))
        if min_len >= 4:
            match_len = 0
            for i in range(min_len):
                if input_name[i] == article_name[i]:
                    match_len += 1
                else:
                    break
            if match_len >= 4:
                return True

        return False

    def _get_complex_info_by_name(
        self,
        sigungu_code: str,
        complex_name: str,
        trade_type: str,
    ) -> Optional[dict]:
        """단지명으로 단지 정보 조회"""
        cortarNo = f"{sigungu_code}00000"
        complexes = self.get_complex_list(cortarNo, trade_type)

        if complex_name in complexes:
            return complexes[complex_name]

        return self._find_similar_complex(complex_name, complexes)

    def get_region_complex_list(
        self,
        sigungu_code: str,
        trade_type: str = "B1",
        property_type: str = "APT",
    ) -> list[dict]:
        """지역 내 단지 목록 조회 (UI용)"""
        cortarNo = f"{sigungu_code}00000"
        complexes = self.get_complex_list(cortarNo, trade_type)

        result = []
        for name, info in complexes.items():
            result.append({
                "name": name,
                "households": info.get("households"),
                "buildings": info.get("buildings"),
                "built_year": info.get("built_year"),
            })

        result.sort(key=lambda x: x.get("households") or 0, reverse=True)
        return result

    # ==================== 매물 검색 ====================
    def search_by_region(
        self,
        region_code: str,
        user_input: UserInput,
        max_items: int = 50,
    ) -> list[Listing]:
        """지역 코드로 매물 검색 (캐시 적용)"""
        sigungu_code = region_code[:5] if len(region_code) > 5 else region_code

        coords = self.REGION_COORDS.get(sigungu_code)
        if not coords:
            self.logger.warning(f"Unknown region: {sigungu_code}")
            return []

        property_types_key = ",".join(sorted(user_input.property_types))
        cache_params = {
            "region": sigungu_code,
            "type": user_input.transaction_type,
            "property_types": property_types_key,
            "max_deposit": user_input.max_deposit,
            "min_area": user_input.min_area_sqm,
        }

        cached_data = self.cache.get(cache_params)
        if cached_data:
            listings = [Listing(**item) for item in cached_data]
            self.logger.info(f"Using cached data: {len(listings)} listings")
            return listings[:max_items]

        from app.data_sources.region_codes import get_name_by_code
        self.logger.info(f"Searching: {get_name_by_code(sigungu_code)} ({sigungu_code})")

        trade_type = settings.TRADE_TYPE_CODES.get(user_input.transaction_type, "B1")

        property_types = []
        for pt in user_input.property_types:
            code = settings.PROPERTY_TYPE_CODES.get(pt, "APT")
            property_types.append(code)
        real_estate_type = ":".join(property_types) if property_types else "APT"

        listings = []
        page = 1
        collected_cortarNos = set()
        lat, lng = coords["lat"], coords["lng"]
        delta = 0.02

        while len(listings) < max_items:
            try:
                url = f"{settings.NAVER_LAND_MOBILE_URL}/cluster/ajax/articleList"
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
                if page > 5:
                    self.logger.info("Page limit reached")
                    break

            except BlockedError:
                raise
            except Exception as e:
                self.logger.error(f"Search error: {e}")
                break

        self._enrich_with_complex_info(listings, collected_cortarNos, trade_type)

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
                region_gu=self._get_region_name_from_cortar(article.get("cortarNo", "")),
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

    def _get_region_name_from_cortar(self, cortarNo: str) -> str:
        if not cortarNo:
            return ""
        from app.data_sources.region_codes import get_name_by_code
        return get_name_by_code(cortarNo[:5])

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
