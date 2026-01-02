"""
리스크 엔진
규칙 기반으로 매물 리스크를 탐지합니다.
"""

import re
from loguru import logger

from app.schemas.listing import Listing
from app.schemas.results import RiskResult, RiskItem, RiskLevel


class RiskEngine:
    """
    규칙 기반 리스크 탐지 엔진

    매물 정보와 설명에서 리스크 신호를 탐지합니다.
    각 리스크에 대해 확인 방법/조치사항을 함께 제공합니다.
    """

    # 리스크 패턴 정의
    RISK_PATTERNS = [
        # 보증보험 관련
        (
            r"보증보험\s*(불가|어려|힘들|안.?됨)",
            "보증보험",
            RiskLevel.HIGH,
            "전세보증보험 가입 불가 가능성",
            "보증보험 가입이 어려울 수 있습니다.",
            "HUG/SGI 보증보험 가입 가능 여부를 중개사에게 반드시 확인하세요."
        ),
        (
            r"(법인|회사)\s*(소유|명의|임대)",
            "보증보험",
            RiskLevel.MEDIUM,
            "법인 소유 매물",
            "법인 소유 매물은 보증보험 조건이 까다로울 수 있습니다.",
            "법인 정보 및 보증보험 가입 가능 여부를 확인하세요."
        ),
        # 권리관계
        (
            r"근저당|담보|저당",
            "권리관계",
            RiskLevel.HIGH,
            "근저당 설정 가능성",
            "근저당이 설정되어 있을 수 있습니다.",
            "등기부등본에서 근저당 설정액과 채권최고액을 확인하세요."
        ),
        (
            r"선순위|후순위|채권",
            "권리관계",
            RiskLevel.HIGH,
            "선순위 권리 존재 가능성",
            "선순위 권리가 존재할 수 있습니다.",
            "등기부등본에서 권리 순위를 확인하세요."
        ),
        (
            r"경매|압류|가압류|가처분",
            "권리관계",
            RiskLevel.HIGH,
            "법적 분쟁 가능성",
            "경매 또는 법적 절차가 진행 중일 수 있습니다.",
            "등기부등본 및 법원 경매정보를 확인하세요."
        ),
        # 계약조건
        (
            r"(급매|급처분|급하게)",
            "계약조건",
            RiskLevel.MEDIUM,
            "급매물",
            "급하게 매물을 내놓은 경우 숨은 문제가 있을 수 있습니다.",
            "급매 사유를 반드시 확인하세요."
        ),
        (
            r"(협의|조정|상담\s*후)",
            "계약조건",
            RiskLevel.LOW,
            "가격 협의 가능",
            "가격 협의가 가능한 매물입니다.",
            "시세 대비 적정가격인지 확인 후 협상하세요."
        ),
        (
            r"(단기|1년|6개월)\s*(계약|임대)",
            "계약조건",
            RiskLevel.MEDIUM,
            "단기 계약",
            "단기 계약 조건이 있을 수 있습니다.",
            "계약 기간과 연장 조건을 확인하세요."
        ),
        # 건물상태
        (
            r"(누수|습기|곰팡이|결로)",
            "건물상태",
            RiskLevel.HIGH,
            "누수/습기 문제",
            "건물에 누수 또는 습기 문제가 있을 수 있습니다.",
            "현장 방문 시 벽면, 천장, 창틀 상태를 꼼꼼히 확인하세요."
        ),
        (
            r"(소음|층간소음|도로소음)",
            "건물상태",
            RiskLevel.MEDIUM,
            "소음 이슈",
            "소음 문제가 있을 수 있습니다.",
            "방문 시 낮/밤 시간대별 소음 수준을 확인하세요."
        ),
        (
            r"(현상태|현재상태|있는\s*그대로)",
            "건물상태",
            RiskLevel.MEDIUM,
            "현상태 인도",
            "수리나 정비 없이 현재 상태로 인도됩니다.",
            "수리 필요 항목과 비용을 미리 파악하세요."
        ),
        # 입주조건
        (
            r"(즉시입주|바로입주|입주\s*가능)",
            "입주조건",
            RiskLevel.INFO,
            "즉시 입주 가능",
            "바로 입주할 수 있는 매물입니다.",
            "빠른 입주가 필요하면 유리한 조건입니다."
        ),
        (
            r"(협의\s*후\s*입주|입주\s*협의)",
            "입주조건",
            RiskLevel.LOW,
            "입주일 협의 필요",
            "입주일을 협의해야 합니다.",
            "희망 입주일에 맞출 수 있는지 확인하세요."
        ),
        # 전세가율 관련 (description에서 탐지)
        (
            r"전세가율.{0,10}(위험|80%|85%|90%)",
            "전세가율",
            RiskLevel.HIGH,
            "높은 전세가율 (깡통전세 위험)",
            "전세가율이 80% 이상으로 깡통전세 위험이 있습니다.",
            "집값 하락 시 보증금 회수가 어려울 수 있습니다. 전세보증보험 필수 가입하세요."
        ),
        (
            r"전세가율.{0,10}(주의|70%|75%)",
            "전세가율",
            RiskLevel.MEDIUM,
            "전세가율 주의 필요",
            "전세가율이 70% 이상으로 주의가 필요합니다.",
            "향후 집값 변동 추이를 확인하고 보증보험 가입을 권장합니다."
        ),
        (
            r"깡통전세",
            "전세가율",
            RiskLevel.HIGH,
            "깡통전세 경고",
            "깡통전세 위험 신호가 감지되었습니다.",
            "등기부등본 확인, 보증보험 가입 필수, 집주인 재정상태 확인 권장."
        ),
    ]

    def analyze(self, listing: Listing) -> RiskResult:
        """
        매물의 리스크를 분석합니다.

        Args:
            listing: 매물 정보

        Returns:
            RiskResult: 리스크 분석 결과
        """
        risks = []

        # 텍스트 결합 (설명 + 제목)
        text_to_check = ""
        if listing.description:
            text_to_check += listing.description
        if listing.title:
            text_to_check += " " + listing.title

        # 패턴 매칭
        for pattern, category, level, title, desc, action in self.RISK_PATTERNS:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                risks.append(RiskItem(
                    category=category,
                    level=level,
                    title=title,
                    description=desc,
                    check_action=action,
                    source=self._extract_context(text_to_check, pattern)
                ))

        # 구조적 리스크 체크
        risks.extend(self._check_structural_risks(listing))

        # 중복 제거 (같은 카테고리의 같은 제목)
        seen = set()
        unique_risks = []
        for risk in risks:
            key = (risk.category, risk.title)
            if key not in seen:
                seen.add(key)
                unique_risks.append(risk)
        risks = unique_risks

        # 리스크 점수 계산
        risk_score = self._calculate_risk_score(risks)

        # 요약 생성
        summary = self._generate_summary(risks)

        result = RiskResult(
            listing_id=listing.id,
            risk_score=risk_score,
            risks=risks,
            summary=summary
        )

        logger.debug(f"Risk score for {listing.id}: {risk_score}")
        return result

    def _check_structural_risks(self, listing: Listing) -> list[RiskItem]:
        """구조적 데이터 기반 리스크 체크"""
        risks = []

        # 세대수 리스크
        if listing.households and listing.households < 100:
            risks.append(RiskItem(
                category="단지규모",
                level=RiskLevel.MEDIUM,
                title="소규모 단지",
                description=f"{listing.households}세대 소규모 단지입니다.",
                check_action="관리 상태와 관리비를 확인하세요."
            ))

        # 연식 리스크
        if listing.built_year and (2025 - listing.built_year) > 30:
            risks.append(RiskItem(
                category="건물연식",
                level=RiskLevel.MEDIUM,
                title="노후 건물",
                description=f"{listing.built_year}년 준공으로 {2025 - listing.built_year}년 경과",
                check_action="배관, 전기 시설 상태를 확인하세요."
            ))

        # 1층/탑층 리스크
        if listing.floor == 1:
            risks.append(RiskItem(
                category="층수",
                level=RiskLevel.LOW,
                title="1층 매물",
                description="1층은 프라이버시, 소음, 습기 이슈가 있을 수 있습니다.",
                check_action="방범, 채광, 환기 상태를 확인하세요."
            ))
        elif listing.floor and listing.total_floors and listing.floor == listing.total_floors:
            risks.append(RiskItem(
                category="층수",
                level=RiskLevel.LOW,
                title="최상층 매물",
                description="최상층은 누수, 단열 이슈가 있을 수 있습니다.",
                check_action="천장 누수 흔적과 단열 상태를 확인하세요."
            ))

        # 주차 리스크
        if listing.parking_per_household and listing.parking_per_household < 0.5:
            risks.append(RiskItem(
                category="주차",
                level=RiskLevel.MEDIUM,
                title="주차 부족",
                description=f"세대당 주차 {listing.parking_per_household}대로 부족합니다.",
                check_action="실제 주차 가능 여부와 대기 현황을 확인하세요."
            ))

        return risks

    def _extract_context(self, text: str, pattern: str) -> str:
        """매칭된 패턴 주변 문맥 추출"""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            return f"...{text[start:end]}..."
        return ""

    def _calculate_risk_score(self, risks: list[RiskItem]) -> int:
        """리스크 점수 계산 (0-100)"""
        score = 0
        for risk in risks:
            if risk.level == RiskLevel.HIGH:
                score += 25
            elif risk.level == RiskLevel.MEDIUM:
                score += 15
            elif risk.level == RiskLevel.LOW:
                score += 5
            # INFO는 점수에 영향 없음
        return min(score, 100)

    def _generate_summary(self, risks: list[RiskItem]) -> str:
        """리스크 요약 생성"""
        if not risks:
            return "특별한 리스크 신호가 발견되지 않았습니다. 그러나 등기부등본 확인은 필수입니다."

        high_risks = [r for r in risks if r.level == RiskLevel.HIGH]
        medium_risks = [r for r in risks if r.level == RiskLevel.MEDIUM]

        parts = []
        if high_risks:
            parts.append(f"주의가 필요한 항목 {len(high_risks)}개")
        if medium_risks:
            parts.append(f"확인이 필요한 항목 {len(medium_risks)}개")

        summary = ", ".join(parts) + "가 있습니다. " if parts else ""

        # 가장 중요한 리스크 언급 (전세가율 우선)
        jeonse_risks = [r for r in high_risks if r.category == "전세가율"]
        if jeonse_risks:
            summary += f"⚠️ '{jeonse_risks[0].title}'에 대해 반드시 확인이 필요합니다."
        elif high_risks:
            summary += f"특히 '{high_risks[0].title}'에 대해 반드시 확인이 필요합니다."

        return summary
