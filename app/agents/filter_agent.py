"""
Filter Agent
사용자 조건에 따라 매물을 필터링합니다.
"""

from .base import BaseAgent
from app.schemas.listing import Listing
from app.schemas.user_input import UserInput
from app.schemas.results import FilterResult
from app.domain.filters import FilterEngine


class FilterInput:
    """Filter Agent 입력"""
    def __init__(self, listing: Listing, user_input: UserInput):
        self.listing = listing
        self.user_input = user_input


class FilterAgent(BaseAgent[FilterInput, FilterResult]):
    """
    필터링 Agent

    규칙 기반 FilterEngine을 사용하여 매물을 필터링합니다.
    LLM은 사용하지 않습니다.
    """

    name = "FilterAgent"

    def __init__(self):
        super().__init__()
        self.engine = FilterEngine()

    def _process(self, input_data: FilterInput) -> FilterResult:
        """필터링 실행"""
        return self.engine.filter(
            listing=input_data.listing,
            user_input=input_data.user_input
        )
