"""
PropLens API 라우터
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.user_input import UserInput
from app.schemas.results import Report
from app.pipeline import PipelineOrchestrator

router = APIRouter()


class SearchRequest(BaseModel):
    """자동 검색 요청"""
    user_input: UserInput
    max_items_per_region: int = 50
    enrich_data: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "user_input": {
                    "transaction_type": "전세",
                    "max_deposit": 45000,
                    "regions": ["강서구", "양천구", "영등포구"],
                    "min_area_sqm": 84.0,
                    "min_households": 1000,
                    "must_conditions": ["max_deposit", "min_area_sqm"]
                },
                "max_items_per_region": 50,
                "enrich_data": True
            }
        }


@router.post("/search", response_model=Report)
async def search_listings(request: SearchRequest) -> Report:
    """
    매물 자동 검색 및 분석

    네이버 부동산에서 조건에 맞는 매물을 자동으로 수집하고 분석합니다.

    - 지역별 매물 검색
    - 실거래가 데이터 보강 (선택)
    - 조건 필터링 및 점수화
    - 리스크 분석 및 질문 생성
    """
    try:
        orchestrator = PipelineOrchestrator(
            max_items_per_region=request.max_items_per_region
        )

        report = orchestrator.run(
            user_input=request.user_input,
            enrich_data=request.enrich_data,
        )

        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")


@router.get("/regions")
async def get_available_regions():
    """사용 가능한 지역 목록 조회"""
    from app.data_sources.region_codes import RegionCodeManager

    manager = RegionCodeManager()

    return {
        "seoul": list(manager.SEOUL_GU_CODES.keys()),
        "gyeonggi": list(manager.GYEONGGI_CODES.keys()),
    }


@router.get("/schema/user-input")
async def get_user_input_schema():
    """사용자 입력 스키마 조회"""
    return UserInput.model_json_schema()


@router.get("/schema/report")
async def get_report_schema():
    """리포트 스키마 조회"""
    return Report.model_json_schema()
