#!/usr/bin/env python
"""
PropLens 캐시 관리 CLI

사용법:
    python scripts/cache_cli.py status          # 캐시 상태 확인
    python scripts/cache_cli.py clear           # 전체 캐시 삭제
    python scripts/cache_cli.py clear-expired   # 만료된 캐시만 삭제
    python scripts/cache_cli.py clear 11500     # 특정 지역(강서구) 캐시 삭제
    python scripts/cache_cli.py detail          # 캐시 상세 정보
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.data_sources import get_cache_manager, get_name_by_code


def cmd_status():
    """캐시 상태 간단히 출력"""
    cache = get_cache_manager()
    stats = cache.get_stats()

    print("=" * 40)
    print("📦 PropLens 캐시 상태")
    print("=" * 40)
    print(f"  저장된 캐시: {stats['count']}개")
    print(f"  총 용량: {stats['size_kb']}KB")
    print(f"  캐시 위치: {cache.cache_dir}")
    print("=" * 40)


def cmd_detail():
    """캐시 상세 정보 출력"""
    cache = get_cache_manager()
    detailed = cache.get_detailed_stats()

    print("=" * 60)
    print("📊 PropLens 캐시 상세 정보")
    print("=" * 60)

    if not detailed:
        print("  (캐시 없음)")
        return

    print(f"{'지역':<12} {'유형':<6} {'매물수':<8} {'저장시간':<16} {'남은시간':<12} {'용량':<8}")
    print("-" * 60)

    for item in detailed:
        region_code = item['region']
        region_name = get_name_by_code(region_code)

        status = "❌" if item['expired'] else "✅"

        print(
            f"{status} {region_name:<10} "
            f"{item['type']:<6} "
            f"{item['items']:<8} "
            f"{item['cached_at']:<16} "
            f"{item['expires_in']:<12} "
            f"{item['size_kb']}KB"
        )

    print("=" * 60)


def cmd_clear(region: str = None):
    """캐시 삭제"""
    cache = get_cache_manager()

    if region:
        # 특정 지역만 삭제
        region_name = get_name_by_code(region)
        count = cache.clear_by_region(region)
        print(f"🗑️  {region_name}({region}) 캐시 {count}개 삭제됨")
    else:
        # 전체 삭제
        count = cache.clear()
        print(f"🗑️  전체 캐시 {count}개 삭제됨")


def cmd_clear_expired():
    """만료된 캐시만 삭제"""
    cache = get_cache_manager()
    count = cache.clear_expired()

    if count > 0:
        print(f"⏰ 만료된 캐시 {count}개 삭제됨")
    else:
        print("✅ 만료된 캐시 없음")


def print_help():
    """도움말 출력"""
    print(__doc__)
    print("\n주요 지역 코드:")
    print("  서울: 11500(강서), 11470(양천), 11560(영등포), 11680(강남)...")
    print("  경기: 41210(광명), 41190(부천), 41135(분당)...")
    print("\n전체 코드는 app/data_sources/region_codes.py 참조")


def main():
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    if command == "status":
        cmd_status()
    elif command == "detail":
        cmd_detail()
    elif command == "clear":
        region = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_clear(region)
    elif command == "clear-expired":
        cmd_clear_expired()
    elif command in ["help", "-h", "--help"]:
        print_help()
    else:
        print(f"❌ 알 수 없는 명령: {command}")
        print_help()


if __name__ == "__main__":
    main()
