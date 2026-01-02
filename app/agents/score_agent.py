"""
Score Agent
매물의 점수를 산정합니다.
"""

from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.schemas.results import ScoredListing
from app.domain.scoring import ScoringEngine


class ScoreInput:
    """Score Agent 입력"""
    def __init__(self, listing: Listing, user_input: UserInput):
        self.listing = listing
        self.user_input = user_input


class ScoreAgent(BaseAgent[ScoreInput, ScoredListing]):
    """
    점수화 Agent
    
    규칙 기반 ScoringEngine을 사용하여 점수를 산정합니다.
    LLM은 사용하지 않습니다.
    """
    
    name = "ScoreAgent"
    
    def __init__(self):
        super().__init__()
        self.engine = ScoringEngine()
    
    def _process(self, input_data: ScoreInput) -> ScoredListing:
        """점수 산정 실행"""
        return self.engine.score(
            listing=input_data.listing,
            user_input=input_data.user_input
        )
