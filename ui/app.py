"""
PropLens Streamlit UI - 안전 모드
"""

import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="PropLens - 부동산 매물 자동 분석",
    page_icon="🏠",
    layout="wide",
)

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "error_message" not in st.session_state:
    st.session_state.error_message = None


MAJOR_STATIONS = [
    "여의도역", "강남역", "삼성역", "선릉역", "역삼역",
    "판교역", "정자역", "시청역", "광화문역", "종각역",
    "홍대입구역", "합정역", "영등포구청역", "당산역",
    "신도림역", "가산디지털단지역", "구로디지털단지역",
    "서울역", "용산역", "잠실역", "건대입구역",
]


def show_cache_status():
    """캐시 상태 표시"""
    try:
        import sys
        sys.path.insert(0, ".")
        from app.data_sources.cache_manager import get_cache_manager
        
        cache = get_cache_manager()
        stats = cache.get_stats()
        
        st.sidebar.markdown("---")
        st.sidebar.caption("📦 캐시 상태")
        st.sidebar.caption(f"저장: {stats['count']}개 ({stats['size_kb']}KB)")
        
        if st.sidebar.button("🗑️ 캐시 삭제", use_container_width=True):
            cache.clear()
            st.sidebar.success("캐시 삭제됨")
            st.rerun()
    except:
        pass


def main():
    st.title("🏠 PropLens")
    st.subheader("AI 기반 부동산 매물 자동 분석 시스템")
    
    st.markdown("""
    **자동화된 매물 검색 및 분석**
    - 네이버 부동산에서 조건에 맞는 매물 자동 수집
    - 단지 정보 (세대수, 준공연도) 자동 조회
    - 전세가율 분석 (깡통전세 위험도)
    - 리스크 분석 및 중개사 질문 자동 생성
    """)
    
    # 에러 메시지 표시
    if st.session_state.error_message:
        st.error(st.session_state.error_message)
        if st.button("확인"):
            st.session_state.error_message = None
            st.rerun()
    
    with st.sidebar:
        st.header("🔍 검색 조건")
        
        transaction_type = st.selectbox(
            "거래 유형",
            ["전세", "월세", "매매"],
            index=0
        )
        
        st.subheader("💰 예산")
        max_deposit = st.number_input(
            "최대 보증금 (만원)",
            min_value=0,
            max_value=500000,
            value=45000,
            step=1000
        )
        
        if transaction_type == "월세":
            max_monthly = st.number_input(
                "최대 월세 (만원)",
                min_value=0,
                max_value=500,
                value=100,
                step=10
            )
        else:
            max_monthly = 0
        
        st.subheader("📍 지역")
        available_regions = [
            "강서구", "양천구", "영등포구", "마포구", "구로구",
            "강남구", "서초구", "송파구", "강동구", "동작구",
            "관악구", "금천구", "용산구", "중구", "종로구",
            "성동구", "광진구", "동대문구", "성북구", "노원구",
            "은평구", "서대문구", "강북구", "도봉구", "중랑구",
        ]
        selected_regions = st.multiselect(
            "검색할 지역 (구 단위)",
            available_regions,
            default=["양천구"]
        )
        
        # 지역 개수 경고
        if len(selected_regions) > 3:
            st.warning("⚠️ 3개 이상 지역 선택 시 시간이 오래 걸립니다")
        
        st.subheader("🚇 출퇴근")
        use_commute = st.checkbox("출퇴근 시간 계산", value=False)
        
        commute_destination = None
        max_commute_minutes = None
        
        if use_commute:
            commute_destination = st.selectbox(
                "출퇴근 목적지",
                [""] + MAJOR_STATIONS,
                index=0
            )
            if commute_destination:
                max_commute_minutes = st.number_input(
                    "최대 출퇴근 시간 (분)",
                    min_value=10,
                    max_value=120,
                    value=40,
                    step=5
                )
            st.caption("⚠️ ODsay API 키 필요")
        
        st.subheader("📐 면적")
        min_area = st.number_input(
            "최소 전용면적 (㎡)",
            min_value=0.0,
            max_value=300.0,
            value=59.0,
            step=1.0
        )
        
        st.subheader("🏢 단지 조건")
        min_households = st.number_input(
            "최소 세대수",
            min_value=0,
            max_value=10000,
            value=300,
            step=100
        )
        
        st.subheader("⭐ 필수 조건")
        must_deposit = st.checkbox("예산 필수", value=True)
        must_area = st.checkbox("면적 필수", value=True)
        must_households = st.checkbox("세대수 필수", value=False)
        
        must_conditions = []
        if must_deposit:
            must_conditions.append("max_deposit")
        if must_area:
            must_conditions.append("min_area_sqm")
        if must_households:
            must_conditions.append("min_households")
        
        st.subheader("⚙️ 옵션")
        max_items = st.slider(
            "지역당 최대 수집",
            min_value=10,
            max_value=50,
            value=30,
            step=10
        )
        
        # 캐시 상태
        show_cache_status()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.header("🚀 검색 실행")
        
        if not selected_regions:
            st.warning("최소 1개 지역을 선택하세요.")
        
        st.markdown("**현재 조건:**")
        st.write(f"- 거래: {transaction_type}")
        st.write(f"- 예산: {max_deposit:,}만원 이하")
        st.write(f"- 지역: {', '.join(selected_regions)}")
        st.write(f"- 면적: {min_area}㎡ 이상")
        st.write(f"- 세대수: {min_households:,}세대 이상")
        if commute_destination:
            st.write(f"- 출퇴근: {commute_destination} {max_commute_minutes}분 이내")
        
        st.markdown("---")
        st.caption("💡 동일 조건은 24시간 캐시됩니다")
        
        if st.button(
            "🔎 검색 시작",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.is_running or not selected_regions
        ):
            st.session_state.is_running = True
            st.session_state.error_message = None
            
            with st.spinner("매물 검색 중... (캐시 없으면 1-2분 소요)"):
                result, error = run_analysis(
                    transaction_type=transaction_type,
                    max_deposit=max_deposit,
                    max_monthly=max_monthly,
                    regions=selected_regions,
                    min_area=min_area,
                    min_households=min_households,
                    commute_destination=commute_destination if commute_destination else None,
                    max_commute_minutes=max_commute_minutes,
                    must_conditions=must_conditions,
                    max_items=max_items,
                )
                
                if error:
                    st.session_state.error_message = error
                else:
                    st.session_state.analysis_result = result
            
            st.session_state.is_running = False
            st.rerun()
    
    with col2:
        st.header("📊 분석 결과")
        
        if st.session_state.analysis_result:
            display_result(st.session_state.analysis_result)
        else:
            st.info("조건을 설정하고 '검색 시작' 버튼을 클릭하세요.")


