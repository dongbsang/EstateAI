"""
Agent 기본 클래스
모든 Agent가 상속받는 추상 기본 클래스입니다.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from loguru import logger

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Agent 기본 클래스

    모든 Agent는 이 클래스를 상속받아 구현합니다.
    - 입출력 타입이 명확하게 정의됩니다.
    - 에러 처리가 일관되게 됩니다.
    """

    name: str = "BaseAgent"

    def __init__(self):
        self.logger = logger.bind(agent=self.name)

    def run(self, input_data: InputT) -> OutputT:
        """
        Agent를 실행합니다.

        Args:
            input_data: 입력 데이터

        Returns:
            출력 데이터
        """
        try:
            # 입력 검증
            self._validate_input(input_data)

            # 실제 처리
            result = self._process(input_data)

            # 출력 검증
            self._validate_output(result)

            return result

        except Exception as e:
            self.logger.error(f"{self.name} 오류: {e}")
            raise

    @abstractmethod
    def _process(self, input_data: InputT) -> OutputT:
        """
        실제 처리 로직 (서브클래스에서 구현)
        """
        pass

    def _validate_input(self, input_data: InputT) -> None:
        """입력 데이터 검증 (필요시 오버라이드)"""
        if input_data is None:
            raise ValueError(f"{self.name}: 입력 데이터가 None입니다.")

    def _validate_output(self, output_data: OutputT) -> None:
        """출력 데이터 검증 (필요시 오버라이드)"""
        if output_data is None:
            raise ValueError(f"{self.name}: 출력 데이터가 None입니다.")
