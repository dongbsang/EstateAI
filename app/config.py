"""
PropLens 설정 관리

모든 설정값은 .env 파일에서 관리합니다.
사용법:
    from app.config import settings
    url = settings.DATA_GO_KR_BASE_URL
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env에 정의되지 않은 변수 무시
    )

    # === 환경 ===
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # === LLM ===
    MODEL_PATH: str = "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    MODEL_N_CTX: int = 4096
    MODEL_N_GPU_LAYERS: int = 0

    # === 공공데이터 API (국토부 실거래가) ===
    DATA_GO_KR_API_KEY: str = ""
    DATA_GO_KR_BASE_URL: str = "http://apis.data.go.kr/1613000"
    DATA_GO_KR_TIMEOUT: int = 30

    # === 네이버 부동산 ===
    NAVER_LAND_MOBILE_URL: str = "https://m.land.naver.com"
    NAVER_LAND_TIMEOUT: int = 30
    NAVER_LAND_MAX_RETRIES: int = 3
    
    # 네이버 부동산 API 헤더
    NAVER_LAND_HEADERS: dict = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://m.land.naver.com/",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    }

    # === ODsay 대중교통 API ===
    ODSAY_API_KEY: str = ""
    ODSAY_BASE_URL: str = "https://api.odsay.com/v1/api"
    ODSAY_TIMEOUT: int = 30

    # === 크롤링 설정 ===
    CRAWL_DELAY_MIN: float = 1.5
    CRAWL_DELAY_MAX: float = 3.0
    MAX_ITEMS_PER_REGION: int = 50

    # === 매물 타입 코드 (네이버 부동산 API) ===
    PROPERTY_TYPE_CODES: dict = {
        "아파트": "APT",
        "오피스텔": "OPST",
        "빌라": "VL",
        "원룸": "OR",
    }

    # === 거래 유형 코드 (네이버 부동산 API) ===
    TRADE_TYPE_CODES: dict = {
        "매매": "A1",
        "전세": "B1",
        "월세": "B2",
    }


# 싱글톤 인스턴스
settings = Settings()