def run_analysis(
    transaction_type: str,
    max_deposit: int,
    max_monthly: int,
    regions: list[str],
    min_area: float,
    min_households: int,
    commute_destination: str,
    max_commute_minutes: int,
    must_conditions: list,
    max_items: int,
) -> tuple[dict, str]:
    """분석 실행 - (결과, 에러메시지) 반환"""
    try:
        import sys
        sys.path.insert(0, ".")
        
        from app.schemas.user_input import UserInput
        from app.pipeline import PipelineOrchestrator
        from app.data_sources.naver_land import BlockedError
        
        user_input = UserInput(
            transaction_type=transaction_type,
            max_deposit=max_deposit,
            max_monthly_rent=max_monthly if max_monthly > 0 else None,
            regions=regions,
            min_area_sqm=min_area,
            min_households=min_households,
            commute_destination=commute_destination,
            max_commute_minutes=max_commute_minutes,
            must_conditions=must_conditions,
        )
        
        orchestrator = PipelineOrchestrator(max_items_per_region=max_items)
        report = orchestrator.run(user_input=user_input)
        
        return report.model_dump(), None
        
    except BlockedError as e:
        return None, f"🚫 API 차단됨: {str(e)}\n\n30분 후 다시 시도하세요."
    except Exception as e:
        import traceback
        return None, f"오류 발생: {e}\n\n{traceback.format_exc()}"


