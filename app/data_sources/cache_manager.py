"""
캐시 매니저
매물 데이터를 파일 기반으로 캐싱합니다.
"""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from loguru import logger


class CacheManager:
    """
    매물 데이터 캐시 관리
    - 파일 기반 캐시
    - TTL 기반 만료
    """

    def __init__(
        self,
        cache_dir: str = ".cache/naver_land",
        ttl_hours: int = 24,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.logger = logger.bind(source="CacheManager")

    def _get_cache_key(self, params: dict) -> str:
        """파라미터로 캐시 키 생성"""
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """캐시 파일 경로"""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, params: dict) -> Optional[Any]:
        """
        캐시에서 데이터 조회

        Returns:
            캐시된 데이터 또는 None (만료/미존재)
        """
        cache_key = self._get_cache_key(params)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)

            cached_at = datetime.fromisoformat(cached["cached_at"])
            if datetime.now() - cached_at > self.ttl:
                self.logger.debug(f"Cache expired: {cache_key[:8]}...")
                cache_path.unlink()
                return None

            self.logger.info(f"Cache hit: {params.get('region', 'unknown')}")
            return cached["data"]

        except Exception as e:
            self.logger.warning(f"Cache read error: {e}")
            return None

    def set(self, params: dict, data: Any):
        """캐시에 데이터 저장"""
        cache_key = self._get_cache_key(params)
        cache_path = self._get_cache_path(cache_key)

        try:
            cached = {
                "cached_at": datetime.now().isoformat(),
                "params": params,
                "data": data,
            }

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cached, f, ensure_ascii=False, indent=2)

            self.logger.debug(f"Cache saved: {cache_key[:8]}...")

        except Exception as e:
            self.logger.warning(f"Cache write error: {e}")

    def clear(self) -> int:
        """전체 캐시 삭제"""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        self.logger.info(f"Cache cleared: {count} files")
        return count

    def clear_expired(self) -> int:
        """만료된 캐시만 삭제"""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                cached_at = datetime.fromisoformat(cached["cached_at"])
                if datetime.now() - cached_at > self.ttl:
                    cache_file.unlink()
                    count += 1
            except Exception:
                # 파싱 실패한 파일도 삭제
                cache_file.unlink()
                count += 1
        self.logger.info(f"Expired cache cleared: {count} files")
        return count

    def clear_by_region(self, region: str) -> int:
        """특정 지역 캐시 삭제"""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                params = cached.get("params", {})
                if params.get("region", "").startswith(region):
                    cache_file.unlink()
                    count += 1
            except Exception:
                pass
        self.logger.info(f"Cache cleared for region {region}: {count} files")
        return count

    def get_stats(self) -> dict:
        """캐시 통계"""
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "count": len(files),
            "size_kb": round(total_size / 1024, 1),
        }

    def get_detailed_stats(self) -> list[dict]:
        """캐시 상세 정보 (지역별, 만료시간 포함)"""
        result = []
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)

                cached_at = datetime.fromisoformat(cached["cached_at"])
                expires_at = cached_at + self.ttl
                remaining = expires_at - datetime.now()

                params = cached.get("params", {})
                data = cached.get("data", [])

                result.append({
                    "region": params.get("region", "unknown"),
                    "type": params.get("type", "unknown"),
                    "items": len(data) if isinstance(data, list) else 0,
                    "cached_at": cached_at.strftime("%Y-%m-%d %H:%M"),
                    "expires_in": self._format_timedelta(remaining),
                    "expired": remaining.total_seconds() < 0,
                    "size_kb": round(cache_file.stat().st_size / 1024, 1),
                })
            except Exception:
                pass

        # 만료 임박 순으로 정렬
        result.sort(key=lambda x: x["expires_in"])
        return result

    def _format_timedelta(self, td: timedelta) -> str:
        """timedelta를 읽기 좋은 문자열로 변환"""
        total_seconds = int(td.total_seconds())
        if total_seconds < 0:
            return "만료됨"

        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}시간 {minutes}분"
        return f"{minutes}분"


# 글로벌 인스턴스
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """싱글톤 캐시 매니저 반환"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
