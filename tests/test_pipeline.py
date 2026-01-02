"""
PropLens 테스트 - Pipeline (자동화 버전)
"""

import pytest
import sys
sys.path.insert(0, ".")

from app.schemas.user_input import UserInput


class TestPipelineIntegration:
    """Pipeline 통합 테스트"""
    
    @pytest.mark.skip(reason="실제 API 호출 - 필요시 활성화")
    def test_full_pipeline(self):
        """전체 파이프라인 테스트"""
        from app.pipeline import PipelineOrchestrator
        
        user_input = UserInput(
            transaction_type="전세",
            max_deposit=45000,
            regions=["양천구"],
            min_area_sqm=80,
            min_households=500,
            must_conditions=["max_deposit"],
        )
        
        orchestrator = PipelineOrchestrator(max_items_per_region=10)
        report = orchestrator.run(
            user_input=user_input,
            enrich_data=False,  # API 키 없으면 스킵
        )
        
        assert report.total_count > 0
        print(f"Total: {report.total_count}, Passed: {report.passed_count}")
        print(f"Summary: {report.summary}")


class TestFilterEngine:
    """Filter Engine 테스트"""
    
    def test_filter_pass(self):
        """필터 통과 테스트"""
        from app.domain.filters import FilterEngine
        from app.schemas.listing import Listing, ListingSource
        from app.schemas.results import FilterStatus
        
        engine = FilterEngine()
        
        listing = Listing(
            id="test_001",
            source=ListingSource.NAVER,
            deposit=40000,
            area_sqm=84.0,
            households=1500,
        )
        
        user_input = UserInput(
            max_deposit=50000,
            min_area_sqm=80,
            min_households=1000,
        )
        
        result = engine.filter(listing, user_input)
        
        assert result.status == FilterStatus.PASS
    
    def test_filter_fail(self):
        """필터 탈락 테스트"""
        from app.domain.filters import FilterEngine
        from app.schemas.listing import Listing, ListingSource
        from app.schemas.results import FilterStatus
        
        engine = FilterEngine()
        
        listing = Listing(
            id="test_002",
            source=ListingSource.NAVER,
            deposit=60000,  # 예산 초과
            area_sqm=84.0,
        )
        
        user_input = UserInput(
            max_deposit=50000,
            must_conditions=["max_deposit"],
        )
        
        result = engine.filter(listing, user_input)
        
        assert result.status == FilterStatus.FAIL
        assert "max_deposit" in result.failed_conditions


class TestScoringEngine:
    """Scoring Engine 테스트"""
    
    def test_scoring(self):
        """점수화 테스트"""
        from app.domain.scoring import ScoringEngine
        from app.schemas.listing import Listing, ListingSource
        
        engine = ScoringEngine()
        
        listing = Listing(
            id="test_003",
            source=ListingSource.NAVER,
            deposit=40000,
            area_sqm=84.0,
            households=1500,
            built_year=2020,
        )
        
        user_input = UserInput(
            max_deposit=50000,
            min_area_sqm=80,
        )
        
        result = engine.score(listing, user_input)
        
        assert result.total_score > 0
        assert result.total_score <= 100
        assert len(result.breakdown) > 0


class TestRiskEngine:
    """Risk Engine 테스트"""
    
    def test_risk_detection(self):
        """리스크 탐지 테스트"""
        from app.domain.risk_rules import RiskEngine
        from app.schemas.listing import Listing, ListingSource
        
        engine = RiskEngine()
        
        listing = Listing(
            id="test_004",
            source=ListingSource.NAVER,
            description="급매 협의가능 근저당 있음",
        )
        
        result = engine.analyze(listing)
        
        assert result.risk_score > 0
        assert len(result.risks) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
