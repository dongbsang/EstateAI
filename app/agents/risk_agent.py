"""
Risk Agent
매물의 리스크를 분석합니다.
"""

from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.results import RiskResult
from app.domain.risk_rules import RiskEngine


class RiskAgent(BaseAgent[Listing, RiskResult]):
    """
    리스크 분석 Agent
    
    규칙 기반 RiskEngine을 사용하여 리스크를 탐지합니다.
    추후 LLM을 활용한 텍스트 분석을 추가할 수 있습니다.
    """
    
    name = "RiskAgent"
    
    def __init__(self):
        super().__init__()
        self.engine = RiskEngine()
    
    def _process(self, listing: Listing) -> RiskResult:
        """리스크 분석 실행"""
        return self.engine.analyze(listing)
