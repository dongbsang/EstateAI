"""
Pipeline Orchestrator
Agent들의 실행 순서를 제어하고 결과를 조합합니다.
"""

import time
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
        pipeline_start = time.time()
        print("\n" + "=" * 60)
        print("🏠 PropLens 파이프라인 시작")
        print("=" * 60)

        # 1. 매물 검색
        step_start = time.time()
        listings = self.search_agent.run(user_input)

        if not listings:
            print("❌ 검색 결과 없음")
            return self._empty_report(user_input)

        print(f"✅ Step 1. 매물 검색: {len(listings)}건 ({time.time()-step_start:.1f}초)")

        # 2. 데이터 보강 (단지정보/실거래가)
        if enrich_data:
            step_start = time.time()
            try:
                listings = self.enrich_agent.run(
                    EnrichInput(listings=listings, user_input=user_input)
                )
                print(f"✅ Step 2. 데이터 보강: {len(listings)}건 ({time.time()-step_start:.1f}초)")
            except Exception as e:
                print(f"⚠️ Step 2. 데이터 보강 실패: {e}")

        # 3. 데이터 정규화
        step_start = time.time()
        normalized_count = 0
        for i, listing in enumerate(listings):
            try:
                listings[i] = self.normalize_agent.run(listing)
                normalized_count += 1
            except Exception:
                pass
        print(f"✅ Step 3. 정규화: {normalized_count}/{len(listings)}건 ({time.time()-step_start:.1f}초)")

        # 4. 필터링
        step_start = time.time()
        filter_results = {}
        passed_listings = []

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
            except Exception:
                pass

        user_input.must_conditions = original_must_conditions
        print(f"✅ Step 4. 필터링: {len(passed_listings)}/{len(listings)}건 통과 ({time.time()-step_start:.1f}초)")

        # 5. 통근 시간 계산
        commute_results = {}
        if user_input.commute_destination and passed_listings:
            step_start = time.time()
            try:
                commute_results = self.commute_agent.run(CommuteInput(
                    listings=passed_listings,
                    destination=user_input.commute_destination,
                    max_minutes=user_input.max_commute_minutes,
                ))

                if "max_commute_minutes" in original_must_conditions and user_input.max_commute_minutes:
                    before_count = len(passed_listings)
                    for listing in passed_listings[:]:
                        commute_result = commute_results.get(listing.id)
                        if commute_result and not commute_result.passed:
                            passed_listings.remove(listing)
                            filter_result = filter_results.get(listing.id)
                            if filter_result:
                                filter_result.status = FilterStatus.FAIL
                                filter_result.failed_conditions.append("max_commute_minutes")
                                minutes = commute_result.commute_minutes
                                filter_result.failure_reasons["max_commute_minutes"] = \
                                    f"통근 시간 {minutes}분 > 상한 {user_input.max_commute_minutes}분"

                    print(f"✅ Step 5. 통근시간: {len(passed_listings)}/{before_count}건 통과 ({time.time()-step_start:.1f}초)")
                else:
                    print(f"✅ Step 5. 통근시간: {len(commute_results)}건 계산 ({time.time()-step_start:.1f}초)")
            except Exception as e:
                print(f"⚠️ Step 5. 통근시간 계산 실패: {e}")

        # 6. 점수화
        step_start = time.time()
        score_results = {}
        for listing in listings:
            filter_result = filter_results.get(listing.id)
            if skip_filtered and filter_result and filter_result.status == FilterStatus.FAIL:
                continue
            try:
                result = self.score_agent.run(
                    ScoreInput(listing=listing, user_input=user_input)
                )
                score_results[listing.id] = result
            except Exception:
                pass
        print(f"✅ Step 6. 점수화: {len(score_results)}건 ({time.time()-step_start:.1f}초)")

        # 7. 리스크 분석
        step_start = time.time()
        risk_results = {}
        for listing in listings:
            try:
                result = self.risk_agent.run(listing)
                risk_results[listing.id] = result
            except Exception:
                pass
        print(f"✅ Step 7. 리스크: {len(risk_results)}건 ({time.time()-step_start:.1f}초)")

        # 8. 질문 생성
        step_start = time.time()
        question_results = {}
        for listing in listings:
            try:
                risk_result = risk_results.get(listing.id)
                result = self.question_agent.run(
                    QuestionInput(listing=listing, risk_result=risk_result)
                )
                question_results[listing.id] = result
            except Exception:
                pass
        print(f"✅ Step 8. 질문생성: {len(question_results)}건 ({time.time()-step_start:.1f}초)")

        # 9. 리포트 생성
        step_start = time.time()
        report = self.report_agent.run(ReportInput(
            listings=listings,
            user_input=user_input,
            filter_results=filter_results,
            score_results=score_results,
            risk_results=risk_results,
            question_results=question_results,
        ))
        print(f"✅ Step 9. 리포트: 완료 ({time.time()-step_start:.1f}초)")

        # 최종 요약
        total_time = time.time() - pipeline_start
        print("\n" + "-" * 60)
        print("📊 파이프라인 완료")
        print(f"   전체 매물: {report.total_count}건")
        print(f"   조건 충족: {report.passed_count}건")
        print(f"   총 소요시간: {total_time:.1f}초")
        print("-" * 60 + "\n")

        return report

    def _empty_report(self, user_input: UserInput) -> Report:
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
