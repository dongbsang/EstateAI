"""
Pipeline Orchestrator
Agent들의 실행 순서를 제어하고 결과를 조합합니다.
"""

from loguru import logger
from app.schemas.user_input import UserInput
from app.schemas.results import Report, FilterStatus
from app.agents.search_agent import SearchAgent
from app.agents.enrich_agent import EnrichAgent, EnrichInput
from app.agents.commute_agent import CommuteAgent, CommuteInput
from app.agents.normalize_agent import NormalizeAgent
from app.agents.filter_agent import FilterAgent, FilterInput
from app.agents.score_agent import ScoreAgent, ScoreInput
from app.agents.risk_agent import RiskAgent
from app.agents.question_agent import QuestionAgent, QuestionInput
from app.agents.report_agent import ReportAgent, ReportInput


class PipelineOrchestrator:
    """
    파이프라인 오케스트레이터
    전체 분석 파이프라인을 관리합니다:

    [Phase 1: 수집 & 보강]
    Search → Enrich (단지정보/실거래가) → Normalize

    [Phase 2: 1차 필터링]
    Filter (예산/면적/세대수 등 기본 조건)

    [Phase 3: 통근 시간 계산] ← 필터 통과 매물만! (API 절약)
    Commute → 2차 필터링 (통근 시간 조건)

    [Phase 4: 분석 & 리포트]
    Score → Risk → Question → Report
    """

    def __init__(self, max_items_per_region: int = 50):
        self.search_agent = SearchAgent(max_items_per_region=max_items_per_region)
        self.enrich_agent = EnrichAgent()
        self.commute_agent = CommuteAgent()
        self.normalize_agent = NormalizeAgent()
        self.filter_agent = FilterAgent()
        self.score_agent = ScoreAgent()
        self.risk_agent = RiskAgent()
        self.question_agent = QuestionAgent()
        self.report_agent = ReportAgent()

        self.logger = logger.bind(component="Pipeline")

    def run(
        self,
        user_input: UserInput,
        skip_filtered: bool = True,
        enrich_data: bool = True,
    ) -> Report:
        """
        전체 파이프라인 실행
        """
        self.logger.info("Starting automated pipeline")

        # 1. 네이버 부동산에서 매물 자동 수집
        self.logger.info("Step 1: Searching listings...")
        listings = self.search_agent.run(user_input)

        if not listings:
            self.logger.warning("No listings found")
            return self._empty_report(user_input)

        self.logger.info(f"Found {len(listings)} listings")

        # 2. 단지정보/실거래가 추가 (통근 시간 제외)
        if enrich_data:
            self.logger.info("Step 2: Enriching with complex info & real price...")
            try:
                listings = self.enrich_agent.run(
                    EnrichInput(listings=listings, user_input=user_input)
                )
            except Exception as e:
                self.logger.warning(f"Enrich failed: {e}")

        # 3. 데이터 정규화
        self.logger.info("Step 3: Normalizing data...")
        for i, listing in enumerate(listings):
            try:
                listings[i] = self.normalize_agent.run(listing)
            except Exception as e:
                self.logger.warning(f"Normalize failed for {listing.id}: {e}")

        # 4. 기본 조건 필터링 (통근 시간 제외)
        self.logger.info("Step 4: Filtering listings (basic conditions)...")
        filter_results = {}
        passed_listings = []

        # 통근 시간 조건 임시 제거
        original_must_conditions = user_input.must_conditions.copy()
        temp_must_conditions = [c for c in user_input.must_conditions if c != "max_commute_minutes"]
        user_input.must_conditions = temp_must_conditions

        for listing in listings:
            try:
                result = self.filter_agent.run(
                    FilterInput(listing=listing, user_input=user_input)
                )
                filter_results[listing.id] = result

                if result.status != FilterStatus.FAIL:
                    passed_listings.append(listing)

            except Exception as e:
                self.logger.error(f"Filter failed for {listing.id}: {e}")

        # 원래 조건 복원
        user_input.must_conditions = original_must_conditions

        self.logger.info(f"1st filter passed: {len(passed_listings)}/{len(listings)}")

        # 통근 시간 계산 (필터 통과 매물만)
        commute_results = {}

        if user_input.commute_destination and passed_listings:
            self.logger.info(f"Step 5: Calculating commute time for {len(passed_listings)} passed listings...")

            try:
                commute_results = self.commute_agent.run(CommuteInput(
                    listings=passed_listings,
                    destination=user_input.commute_destination,
                    max_minutes=user_input.max_commute_minutes,
                ))

                # 통근 시간 조건이 필수인 경우 2차 필터링
                if "max_commute_minutes" in original_must_conditions and user_input.max_commute_minutes:
                    before_count = len(passed_listings)

                    for listing in passed_listings[:]:  # 복사본 순회
                        commute_result = commute_results.get(listing.id)

                        if commute_result and not commute_result.passed:
                            # 통근 시간 초과 → 탈락 처리
                            passed_listings.remove(listing)

                            # 필터 결과 업데이트
                            filter_result = filter_results.get(listing.id)
                            if filter_result:
                                filter_result.status = FilterStatus.FAIL
                                filter_result.failed_conditions.append("max_commute_minutes")
                                minutes = commute_result.commute_minutes
                                filter_result.failure_reasons["max_commute_minutes"] = \
                                    f"통근 시간 {minutes}분 > 상한 {user_input.max_commute_minutes}분"

                    self.logger.info(f"2nd filter (commute): {len(passed_listings)}/{before_count}")

            except Exception as e:
                self.logger.warning(f"Commute calculation failed: {e}")

        # 6. Score - 점수화
        self.logger.info("Step 6: Scoring listings...")
        score_results = {}

        for listing in listings:
            filter_result = filter_results.get(listing.id)

            if skip_filtered and filter_result:
                if filter_result.status == FilterStatus.FAIL:
                    continue

            try:
                result = self.score_agent.run(
                    ScoreInput(listing=listing, user_input=user_input)
                )
                score_results[listing.id] = result
            except Exception as e:
                self.logger.error(f"Score failed for {listing.id}: {e}")

        # 7. Risk - 리스크 분석
        self.logger.info("Step 7: Analyzing risks...")
        risk_results = {}
        for listing in listings:
            try:
                result = self.risk_agent.run(listing)
                risk_results[listing.id] = result
            except Exception as e:
                self.logger.error(f"Risk failed for {listing.id}: {e}")

        # 8. Question - 질문 생성
        self.logger.info("Step 8: Generating questions...")
        question_results = {}
        for listing in listings:
            try:
                risk_result = risk_results.get(listing.id)
                result = self.question_agent.run(
                    QuestionInput(listing=listing, risk_result=risk_result)
                )
                question_results[listing.id] = result
            except Exception as e:
                self.logger.error(f"Question failed for {listing.id}: {e}")

        # 9. Report - 최종 리포트 생성
        self.logger.info("Step 9: Generating report...")
        report = self.report_agent.run(ReportInput(
            listings=listings,
            user_input=user_input,
            filter_results=filter_results,
            score_results=score_results,
            risk_results=risk_results,
            question_results=question_results,
        ))

        self.logger.info(
            f"Pipeline complete: {report.passed_count}/{report.total_count} passed"
        )

        return report

    def _empty_report(self, user_input: UserInput) -> Report:
        """빈 리포트 생성"""
        from datetime import datetime

        return Report(
            created_at=datetime.now(),
            total_count=0,
            passed_count=0,
            top_recommendations=[],
            filtered_out=[],
            summary="검색 조건에 맞는 매물을 찾지 못했습니다. 조건을 완화해 보세요.",
            insights=["검색 결과가 없습니다."],
        )
