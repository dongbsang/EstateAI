"""
간단한 테스트 스크립트
"""
import sys
sys.path.insert(0, ".")

print("=" * 50)
print("PropLens 테스트 시작")
print("=" * 50)

# 1. Import 테스트
print("\n[1] Import 테스트...")
try:
    from app.agents.parse_agent import ParseAgent, ParseInput
    from app.schemas.listing import ListingSource
    from app.schemas.user_input import UserInput
    from app.pipeline import PipelineOrchestrator
    print("✅ 모든 모듈 import 성공")
except Exception as e:
    print(f"❌ Import 실패: {e}")
    sys.exit(1)

# 2. Parse Agent 테스트
print("\n[2] Parse Agent 테스트...")
try:
    agent = ParseAgent()
    text = "래미안목동 전세 4억5000 84㎡ 15/25층 2020년 준공 1500세대"
    inp = ParseInput(text=text, source=ListingSource.MANUAL)
    result = agent.run(inp)
    
    print(f"  거래유형: {result.transaction_type}")
    print(f"  보증금: {result.deposit}만원")
    print(f"  면적: {result.area_sqm}㎡")
    print(f"  층수: {result.floor}/{result.total_floors}층")
    print(f"  준공: {result.built_year}년")
    print(f"  세대수: {result.households}세대")
    print("✅ Parse Agent 성공")
except Exception as e:
    print(f"❌ Parse Agent 실패: {e}")

# 3. Pipeline 테스트
print("\n[3] Pipeline 테스트...")
try:
    orchestrator = PipelineOrchestrator()
    
    user_input = UserInput(
        max_deposit=50000,
        min_area_sqm=80,
        min_households=1000,
        must_conditions=["max_deposit"],
    )
    
    report = orchestrator.run_single(
        "래미안목동 전세 4억5000 84㎡ 2020년 준공 1500세대",
        user_input
    )
    
    print(f"  총 매물: {report.total_count}")
    print(f"  통과: {report.passed_count}")
    print(f"  요약: {report.summary}")
    print("✅ Pipeline 성공")
except Exception as e:
    print(f"❌ Pipeline 실패: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("테스트 완료!")
print("=" * 50)
