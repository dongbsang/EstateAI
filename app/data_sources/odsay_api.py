"""
ODsay 대중교통 길찾기 API 클라이언트
출퇴근 시간 계산에 사용합니다.
"""

from typing import Optional
from loguru import logger

from app.config import settings
import httpx


class ODsayClient:
    """
    ODsay 대중교통 API 클라이언트

    API 키 발급:
    - https://lab.odsay.com 회원가입
    - 무료: 1,000건/일

    환경변수:
    - ODSAY_API_KEY: ODsay API 키
    """

    BASE_URL = settings.ODSAY_BASE_URL

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ODSAY_API_KEY
        self.client = httpx.Client(timeout=settings.ODSAY_TIMEOUT)
        self.logger = logger.bind(source="ODsay")

        if not self.api_key:
            self.logger.warning("ODsay API 키가 없습니다. ODSAY_API_KEY 환경변수를 설정하세요.")

    def get_transit_route(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
    ) -> Optional[dict]:
        """
        대중교통 경로 검색

        Args:
            start_lat: 출발지 위도
            start_lng: 출발지 경도
            end_lat: 도착지 위도
            end_lng: 도착지 경도

        Returns:
            {
                "total_time": 총 소요시간(분),
                "walk_time": 도보 시간(분),
                "transit_count": 환승 횟수,
                "path_type": 경로 유형,
            }
        """
        if not self.api_key:
            return None

        try:
            url = f"{self.BASE_URL}/searchPubTransPathT"
            params = {
                "apiKey": self.api_key,
                "SX": start_lng,
                "SY": start_lat,
                "EX": end_lng,
                "EY": end_lat,
                "SearchType": 0,  # 0: 추천순
            }

            response = self.client.get(url, params=params)

            if response.status_code != 200:
                self.logger.error(f"ODsay API error: {response.status_code}")
                return None

            data = response.json()

            # 에러 체크
            if "error" in data:
                self.logger.error(f"ODsay error: {data['error']}")
                return None

            result = data.get("result")
            if not result:
                return None

            # 첫 번째 경로 (추천 경로) 사용
            paths = result.get("path", [])
            if not paths:
                return None

            best_path = paths[0]
            info = best_path.get("info", {})

            return {
                "total_time": info.get("totalTime", 0),  # 분
                "walk_time": info.get("totalWalk", 0) // 60,  # 초 → 분
                "transit_count": info.get("busTransitCount", 0) + info.get("subwayTransitCount", 0),
                "payment": info.get("payment", 0),
                "path_type": self._get_path_type(best_path.get("pathType")),
            }

        except Exception as e:
            self.logger.error(f"Transit route error: {e}")
            return None

    def _get_path_type(self, path_type: int) -> str:
        """경로 유형 변환"""
        types = {
            1: "지하철",
            2: "버스",
            3: "지하철+버스",
        }
        return types.get(path_type, "기타")

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# 주요 지하철역 좌표 (출퇴근 목적지용)
STATION_COORDS = {
    # 주요 업무지구
    "여의도역": {"lat": 37.5216, "lng": 126.9243},
    "강남역": {"lat": 37.4979, "lng": 127.0276},
    "삼성역": {"lat": 37.5089, "lng": 127.0631},
    "선릉역": {"lat": 37.5046, "lng": 127.0486},
    "역삼역": {"lat": 37.5007, "lng": 127.0365},
    "교대역": {"lat": 37.4934, "lng": 127.0145},
    "서초역": {"lat": 37.4916, "lng": 127.0077},
    "시청역": {"lat": 37.5652, "lng": 126.9772},
    "광화문역": {"lat": 37.5709, "lng": 126.9768},
    "종각역": {"lat": 37.5700, "lng": 126.9830},
    "을지로입구역": {"lat": 37.5660, "lng": 126.9822},
    "충정로역": {"lat": 37.5597, "lng": 126.9636},
    "홍대입구역": {"lat": 37.5571, "lng": 126.9239},
    "합정역": {"lat": 37.5498, "lng": 126.9139},
    "영등포구청역": {"lat": 37.5257, "lng": 126.8963},
    "당산역": {"lat": 37.5347, "lng": 126.9023},
    "신도림역": {"lat": 37.5089, "lng": 126.8913},
    "가산디지털단지역": {"lat": 37.4816, "lng": 126.8826},
    "구로디지털단지역": {"lat": 37.4852, "lng": 126.9015},
    "판교역": {"lat": 37.3947, "lng": 127.1112},
    "정자역": {"lat": 37.3662, "lng": 127.1085},

    # 추가 역
    "서울역": {"lat": 37.5547, "lng": 126.9707},
    "용산역": {"lat": 37.5299, "lng": 126.9648},
    "왕십리역": {"lat": 37.5614, "lng": 127.0378},
    "건대입구역": {"lat": 37.5404, "lng": 127.0696},
    "잠실역": {"lat": 37.5133, "lng": 127.1001},
    "천호역": {"lat": 37.5388, "lng": 127.1236},
    "목동역": {"lat": 37.5274, "lng": 126.8754},
    "발산역": {"lat": 37.5581, "lng": 126.8378},
    "마곡역": {"lat": 37.5621, "lng": 126.8256},
}


def get_station_coords(station_name: str) -> Optional[dict]:
    """역 이름으로 좌표 조회"""
    # "역" 접미사 처리
    if not station_name.endswith("역"):
        station_name = station_name + "역"

    return STATION_COORDS.get(station_name)
