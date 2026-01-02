"""
Question Agent
중개사에게 물어볼 질문을 생성합니다.
"""

from typing import Optional
from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.results import RiskResult, QuestionResult, RiskLevel


class QuestionInput:
    """Question Agent 입력"""
    def __init__(self, listing: Listing, risk_result: Optional[RiskResult] = None):
        self.listing = listing
        self.risk_result = risk_result


class QuestionAgent(BaseAgent[QuestionInput, QuestionResult]):
    """
    질문 생성 Agent

    매물 정보와 리스크 분석 결과를 바탕으로
    중개사에게 물어볼 질문 목록을 생성합니다.

    - 규칙 기반 기본 질문
    - 리스크 기반 추가 질문
    - (추후) LLM 기반 맞춤 질문
    """

    name = "QuestionAgent"

    # 기본 질문 템플릿 (모든 매물 공통)
    BASE_QUESTIONS = [
        ("전세보증보험(HUG/SGI) 가입이 가능한가요?", "전세 사기 예방을 위한 필수 확인 사항"),
        ("등기부등본상 근저당이나 가압류가 있나요?", "권리관계 확인"),
        ("실제 입주 가능일이 언제인가요?", "입주 일정 확인"),
        ("현재 임차인이 있나요? 있다면 보증금은 얼마인가요?", "선순위 임차인 확인"),
        ("관리비에 포함된 항목과 별도 청구 항목은 무엇인가요?", "실제 월 비용 파악"),
    ]

    # 조건별 추가 질문
    CONDITIONAL_QUESTIONS = {
        "no_households": [
            ("단지 총 세대수가 몇 세대인가요?", "단지 규모 파악"),
        ],
        "no_parking": [
            ("주차가 가능한가요? 세대당 주차 대수는?", "주차 가능 여부 확인"),
        ],
        "old_building": [
            ("최근 배관/전기 공사 이력이 있나요?", "노후 시설 상태 확인"),
            ("리모델링 계획이 있나요?", "향후 추가 비용 가능성"),
        ],
        "first_floor": [
            ("방범 시설이 어떻게 되어 있나요?", "1층 보안 확인"),
            ("습기나 결로 문제가 있었나요?", "1층 습기 문제 확인"),
        ],
        "top_floor": [
            ("옥상 방수 공사는 언제 했나요?", "누수 가능성 확인"),
            ("여름철 단열은 어떤가요?", "최상층 단열 확인"),
        ],
        "high_deposit": [
            ("전세가율이 어느 정도인가요?", "깡통전세 위험 확인"),
            ("최근 실거래가 대비 적정한 가격인가요?", "가격 적정성 확인"),
        ],
    }

    def _process(self, input_data: QuestionInput) -> QuestionResult:
        """질문 생성"""
        listing = input_data.listing
        risk_result = input_data.risk_result

        questions = []
        reasons = {}

        # 1. 기본 질문 추가
        for q, reason in self.BASE_QUESTIONS:
            questions.append(q)
            reasons[q] = reason

        # 2. 조건별 질문 추가
        conditional_qs = self._get_conditional_questions(listing)
        for q, reason in conditional_qs:
            if q not in questions:
                questions.append(q)
                reasons[q] = reason

        # 3. 리스크 기반 질문 추가
        if risk_result:
            risk_qs = self._get_risk_questions(risk_result)
            for q, reason in risk_qs:
                if q not in questions:
                    questions.append(q)
                    reasons[q] = reason

        # 4. 매물 특성 기반 질문 추가
        specific_qs = self._get_specific_questions(listing)
        for q, reason in specific_qs:
            if q not in questions:
                questions.append(q)
                reasons[q] = reason

        return QuestionResult(
            listing_id=listing.id,
            questions=questions,
            question_reasons=reasons
        )

    def _get_conditional_questions(
        self, listing: Listing
    ) -> list[tuple[str, str]]:
        """조건별 질문 선택"""
        questions = []

        # 세대수 정보 없음
        if listing.households is None:
            questions.extend(self.CONDITIONAL_QUESTIONS["no_households"])

        # 주차 정보 없음
        if listing.has_parking is None and listing.parking_per_household is None:
            questions.extend(self.CONDITIONAL_QUESTIONS["no_parking"])

        # 노후 건물 (20년 이상)
        if listing.built_year and (2025 - listing.built_year) >= 20:
            questions.extend(self.CONDITIONAL_QUESTIONS["old_building"])

        # 1층
        if listing.floor == 1:
            questions.extend(self.CONDITIONAL_QUESTIONS["first_floor"])

        # 최상층
        if (listing.floor and listing.total_floors and listing.floor == listing.total_floors):
            questions.extend(self.CONDITIONAL_QUESTIONS["top_floor"])

        # 고액 보증금 (4억 이상)
        if listing.deposit and listing.deposit >= 40000:
            questions.extend(self.CONDITIONAL_QUESTIONS["high_deposit"])

        return questions

    def _get_risk_questions(
        self, risk_result: RiskResult
    ) -> list[tuple[str, str]]:
        """리스크 기반 질문 생성"""
        questions = []

        for risk in risk_result.risks:
            if risk.level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
                # 리스크 확인 조치를 질문으로 변환
                q = f"{risk.title}와 관련해서 상태가 어떤가요?"
                questions.append((q, f"리스크 탐지: {risk.description}"))

        return questions

    def _get_specific_questions(
        self, listing: Listing
    ) -> list[tuple[str, str]]:
        """매물 특성 기반 맞춤 질문"""
        questions = []

        # 오피스텔인 경우
        if listing.property_type and "오피스텔" in listing.property_type:
            questions.append((
                "주거용으로 사용 가능한가요? 전입신고가 되나요?",
                "오피스텔 용도 확인"
            ))
            questions.append((
                "주거용/업무용 비율이 어떻게 되나요?",
                "오피스텔 단지 구성 확인"
            ))

        # 빌라/다세대인 경우
        if listing.property_type and listing.property_type in ["빌라", "다세대"]:
            questions.append((
                "건물 전체 소유주가 동일한가요?",
                "빌라 소유 구조 확인"
            ))
            questions.append((
                "관리인이 상주하나요?",
                "관리 상태 확인"
            ))

        # 반지하/지하인 경우 (층수가 0 이하)
        if listing.floor is not None and listing.floor <= 0:
            questions.append((
                "침수 이력이 있나요?",
                "반지하/지하 침수 위험"
            ))
            questions.append((
                "환기 시설이 어떻게 되어 있나요?",
                "반지하/지하 환기 확인"
            ))

        return questions
