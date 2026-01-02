"""
PropLens 테스트 - Filter Engine
"""

import pytest
import sys
sys.path.insert(0, ".")

from app.domain.filters import FilterEngine
from app.schemas.listing import Listing, ListingSource
from app.schemas.user_input import UserInput
from app.schemas.results import FilterStatus


class TestFilterEngine:
    """Filter Engine 테스트"""
    
    def setup_method(self):
        self.engine = FilterEngine()
        
        # 기본 테스트 매물
        self.listing = Listing(
            id="test_001",
            source=ListingSource.MANUAL,
            deposit=45000,
            area_sqm=84.0,
            households=1500,
            built_year=2020,
            region_gu="양천구",
            property_type="아파트",
        )
    
    def test_pass_all_conditions(self):
        """모든 조건 통과"""
        user_input = UserInput(
            max_deposit=50000,
            min_area_sqm=80,
            min_households=1000,
        )
        
        result = self.engine.filter(self.listing, user_input)
        
        assert result.status == FilterStatus.PASS
        assert len(result.failed_conditions) == 0
    
    def test_fail_deposit(self):
        """예산 초과로 탈락"""
        user_input = UserInput(
            max_deposit=40000,  # 예산보다 높음
            must_conditions=["max_deposit"],
        )
        
        result = self.engine.filter(self.listing, user_input)
        
        assert result.status == FilterStatus.FAIL
        assert "max_deposit" in result.failed_conditions
        assert "보증금" in result.failure_reasons["max_deposit"]
    
    def test_fail_area(self):
        """면적 부족으로 탈락"""
        user_input = UserInput(
            min_area_sqm=100,  # 더 큰 면적 요구
            must_conditions=["min_area_sqm"],
        )
        
        result = self.engine.filter(self.listing, user_input)
        
        assert result.status == FilterStatus.FAIL
        assert "min_area_sqm" in result.failed_conditions
    
    def test_partial_pass(self):
        """일부 조건만 충족 (필수 조건은 통과)"""
        user_input = UserInput(
            max_deposit=50000,
            min_households=2000,  # 충족 못함
            must_conditions=["max_deposit"],  # 필수는 예산만
        )
        
        result = self.engine.filter(self.listing, user_input)
        
        assert result.status == FilterStatus.PARTIAL
        assert "max_deposit" in result.passed_conditions
        assert "min_households" in result.failed_conditions
    
    def test_region_filter(self):
        """지역 필터"""
        user_input = UserInput(
            regions=["양천구", "강서구"],
        )
        
        result = self.engine.filter(self.listing, user_input)
        
        assert result.status == FilterStatus.PASS
        assert "regions" in result.passed_conditions
    
    def test_region_filter_fail(self):
        """지역 불일치"""
        user_input = UserInput(
            regions=["강남구", "서초구"],
            must_conditions=["regions"],
        )
        
        result = self.engine.filter(self.listing, user_input)
        
        assert result.status == FilterStatus.FAIL


class TestFilterEngineMissingData:
    """누락 데이터 처리 테스트"""
    
    def setup_method(self):
        self.engine = FilterEngine()
    
    def test_missing_deposit(self):
        """보증금 정보 없는 경우"""
        listing = Listing(
            id="test_002",
            source=ListingSource.MANUAL,
            deposit=None,  # 정보 없음
        )
        
        user_input = UserInput(max_deposit=50000)
        result = self.engine.filter(listing, user_input)
        
        # 정보 없으면 통과 (보수적 처리)
        assert "max_deposit" in result.passed_conditions
    
    def test_missing_area_must(self):
        """면적 정보 없는 경우 (필수 조건)"""
        listing = Listing(
            id="test_003",
            source=ListingSource.MANUAL,
            area_sqm=None,  # 정보 없음
        )
        
        user_input = UserInput(
            min_area_sqm=80,
            must_conditions=["min_area_sqm"],
        )
        result = self.engine.filter(listing, user_input)
        
        # 필수 조건인데 정보 없으면 탈락
        assert result.status == FilterStatus.FAIL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
