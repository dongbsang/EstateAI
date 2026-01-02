"""
GGUF 모델 다운로드 스크립트

사용법:
    python download_model.py

기본으로 Qwen2.5-7B-Instruct Q4_K_M 모델을 다운로드합니다.
더 작은 모델이 필요하면 MODEL_ID를 변경하세요.
"""

import os
import sys

# 모델 선택 (용량/성능 트레이드오프)
MODELS = {
    "7b": {
        "repo": "bartowski/Qwen2.5-7B-Instruct-GGUF",
        "file": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "size": "4.68 GB",
    },
    "3b": {
        "repo": "bartowski/Qwen2.5-3B-Instruct-GGUF",
        "file": "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        "size": "2.0 GB",
    },
    "1.5b": {
        "repo": "bartowski/Qwen2.5-1.5B-Instruct-GGUF",
        "file": "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
        "size": "1.0 GB",
    },
}

# 기본 모델 (변경 가능)
DEFAULT_MODEL = "7b"


def download_model(model_key: str = DEFAULT_MODEL):
    """Hugging Face에서 모델 다운로드"""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("huggingface_hub 설치 중...")
        os.system(f"{sys.executable} -m pip install huggingface_hub")
        from huggingface_hub import hf_hub_download
    
    model = MODELS.get(model_key, MODELS[DEFAULT_MODEL])
    
    print(f"\n{'='*50}")
    print(f"모델 다운로드: {model['file']}")
    print(f"크기: {model['size']}")
    print(f"{'='*50}\n")
    
    # models 폴더 경로
    script_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(script_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    # 다운로드
    filepath = hf_hub_download(
        repo_id=model["repo"],
        filename=model["file"],
        local_dir=models_dir,
        local_dir_use_symlinks=False,
    )
    
    print(f"\n✅ 다운로드 완료!")
    print(f"경로: {filepath}")
    
    # .env 파일 업데이트 안내
    print(f"\n📝 .env 파일에 다음을 추가하세요:")
    print(f"MODEL_PATH=models/{model['file']}")
    
    return filepath


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GGUF 모델 다운로드")
    parser.add_argument(
        "--model",
        choices=["7b", "3b", "1.5b"],
        default=DEFAULT_MODEL,
        help="다운로드할 모델 크기 (기본: 7b)"
    )
    
    args = parser.parse_args()
    
    print("\n🚀 PropLens GGUF 모델 다운로더")
    print("-" * 40)
    print("사용 가능한 모델:")
    for key, info in MODELS.items():
        marker = "→" if key == args.model else " "
        print(f"  {marker} {key}: {info['file']} ({info['size']})")
    
    download_model(args.model)
