"""
LLM Runner
llama.cpp를 사용한 로컬 LLM 실행 래퍼입니다.
"""

import os
from typing import Optional
from pathlib import Path
from loguru import logger

# llama-cpp-python이 설치되지 않았을 때 graceful 처리
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False
    Llama = None


class LLMRunner:
    """
    llama.cpp 래퍼

    GGUF 모델을 로드하고 텍스트 생성을 수행합니다.
    MVP에서는 주로 다음 용도로 사용:
    - 매물 설명 요약
    - 리스크 신호 추출 (규칙 보완)
    - 질문 문장 다듬기
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
    ):
        """
        Args:
            model_path: GGUF 모델 파일 경로
            n_ctx: 컨텍스트 윈도우 크기
            n_gpu_layers: GPU 오프로드 레이어 수 (0이면 CPU only)
        """
        self.model_path = model_path or os.getenv(
            "MODEL_PATH",
            "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
        )
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self._model: Optional[Llama] = None
        self.logger = logger.bind(component="LLMRunner")

    @property
    def is_available(self) -> bool:
        """LLM 사용 가능 여부"""
        if not LLAMA_AVAILABLE:
            return False
        return Path(self.model_path).exists()

    def load(self) -> bool:
        """모델 로드"""
        if not LLAMA_AVAILABLE:
            self.logger.warning("llama-cpp-python이 설치되지 않았습니다.")
            return False

        if not Path(self.model_path).exists():
            self.logger.warning(f"모델 파일이 없습니다: {self.model_path}")
            return False

        try:
            self.logger.info(f"Loading model: {self.model_path}")
            self._model = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                verbose=False,
            )
            self.logger.info("Model loaded successfully")
            return True
        except Exception as e:
            self.logger.error(f"Model loading failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: Optional[list[str]] = None,
    ) -> str:
        """
        텍스트 생성

        Args:
            prompt: 입력 프롬프트
            max_tokens: 최대 생성 토큰 수
            temperature: 샘플링 온도
            stop: 중단 시퀀스

        Returns:
            생성된 텍스트
        """
        if self._model is None:
            if not self.load():
                return "[LLM 사용 불가]"

        try:
            output = self._model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop or ["</s>", "\n\n"],
            )
            return output["choices"][0]["text"].strip()
        except Exception as e:
            self.logger.error(f"Generation failed: {e}")
            return f"[생성 실패: {e}]"

    def extract_json(
        self,
        prompt: str,
        max_tokens: int = 1024,
    ) -> dict:
        """
        JSON 형식 응답 추출

        프롬프트에 JSON 형식을 요청하고 파싱합니다.
        """
        import json

        response = self.generate(
            prompt=prompt + "\n\nJSON 형식으로만 응답하세요:",
            max_tokens=max_tokens,
            temperature=0.3,
            stop=["```", "\n\n\n"],
        )

        # JSON 추출 시도
        try:
            # ```json ... ``` 패턴 처리
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except json.JSONDecodeError:
            self.logger.warning(f"JSON 파싱 실패: {response[:100]}")
            return {"error": "JSON 파싱 실패", "raw": response}


# 싱글톤 인스턴스
_runner: Optional[LLMRunner] = None


def get_llm_runner() -> LLMRunner:
    """LLM Runner 싱글톤 인스턴스 반환"""
    global _runner
    if _runner is None:
        _runner = LLMRunner()
    return _runner
