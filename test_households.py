"""
세대수 수집 테스트 스크립트
"""
import sys
sys.path.insert(0, ".")

from app.data_sources.naver_land import NaverLandClient
from app.schemas.user_input import UserInput


def test_complex_list():
    """단지 목록 조회 테스트"""
    print("=" * 60)
    print("1. 단지 목록 조회 테스트 (양천구 신정동)")
    print("=" * 60)
    
    with NaverLandClient() as client:
        # 양천구 신정1동 법정동 코드
        complexes = client.get_complex_list("1147010100", "B1")
        
        print(f"\n총 {len(complexes)}개 단지 발견\n")
        
        for name, info in list(complexes.items())[:10]:
            print(f"- {name}")
            print(f"  세대수: {info.get('households')}세대")
            print(f"  동수: {info.get('buildings')}동")
            print(f"  준공연도: {info.get('built_year')}년")
            print()


def test_search_with_households():
    """매물 검색 + 세대수 매칭 테스트"""
    print("=" * 60)
    print("2. 매물 검색 + 세대수 매칭 테스트")
    print("=" * 60)
    
    user_input = UserInput(
        transaction_type="전세",
        max_deposit=80000,
        regions=["양천구"],
        min_area_sqm=60.0,
    )
    
    with NaverLandClient() as client:
        listings = client.search_by_region(
            region_code="11470",
            user_input=user_input,
            max_items=20,
        )
        
        print(f"\n총 {len(listings)}개 매물 수집\n")
        
        # 세대수 있는 매물 확인
        with_households = [l for l in listings if l.households]
        print(f"세대수 정보 있음: {len(with_households)}개")
        print(f"세대수 정보 없음: {len(listings) - len(with_households)}개\n")
        
        for listing in listings[:10]:
            print(f"- {listing.complex_name}")
            print(f"  보증금: {listing.deposit:,}만원")
            print(f"  면적: {listing.area_sqm}㎡ ({listing.area_pyeong}평)")
            print(f"  세대수: {listing.households or '정보없음'}")
            print(f"  준공연도: {listing.built_year or '정보없음'}")
            print()


if __name__ == "__main__":
    test_complex_list()
    print("\n" + "=" * 60 + "\n")
    test_search_with_households()
