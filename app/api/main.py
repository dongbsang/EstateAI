"""
PropLens FastAPI 메인
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="PropLens",
    description="AI 기반 부동산 매물 사전 검증 시스템",
    version="0.1.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """헬스 체크"""
    return {
        "name": "PropLens",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    """상세 헬스 체크"""
    return {
        "status": "healthy",
    }
