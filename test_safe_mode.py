"""
안전 모드 테스트
"""
import sys
sys.path.insert(0, ".")

from app.data_sources.naver_land import NaverLandClient, BlockedError
from app.data_sources.cache_manager import get_cache_manager
from app.schemas.user_input import UserInput


def test_cache():
    """캐시 테스트"""
    print("=" * 50)
    print("1. 캐시 상태")
    print("=" * 50)
    
    cache = get_cache_manager()
    stats = cache.get_stats()
    print(f"캐시 파일: {stats['count']}개")
    print(f"캐시 크기: {stats['size_kb']}KB")


def test_search():
    """검색 테스트 (캐시 활용)"""
    print("\n" + "=" * 50)
    print("2. 매물 검색 테스트")
    print("=" * 50)
    
    user_input = UserInput(
        transaction_type="전세",
        max_deposit=50000,
        regions=["양천구"],
        min_area_sqm=59.0,
    )
    
    try:
        with NaverLandClient() as client:
            listings = client.search_by_region(
                region_code="11470",
                user_input=user_input,
                max_items=10,
            )
            
            print(f"\n총 {len(listings)}개 매물")
            
            with_households = [l for l in listings if l.households]
            print(f"세대수 정보 있음: {len(with_households)}개")
            
            print("\n--- 상위 5개 ---")
            for listing in listings[:5]:
                print(f"- {listing.complex_name}")
                print(f"  {listing.deposit:,}만원 | {listing.area_pyeong}평")
                print(f"  세대수: {listing.households or '없음'} | 준공: {listing.built_year or '없음'}")
                print()
                
    except BlockedError as e:
        print(f"\n🚫 차단됨: {e}")
        print("30분 후 다시 시도하세요.")


if __name__ == "__main__":
    test_cache()
    test_search()