def display_result(result: dict):
    """결과 표시"""
    if not result:
        return
    
    st.success(result.get("summary", ""))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 매물", result.get("total_count", 0))
    with col2:
        st.metric("조건 충족", result.get("passed_count", 0))
    with col3:
        filtered = result.get("total_count", 0) - result.get("passed_count", 0)
        st.metric("탈락", filtered)
    
    insights = result.get("insights", [])
    if insights:
        st.subheader("💡 인사이트")
        for insight in insights:
            st.info(insight)
    
    recommendations = result.get("top_recommendations", [])
    if recommendations:
        st.subheader(f"✅ 추천 매물 ({len(recommendations)}개)")
        
        for i, rec in enumerate(recommendations[:10]):
            listing = rec.get("listing", {})
            
            title = listing.get("title") or listing.get("complex_name") or "매물"
            deposit = listing.get("deposit", 0)
            area = listing.get("area_pyeong", 0)
            households = listing.get("households")
            
            risk_result = rec.get("risk_result", {})
            risk_score = risk_result.get("risk_score", 0) if risk_result else 0
            risk_emoji = "🟢" if risk_score < 20 else "🟡" if risk_score < 50 else "🔴"
            
            households_str = f"{households}세대" if households else "세대수 정보없음"
            
            with st.expander(
                f"#{i+1} {title} | {deposit:,}만원 | {area}평 | {households_str} | {risk_emoji}"
            ):
                display_listing_detail(rec)
    
    filtered_out = result.get("filtered_out", [])
    if filtered_out:
        with st.expander(f"❌ 탈락 매물 ({len(filtered_out)}개)"):
            for rec in filtered_out[:5]:
                listing = rec.get("listing", {})
                filter_result = rec.get("filter_result", {})
                reasons = filter_result.get("failure_reasons", {}) if filter_result else {}
                
                title = listing.get("title") or listing.get("complex_name") or "매물"
                st.write(f"**{title}**")
                if reasons:
                    for field, reason in reasons.items():
                        st.caption(f"  - {reason}")


def display_listing_detail(rec: dict):
    """매물 상세 표시"""
    listing = rec.get("listing", {})
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**보증금:** {listing.get('deposit', 0):,}만원")
        st.write(f"**면적:** {listing.get('area_sqm', 0)}㎡ ({listing.get('area_pyeong', 0)}평)")
        st.write(f"**층수:** {listing.get('floor', '-')}/{listing.get('total_floors', '-')}층")
        st.write(f"**향:** {listing.get('direction', '-')}")
    with col2:
        st.write(f"**단지:** {listing.get('complex_name', '-')}")
        st.write(f"**세대수:** {listing.get('households') or '정보없음'}")
        st.write(f"**동수:** {listing.get('buildings') or '-'}동")
        st.write(f"**준공:** {listing.get('built_year') or '-'}년")
    
    url = listing.get("url")
    if url:
        st.markdown(f"[🔗 네이버 부동산에서 보기]({url})")
    
    description = listing.get("description", "")
    if description:
        st.write("---")
        st.write("**📝 분석 정보**")
        
        lines = description.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "[전세가율]" in line:
                if "위험" in line or "🔴" in line:
                    st.error(line)
                elif "주의" in line or "🟠" in line:
                    st.warning(line)
                else:
                    st.info(line)
            elif line.startswith("["):
                st.write(line)
            else:
                st.write(line)
    
    score_result = rec.get("score_result", {})
    if score_result:
        st.write("---")
        st.write("**📊 점수**")
        breakdown = score_result.get("breakdown", [])
        for item in breakdown:
            score = item.get("score", 0)
            max_score = item.get("max_score", 0)
            pct = score / max_score if max_score > 0 else 0
            st.progress(pct, text=f"{item.get('category', '')}: {score:.1f}/{max_score}")
    
    risk_result = rec.get("risk_result", {})
    if risk_result:
        risks = risk_result.get("risks", [])
        if risks:
            st.write("---")
            st.write(f"**⚠️ 리스크** ({risk_result.get('risk_score', 0)}/100)")
            
            for risk in risks[:5]:
                level = risk.get("level", "")
                emoji = "🔴" if level == "높음" else "🟡" if level == "보통" else "🔵"
                st.write(f"{emoji} **{risk.get('title', '')}**")
                st.caption(f"   → {risk.get('check_action', '')}")
    
    question_result = rec.get("question_result", {})
    if question_result:
        questions = question_result.get("questions", [])
        if questions:
            st.write("---")
            st.write("**❓ 중개사 질문**")
            for i, q in enumerate(questions[:5], 1):
                st.write(f"{i}. {q}")


if __name__ == "__main__":
    main()
