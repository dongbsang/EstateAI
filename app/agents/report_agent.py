"""
Report Agent
최종 분석 리포트를 생성합니다.
"""

from datetime import datetime
from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.schemas.results import (
    Report,
    ListingReport,
    FilterResult,
    ScoredListing,
    RiskResult,
    QuestionResult,
    FilterStatus,
)


class ReportInput:
    """Report Agent 입력"""
    def __init__(
        self,
        listings: list[Listing],
        user_input: UserInput,
        filter_results: dict[str, FilterResult],
        score_results: dict[str, ScoredListing],
        risk_results: dict[str, RiskResult],
        question_results: dict[str, QuestionResult],
    ):
        self.listings = listings
        self.user_input = user_input
        self.filter_results = filter_results
        self.score_results = score_results
        self.risk_results = risk_results
        self.question_results = question_results


class ReportAgent(BaseAgent[ReportInput, Report]):
    """
    리포트 생성 Agent

    모든 분석 결과를 종합하여 최종 리포트를 생성합니다.
    - 추천 매물 순위
    - 탈락 매물 및 사유
    - 전체 요약 및 인사이트
    """

    name = "ReportAgent"

    def _process(self, input_data: ReportInput) -> Report:
        """리포트 생성"""

        top_recommendations = []
        filtered_out = []

        for listing in input_data.listings:
            lid = listing.id

            # 각 결과 조회
            filter_result = input_data.filter_results.get(lid)
            score_result = input_data.score_results.get(lid)
            risk_result = input_data.risk_results.get(lid)
            question_result = input_data.question_results.get(lid)

            # ListingReport 생성
            report = ListingReport(
                listing=listing,
                filter_result=filter_result,
                score_result=score_result,
                risk_result=risk_result,
                question_result=question_result,
            )

            # 통과/탈락 분류
            if filter_result and filter_result.status == FilterStatus.FAIL:
                filtered_out.append(report)
            else:
                top_recommendations.append(report)

        # 점수순 정렬
        top_recommendations.sort(
            key=lambda r: r.score_result.total_score if r.score_result else 0,
            reverse=True
        )

        # 순위 부여
        for i, report in enumerate(top_recommendations):
            if report.score_result:
                report.score_result.rank = i + 1

        # 요약 생성
        summary = self._generate_summary(
            top_recommendations, filtered_out, input_data.user_input
        )

        # 인사이트 생성
        insights = self._generate_insights(
            top_recommendations, filtered_out, input_data
        )

        return Report(
            created_at=datetime.now(),
            total_count=len(input_data.listings),
            passed_count=len(top_recommendations),
            top_recommendations=top_recommendations,
            filtered_out=filtered_out,
            summary=summary,
            insights=insights,
        )

    def _generate_summary(
        self,
        passed: list[ListingReport],
        failed: list[ListingReport],
        user_input: UserInput,
    ) -> str:
        """요약 문장 생성"""
        total = len(passed) + len(failed)

        if not passed:
            return f"분석한 {total}개 매물 중 조건에 맞는 매물이 없습니다. 조건을 완화해 보세요."

        top = passed[0]
        top_name = top.listing.title or top.listing.complex_name or "1순위 매물"
        top_score = top.score_result.total_score if top.score_result else 0

        summary = f"{total}개 매물 중 {len(passed)}개가 조건에 부합합니다. "
        summary += f"'{top_name}'이(가) {top_score:.1f}점으로 가장 추천됩니다."

        if failed:
            # 주요 탈락 사유
            fail_reasons = []
            for report in failed[:3]:
                if report.filter_result and report.filter_result.failure_reasons:
                    for reason in report.filter_result.failure_reasons.values():
                        if reason not in fail_reasons:
                            fail_reasons.append(reason)

            if fail_reasons:
                summary += f" 탈락 매물의 주요 사유: {fail_reasons[0]}"

        return summary

    def _generate_insights(
        self,
        passed: list[ListingReport],
        failed: list[ListingReport],
        input_data: ReportInput,
    ) -> list[str]:
        """인사이트 생성"""
        insights = []

        # 1. 가격 분석
        deposits = [
            r.listing.deposit for r in passed
            if r.listing.deposit
        ]
        if deposits:
            avg_deposit = sum(deposits) / len(deposits)
            min_deposit = min(deposits)
            insights.append(
                f"조건 충족 매물의 평균 보증금: {avg_deposit/10000:.1f}억원 "
                f"(최저 {min_deposit/10000:.1f}억원)"
            )

        # 2. 세대수 분석
        large_complex = [
            r for r in passed
            if r.listing.households and r.listing.households >= 1000
        ]
        if large_complex:
            insights.append(
                f"1,000세대 이상 대단지: {len(large_complex)}개"
            )

        # 3. 리스크 분석
        high_risk = [
            r for r in passed
            if r.risk_result and r.risk_result.risk_score >= 50
        ]
        if high_risk:
            insights.append(
                f"리스크 점수 50점 이상 매물 {len(high_risk)}개 - 주의 필요"
            )

        # 4. 탈락 패턴 분석
        if failed:
            fail_counts = {}
            for report in failed:
                if report.filter_result:
                    for condition in report.filter_result.failed_conditions:
                        fail_counts[condition] = fail_counts.get(condition, 0) + 1

            if fail_counts:
                top_fail = max(fail_counts, key=fail_counts.get)
                insights.append(
                    f"가장 많은 탈락 사유: {top_fail} ({fail_counts[top_fail]}건)"
                )

        return insights
