"""
PropLens Streamlit UI
- 자동 검색: 조건에 맞는 매물 자동 수집 및 분석
- 직접 평가: 지역 → 단지 → 매물 선택하여 평가
"""

import streamlit as st
import re
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="PropLens - 부동산 매물 자동 분석",
    page_icon="🏠",
    layout="wide",
)

# Session State 초기화
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "single_result" not in st.session_state:
    st.session_state.single_result = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "error_message" not in st.session_state:
    st.session_state.error_message = None
if "display_count" not in st.session_state:
    st.session_state.display_count = 10
if "filtered_display_count" not in st.session_state:
    st.session_state.filtered_display_count = 10
# 직접 평가용 상태
if "complex_list" not in st.session_state:
    st.session_state.complex_list = []
if "article_list" not in st.session_state:
    st.session_state.article_list = []
if "selected_complex" not in st.session_state:
    st.session_state.selected_complex = None


def get_station_list():
    """역 목록 가져오기"""
    try:
        import sys
        sys.path.insert(0, ".")
        from app.data_sources import STATION_COORDS
        return list(STATION_COORDS.keys())
    except ImportError:
        return [
            "여의도역", "강남역", "삼성역", "선릉역", "역삼역",
            "판교역", "정자역", "시청역", "광화문역", "종각역",
        ]


def show_cache_status():
    """캐시 상태 표시 및 관리"""
    try:
        import sys
        sys.path.insert(0, ".")
        from app.data_sources import get_cache_manager, get_name_by_code

        cache = get_cache_manager()
        stats = cache.get_stats()
        st.sidebar.markdown("---")
        st.sidebar.subheader("📦 캐시 관리")
        st.sidebar.caption(f"💾 {stats['count']}개 ({stats['size_kb']}KB)")

        if stats['count'] > 0:
            with st.sidebar.expander("📊 상세 보기"):
                detailed = cache.get_detailed_stats()
                for item in detailed:
                    region_code = item['region']
                    region_name = get_name_by_code(region_code)
                    status_emoji = "🔴" if item['expired'] else "🟢"
                    st.caption(f"{status_emoji} **{region_name}** | {item['items']}건 | {item['expires_in']} 남음")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("🗑️ 전체 삭제", use_container_width=True):
                count = cache.clear()
                st.sidebar.success(f"{count}개 삭제됨")
                st.rerun()
        with col2:
            if st.button("⏰ 만료만", use_container_width=True):
                count = cache.clear_expired()
                if count > 0:
                    st.sidebar.success(f"{count}개 삭제됨")
                else:
                    st.sidebar.info("만료 캐시 없음")
                st.rerun()
        st.sidebar.caption("💡 동일 조건은 24시간 캐시됩니다")
    except Exception as e:
        st.sidebar.warning(f"캐시 오류: {e}")


def main():
    st.title("🏠 PropLens")
    st.subheader("AI 기반 부동산 매물 자동 분석 시스템")

    if st.session_state.error_message:
        st.error(st.session_state.error_message)
        if st.button("확인"):
            st.session_state.error_message = None
            st.rerun()

    # 탭 선택
    tab1, tab2 = st.tabs(["🔍 자동 검색", "📝 직접 평가"])

    with tab1:
        render_auto_search_tab()

    with tab2:
        render_single_evaluation_tab()


def render_auto_search_tab():
    """자동 검색 탭"""
    st.markdown("""
    **조건에 맞는 매물 자동 수집**
    - 네이버 부동산에서 조건에 맞는 매물 자동 수집
    - 전세가율 분석 및 리스크 체크
    """)

    with st.sidebar:
        st.header("🔍 검색 조건")
        transaction_type = st.selectbox("거래 유형", ["전세", "월세", "매매"], index=0, key="auto_tx_type")

        st.subheader("💰 예산")
        max_deposit = st.number_input("최대 보증금 (만원)", min_value=0, max_value=500000, value=45000, step=1000, key="auto_deposit")
        if transaction_type == "월세":
            max_monthly = st.number_input("최대 월세 (만원)", min_value=0, max_value=500, value=100, step=10, key="auto_monthly")
        else:
            max_monthly = 0

        st.subheader("📍 지역")
        st.caption("🔵 서울")
        seoul_regions = [
            "강서구", "양천구", "영등포구", "마포구", "구로구",
            "강남구", "서초구", "송파구", "강동구", "동작구",
            "관악구", "금천구", "용산구", "중구", "종로구",
            "성동구", "광진구", "동대문구", "성북구", "도봉구",
            "은평구", "서대문구", "강북구", "노원구", "중랑구",
        ]
        selected_seoul = st.multiselect("서울 (구 단위)", seoul_regions, default=[], key="auto_seoul")

        st.caption("🟢 경기도")
        gyeonggi_regions = [
            "광명", "부천", "안산 단원구", "안산 상록구",
            "고양 덕양구", "안양 동안구", "안양 만안구",
            "성남 수정구", "성남 중원구", "성남 분당구",
            "과천", "군포", "의왕", "하남", "김포"
        ]
        selected_gyeonggi = st.multiselect("경기도", gyeonggi_regions, default=[], key="auto_gyeonggi")
        selected_regions = selected_seoul + selected_gyeonggi

        if len(selected_regions) > 3:
            st.warning("⚠️ 3개 이상 지역 선택 시 시간이 오래 걸립니다")

        st.subheader("🚇 출퇴근")
        use_commute = st.checkbox("출퇴근 시간 계산", value=False, key="auto_commute")
        commute_destination = None
        max_commute_minutes = None
        if use_commute:
            station_list = get_station_list()
            commute_destination = st.selectbox("출퇴근 목적지", [""] + station_list, index=0, key="auto_station")
            if commute_destination:
                max_commute_minutes = st.number_input("최대 출퇴근 시간 (분)", min_value=10, max_value=120, value=40, step=5, key="auto_commute_min")
            st.caption("⚠️ ODsay API 키 필요")

        st.subheader("🏠 주거 유형")
        available_property_types = ["아파트", "오피스텔", "빌라"]
        selected_property_types = st.multiselect("검색할 주거 유형", available_property_types, default=["아파트"], key="auto_prop_types")
        if not selected_property_types:
            st.warning("최소 1개 주거 유형을 선택하세요")

        st.subheader("📐 면적")
        min_area = st.number_input("최소 전용면적 (㎡)", min_value=0.0, max_value=300.0, value=59.0, step=1.0, key="auto_area")

        st.subheader("🏢 단지 조건")
        min_households = st.number_input("최소 세대수", min_value=0, max_value=10000, value=300, step=100, key="auto_households")

        st.subheader("✅ 필수 조건")
        must_deposit = st.checkbox("예산 필수", value=True, key="auto_must_deposit")
        must_area = st.checkbox("면적 필수", value=True, key="auto_must_area")
        must_households = st.checkbox("세대수 필수", value=False, key="auto_must_households")
        must_conditions = []
        if must_deposit:
            must_conditions.append("max_deposit")
        if must_area:
            must_conditions.append("min_area_sqm")
        if must_households:
            must_conditions.append("min_households")

        st.subheader("⚙️ 옵션")
        max_items = st.slider("지역당 최대 수집", min_value=10, max_value=50, value=30, step=10, key="auto_max_items")

        show_cache_status()

    col1, col2 = st.columns([1, 2])

    with col1:
        st.header("▶️ 검색 실행")
        if not selected_regions:
            st.warning("최소 1개 지역을 선택하세요!")

        st.markdown("**현재 조건:**")
        st.write(f"- 거래: {transaction_type}")
        st.write(f"- 예산: {max_deposit:,}만원 이하")
        st.write(f"- 지역: {', '.join(selected_regions) if selected_regions else '미선택'}")
        st.write(f"- 주거유형: {', '.join(selected_property_types)}")
        st.write(f"- 면적: {min_area}㎡ 이상")
        st.write(f"- 세대수: {min_households:,}세대 이상")
        if commute_destination:
            st.write(f"- 출퇴근: {commute_destination} {max_commute_minutes}분 이내")

        st.markdown("---")
        st.caption("💡 동일 조건은 24시간 캐시됩니다")

        if st.button("🔎 검색 시작", type="primary", use_container_width=True,
                     disabled=st.session_state.is_running or not selected_regions or not selected_property_types,
                     key="btn_auto_search"):
            st.session_state.is_running = True
            st.session_state.error_message = None
            st.session_state.display_count = 10
            st.session_state.filtered_display_count = 10

            with st.spinner("매물 검색 중... (캐시 없으면 1-2분 소요)"):
                result, error = run_auto_analysis(
                    transaction_type, max_deposit, max_monthly,
                    selected_regions, selected_property_types,
                    min_area, min_households,
                    commute_destination if commute_destination else None,
                    max_commute_minutes, must_conditions, max_items
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
            display_auto_result(st.session_state.analysis_result)
        else:
            st.info("조건을 설정하고 '검색 시작' 버튼을 클릭하세요")


def render_single_evaluation_tab():
    """직접 평가 탭 - 목록 선택 / 직접 입력 지원"""
    st.markdown("""
    **특정 매물 직접 평가** - 목록에서 선택하거나 단지명 직접 입력
    """)

    col1, col2 = st.columns([1, 2])

    with col1:
        # 입력 방식 선택
        input_mode = st.radio(
            "입력 방식",
            ["📝 목록에서 선택", "⌨️ 단지명 직접 입력"],
            horizontal=True,
            key="single_input_mode"
        )

        st.markdown("---")

        # 공통: 지역 + 거래유형 선택
        st.header("Step 1️⃣ 기본 정보")

        seoul_regions = [
            "강서구", "양천구", "영등포구", "마포구", "구로구",
            "강남구", "서초구", "송파구", "강동구", "동작구",
            "관악구", "금천구", "용산구", "중구", "종로구",
            "성동구", "광진구", "동대문구", "성북구", "도봉구",
            "은평구", "서대문구", "강북구", "노원구", "중랑구",
        ]

        region_gu = st.selectbox(
            "지역 (구) *",
            ["선택하세요"] + seoul_regions,
            index=0,
            key="single_region"
        )

        col_a, col_b = st.columns(2)
        with col_a:
            transaction_type = st.selectbox(
                "거래 유형",
                ["전세", "월세", "매매"],
                index=0,
                key="single_tx_type"
            )
        with col_b:
            property_type = st.selectbox(
                "주거 유형",
                ["아파트", "오피스텔", "빌라"],
                index=0,
                key="single_prop_type"
            )

        # === 목록에서 선택 모드 ===
        if input_mode == "📝 목록에서 선택":
            if region_gu != "선택하세요":
                if st.button("🔍 단지 목록 조회", use_container_width=True, key="btn_load_complex"):
                    with st.spinner("단지 목록 조회 중..."):
                        complexes, error = load_complex_list(region_gu, transaction_type, property_type)
                        if error:
                            st.error(error)
                        else:
                            st.session_state.complex_list = complexes
                            st.session_state.article_list = []
                            st.session_state.single_result = None
                            st.rerun()

            if st.session_state.complex_list:
                st.markdown("---")
                st.header("Step 2️⃣ 단지 선택")

                complex_options = []
                for c in st.session_state.complex_list:
                    hh = c.get("households") or "?"
                    year = c.get("built_year") or "?"
                    complex_options.append(f"{c['name']} ({hh}세대, {year}년)")

                selected_idx = st.selectbox(
                    f"단지 선택 ({len(complex_options)}개)",
                    range(len(complex_options)),
                    format_func=lambda x: complex_options[x],
                    key="single_complex_select"
                )

                selected_complex = st.session_state.complex_list[selected_idx]

                if st.button("🏠 매물 목록 조회", use_container_width=True, key="btn_load_articles"):
                    with st.spinner(f"'{selected_complex['name']}' 매물 조회 중..."):
                        articles, error = load_complex_articles(
                            region_gu,
                            selected_complex['name'],
                            transaction_type,
                            property_type
                        )
                        if error:
                            st.error(error)
                        elif not articles:
                            st.warning("현재 등록된 매물이 없습니다.")
                        else:
                            st.session_state.article_list = articles
                            st.session_state.selected_complex = selected_complex
                            st.session_state.single_result = None
                            st.rerun()

            if st.session_state.article_list:
                st.markdown("---")
                st.header("Step 3️⃣ 매물 선택")

                complex_info = st.session_state.selected_complex
                st.info(f"📍 **{complex_info['name']}** | {complex_info.get('households') or '?'}세대 | {complex_info.get('built_year') or '?'}년")

                # 매물 필터링 옵션
                with st.expander("🔍 매물 필터링", expanded=False):
                    st.caption("조건을 설정하면 매물 목록이 필터링됩니다")
                    
                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        filter_max_deposit = st.number_input(
                            "최대 보증금 (만원)", 
                            min_value=0, max_value=500000, value=0, step=1000,
                            key="filter_max_deposit",
                            help="0이면 필터 안함"
                        )
                    with filter_col2:
                        filter_min_households = st.number_input(
                            "최소 세대수", 
                            min_value=0, max_value=10000, value=0, step=100,
                            key="filter_min_households",
                            help="0이면 필터 안함"
                        )
                    
                    filter_col3, filter_col4 = st.columns(2)
                    with filter_col3:
                        filter_min_area = st.number_input(
                            "최소 면적 (㎡)", 
                            min_value=0.0, max_value=300.0, value=0.0, step=1.0,
                            key="filter_min_area",
                            help="0이면 필터 안함"
                        )
                    with filter_col4:
                        filter_max_area = st.number_input(
                            "최대 면적 (㎡)", 
                            min_value=0.0, max_value=300.0, value=0.0, step=1.0,
                            key="filter_max_area",
                            help="0이면 필터 안함"
                        )
                
                # 필터링 적용
                filtered_articles = []
                for a in st.session_state.article_list:
                    deposit = a.get("deposit", 0) or 0
                    area = a.get("area_sqm", 0) or 0
                    households = a.get("households", 0) or 0
                    
                    # 보증금 필터
                    if filter_max_deposit > 0 and deposit > filter_max_deposit:
                        continue
                    # 세대수 필터
                    if filter_min_households > 0 and households < filter_min_households:
                        continue
                    # 최소 면적 필터
                    if filter_min_area > 0 and area < filter_min_area:
                        continue
                    # 최대 면적 필터
                    if filter_max_area > 0 and area > filter_max_area:
                        continue
                    
                    filtered_articles.append(a)
                
                # 필터링 결과 표시
                total_count = len(st.session_state.article_list)
                filtered_count = len(filtered_articles)
                if filtered_count < total_count:
                    st.caption(f"📊 필터링: {total_count}개 → {filtered_count}개")
                
                if not filtered_articles:
                    st.warning("필터 조건에 맞는 매물이 없습니다.")
                else:
                    article_options = []
                    for a in filtered_articles:
                        deposit = a.get("deposit", 0)
                        area = a.get("area_pyeong", 0)
                        floor = a.get("floor") or "?"
                        article_options.append(f"{deposit:,}만원 | {area}평 | {floor}층")

                    selected_article_idx = st.selectbox(
                        f"매물 선택 ({len(article_options)}개)",
                        range(len(article_options)),
                        format_func=lambda x: article_options[x],
                        key="single_article_select"
                    )

                    selected_article = filtered_articles[selected_article_idx]

                    st.markdown("---")
                    st.subheader("⚖️ 내 평가 기준")

                    col_e, col_f = st.columns(2)
                    with col_e:
                        my_max_deposit = st.number_input("최대 예산 (만원)", min_value=0, max_value=500000, value=45000, step=1000, key="single_my_deposit")
                    with col_f:
                        my_min_households = st.number_input("최소 세대수", min_value=0, max_value=10000, value=300, step=100, key="single_my_households")

                    col_g, col_h = st.columns(2)
                    with col_g:
                        my_min_area = st.number_input("최소 면적 (㎡)", min_value=0.0, max_value=300.0, value=59.0, step=1.0, key="single_my_area")
                    with col_h:
                        my_max_area = st.number_input("최대 면적 (㎡)", min_value=0.0, max_value=300.0, value=150.0, step=1.0, key="single_my_max_area")

                    if st.button("📊 매물 평가", type="primary", use_container_width=True, key="btn_evaluate"):
                        with st.spinner("매물 평가 중..."):
                            result, error = run_single_evaluation_from_listing(
                                listing_data=selected_article,
                                complex_info=complex_info,
                                my_max_deposit=my_max_deposit,
                                my_min_area=my_min_area,
                                my_max_area=my_max_area,
                                my_min_households=my_min_households,
                            )
                            if error:
                                st.error(error)
                            else:
                                st.session_state.single_result = result
                                st.rerun()

        # === 직접 입력 모드 ===
        else:
            st.markdown("---")
            st.header("Step 2️⃣ 단지명 입력")

            complex_name = st.text_input(
                "단지명 *",
                placeholder="래미안목동아델리체",
                key="manual_complex_name"
            )
            st.caption("💡 네이버 부동산에서 매물 검색 후 단지명을 정확히 입력하세요")

            if region_gu != "선택하세요" and complex_name:
                if st.button("🔍 매물 검색", use_container_width=True, key="btn_search_manual"):
                    with st.spinner(f"'{complex_name}' 매물 검색 중..."):
                        articles, error = load_complex_articles(
                            region_gu,
                            complex_name,
                            transaction_type,
                            property_type
                        )
                        if error:
                            st.error(error)
                        elif not articles:
                            st.warning(f"'{complex_name}' 매물을 찾을 수 없습니다. 단지명을 확인해주세요.")
                        else:
                            st.session_state.article_list = articles
                            st.session_state.selected_complex = {
                                "name": complex_name,
                                "households": articles[0].get("households") if articles else None,
                                "built_year": articles[0].get("built_year") if articles else None,
                            }
                            st.session_state.single_result = None
                            st.rerun()

            if st.session_state.article_list and input_mode == "⌨️ 단지명 직접 입력":
                st.markdown("---")
                st.header("Step 3️⃣ 매물 선택")

                complex_info = st.session_state.selected_complex
                st.success(f"✅ '{complex_info['name']}' 매물 {len(st.session_state.article_list)}건 발견")

                # 매물 필터링 옵션
                with st.expander("🔍 매물 필터링", expanded=False):
                    st.caption("조건을 설정하면 매물 목록이 필터링됩니다")
                    
                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        filter_max_deposit_m = st.number_input(
                            "최대 보증금 (만원)", 
                            min_value=0, max_value=500000, value=0, step=1000,
                            key="filter_max_deposit_manual",
                            help="0이면 필터 안함"
                        )
                    with filter_col2:
                        filter_min_households_m = st.number_input(
                            "최소 세대수", 
                            min_value=0, max_value=10000, value=0, step=100,
                            key="filter_min_households_manual",
                            help="0이면 필터 안함"
                        )
                    
                    filter_col3, filter_col4 = st.columns(2)
                    with filter_col3:
                        filter_min_area_m = st.number_input(
                            "최소 면적 (㎡)", 
                            min_value=0.0, max_value=300.0, value=0.0, step=1.0,
                            key="filter_min_area_manual",
                            help="0이면 필터 안함"
                        )
                    with filter_col4:
                        filter_max_area_m = st.number_input(
                            "최대 면적 (㎡)", 
                            min_value=0.0, max_value=300.0, value=0.0, step=1.0,
                            key="filter_max_area_manual",
                            help="0이면 필터 안함"
                        )
                
                # 필터링 적용
                filtered_articles = []
                for a in st.session_state.article_list:
                    deposit = a.get("deposit", 0) or 0
                    area = a.get("area_sqm", 0) or 0
                    households = a.get("households", 0) or 0
                    
                    if filter_max_deposit_m > 0 and deposit > filter_max_deposit_m:
                        continue
                    if filter_min_households_m > 0 and households < filter_min_households_m:
                        continue
                    if filter_min_area_m > 0 and area < filter_min_area_m:
                        continue
                    if filter_max_area_m > 0 and area > filter_max_area_m:
                        continue
                    
                    filtered_articles.append(a)
                
                total_count = len(st.session_state.article_list)
                filtered_count = len(filtered_articles)
                if filtered_count < total_count:
                    st.caption(f"📊 필터링: {total_count}개 → {filtered_count}개")
                
                if not filtered_articles:
                    st.warning("필터 조건에 맞는 매물이 없습니다.")
                else:
                    article_options = []
                    for a in filtered_articles:
                        deposit = a.get("deposit", 0)
                        area = a.get("area_pyeong", 0)
                        floor = a.get("floor") or "?"
                        article_options.append(f"{deposit:,}만원 | {area}평 | {floor}층")

                    selected_article_idx = st.selectbox(
                        f"매물 선택 ({len(article_options)}개)",
                        range(len(article_options)),
                        format_func=lambda x: article_options[x],
                        key="manual_article_select"
                    )

                    selected_article = filtered_articles[selected_article_idx]

                    st.markdown("---")
                    st.subheader("⚖️ 내 평가 기준")

                    col_e, col_f = st.columns(2)
                    with col_e:
                        my_max_deposit = st.number_input("최대 예산 (만원)", min_value=0, max_value=500000, value=45000, step=1000, key="manual_my_deposit")
                    with col_f:
                        my_min_households = st.number_input("최소 세대수", min_value=0, max_value=10000, value=300, step=100, key="manual_my_households")

                    col_g, col_h = st.columns(2)
                    with col_g:
                        my_min_area = st.number_input("최소 면적 (㎡)", min_value=0.0, max_value=300.0, value=59.0, step=1.0, key="manual_my_area")
                    with col_h:
                        my_max_area = st.number_input("최대 면적 (㎡)", min_value=0.0, max_value=300.0, value=150.0, step=1.0, key="manual_my_max_area")

                    if st.button("📊 매물 평가", type="primary", use_container_width=True, key="btn_evaluate_manual"):
                        with st.spinner("매물 평가 중..."):
                            result, error = run_single_evaluation_from_listing(
                                listing_data=selected_article,
                                complex_info=complex_info,
                                my_max_deposit=my_max_deposit,
                                my_min_area=my_min_area,
                                my_max_area=my_max_area,
                                my_min_households=my_min_households,
                            )
                            if error:
                                st.error(error)
                            else:
                                st.session_state.single_result = result
                                st.rerun()

    with col2:
        st.header("📊 평가 결과")

        if st.session_state.single_result:
            display_single_result(st.session_state.single_result)
        elif st.session_state.article_list:
            st.info("매물을 선택하고 '매물 평가' 버튼을 클릭하세요")

            idx_key = "single_article_select" if input_mode == "📝 목록에서 선택" else "manual_article_select"
            if idx_key in st.session_state:
                idx = st.session_state[idx_key]
                if idx < len(st.session_state.article_list):
                    article = st.session_state.article_list[idx]
                    st.subheader("📋 선택된 매물 정보")

                    col_x, col_y = st.columns(2)
                    with col_x:
                        st.write(f"**보증금:** {article.get('deposit', 0):,}만원")
                        st.write(f"**면적:** {article.get('area_sqm', 0)}㎡ ({article.get('area_pyeong', 0)}평)")
                        st.write(f"**층수:** {article.get('floor') or '-'}층")
                    with col_y:
                        st.write(f"**단지:** {article.get('complex_name', '-')}")
                        st.write(f"**세대수:** {article.get('households') or '정보없음'}")
                        st.write(f"**준공:** {article.get('built_year') or '-'}년")

                    url = article.get("url")
                    if url:
                        st.markdown(f"[🔗 네이버 부동산에서 보기]({url})")

        elif input_mode == "📝 목록에서 선택":
            if st.session_state.complex_list:
                st.info("단지를 선택하고 '매물 목록 조회' 버튼을 클릭하세요")
            else:
                st.info("지역을 선택하고 '단지 목록 조회' 버튼을 클릭하세요")
        else:
            st.info("단지명을 입력하고 '매물 검색' 버튼을 클릭하세요")


def load_complex_list(region_gu: str, transaction_type: str, property_type: str):
    """지역 내 단지 목록 조회"""
    import sys
    if "." not in sys.path:
        sys.path.insert(0, ".")

    try:
        from app.data_sources.naver_land import NaverLandClient
        from app.data_sources.region_codes import RegionCodeManager
        from app.config import settings

        # 지역 코드 조회
        region_manager = RegionCodeManager()
        sigungu_code = region_manager.get_sigungu_code(region_gu)

        if not sigungu_code:
            return [], f"지역 코드를 찾을 수 없습니다: {region_gu}"

        # 거래 유형 코드
        trade_type = settings.TRADE_TYPE_CODES.get(transaction_type, "B1")
        prop_code = settings.PROPERTY_TYPE_CODES.get(property_type, "APT")

        with NaverLandClient() as client:
            complexes = client.get_region_complex_list(sigungu_code, trade_type, prop_code)

        return complexes, None

    except Exception as e:
        return [], f"단지 목록 조회 실패: {e}"


def load_complex_articles(region_gu: str, complex_name: str, transaction_type: str, property_type: str):
    """특정 단지의 매물 목록 조회"""
    import sys
    if "." not in sys.path:
        sys.path.insert(0, ".")

    try:
        from app.data_sources.naver_land import NaverLandClient
        from app.data_sources.region_codes import RegionCodeManager
        from app.config import settings

        region_manager = RegionCodeManager()
        sigungu_code = region_manager.get_sigungu_code(region_gu)

        if not sigungu_code:
            return [], f"지역 코드를 찾을 수 없습니다: {region_gu}"

        trade_type = settings.TRADE_TYPE_CODES.get(transaction_type, "B1")
        prop_code = settings.PROPERTY_TYPE_CODES.get(property_type, "APT")

        with NaverLandClient() as client:
            listings = client.get_complex_articles(sigungu_code, complex_name, trade_type, prop_code)

        # Listing 객체를 dict로 변환
        articles = [l.model_dump() for l in listings]
        return articles, None

    except Exception as e:
        return [], f"매물 목록 조회 실패: {e}"


def run_single_evaluation_from_listing(
    listing_data: dict,
    complex_info: dict,
    my_max_deposit: int,
    my_min_area: float,
    my_max_area: float,
    my_min_households: int,
):
    """선택된 매물 평가"""
    import sys
    import traceback

    if "." not in sys.path:
        sys.path.insert(0, ".")

    try:
        from app.schemas.listing import Listing
        from app.schemas.user_input import UserInput
        from app.agents import FilterAgent, FilterInput, ScoreAgent, ScoreInput, RiskAgent, QuestionAgent, QuestionInput
        from app.data_sources.molit_api import MolitRealPriceClient
        from app.data_sources.region_codes import RegionCodeManager

        # Listing 재구성 (complex_info 병합)
        listing = Listing(**listing_data)
        if listing.households is None:
            listing.households = complex_info.get("households")
        if listing.buildings is None:
            listing.buildings = complex_info.get("buildings")
        if listing.built_year is None:
            listing.built_year = complex_info.get("built_year")

        transaction_type = listing.transaction_type or "전세"
        property_type = listing.property_type or "아파트"
        region_gu = listing.region_gu or ""

        # UserInput
        user_input = UserInput(
            transaction_type=transaction_type,
            max_deposit=my_max_deposit,
            regions=[region_gu] if region_gu else [],
            property_types=[property_type],
            min_area_sqm=my_min_area,
            min_households=my_min_households,
            must_conditions=["max_deposit", "min_area_sqm"],
        )

        result = {
            "listing": listing.model_dump(),
            "filter_result": None,
            "score_result": None,
            "risk_result": None,
            "question_result": None,
            "price_analysis": None,
            "evaluation_criteria": {
                "max_deposit": my_max_deposit,
                "min_area": my_min_area,
                "max_area": my_max_area,
                "min_households": my_min_households,
            }
        }

        # 1. 실거래가 분석
        if transaction_type in ["전세", "매매"] and region_gu:
            region_manager = RegionCodeManager()
            sigungu_code = region_manager.get_sigungu_code(region_gu)

            if sigungu_code:
                complex_name = listing.complex_name or ""
                area_sqm = listing.area_sqm or 84.0
                deposit = listing.deposit or 0

                with MolitRealPriceClient() as client:
                    if transaction_type == "전세":
                        analysis = client.get_complex_price_analysis(
                            sigungu_code=sigungu_code,
                            complex_name=complex_name,
                            area_sqm=area_sqm,
                            current_deposit=deposit,
                            months=3,
                        )
                        if analysis:
                            result["price_analysis"] = analysis
                            notes = []
                            if analysis.get("rent_analysis"):
                                avg = analysis["rent_analysis"]["avg_deposit"]
                                notes.append(f"[전세 시세] 평균: {avg:,}만원")
                            if analysis.get("trade_analysis"):
                                avg = analysis["trade_analysis"]["avg_price"]
                                notes.append(f"[매매 시세] 평균: {avg:,}만원")
                            if analysis.get("jeonse_ratio_analysis"):
                                ratio = analysis["jeonse_ratio_analysis"]["jeonse_ratio"]
                                risk = analysis["jeonse_ratio_analysis"]["risk_level"]
                                notes.append(f"[전세가율] {ratio:.1f}% ({risk})")
                            if notes:
                                listing.description = (listing.description or "") + "\n\n" + "\n".join(notes)
                    else:
                        trade_info = client.get_complex_trade_avg(
                            sigungu_code=sigungu_code,
                            complex_name=complex_name,
                            area_sqm=area_sqm,
                            months=3,
                        )
                        if trade_info:
                            result["price_analysis"] = {"trade_analysis": trade_info}
                            avg = trade_info["avg_price"]
                            listing.description = (listing.description or "") + f"\n\n[매매 시세] 평균: {avg:,}만원"

        # 2. 필터링
        filter_agent = FilterAgent()
        filter_result = filter_agent.run(FilterInput(listing=listing, user_input=user_input))
        result["filter_result"] = filter_result.model_dump()

        # 3. 점수화
        score_agent = ScoreAgent()
        scored = score_agent.run(ScoreInput(listing=listing, user_input=user_input))
        sr = getattr(scored, "score_result", None)
        if sr is not None:
            result["score_result"] = sr.model_dump()
        else:
            result["score_result"] = scored.model_dump()

        # 4. 리스크
        risk_agent = RiskAgent()
        risk_result = risk_agent.run(listing)
        result["risk_result"] = risk_result.model_dump()

        # 5. 질문 생성
        question_agent = QuestionAgent()
        question_result = question_agent.run(QuestionInput(listing=listing, risk_result=risk_result))
        result["question_result"] = question_result.model_dump()

        result["listing"] = listing.model_dump()

        return result, None

    except Exception as e:
        return None, f"평가 오류: {e}\n\n{traceback.format_exc()}"


def display_single_result(result: dict):
    """단일 매물 평가 결과 표시"""
    listing = result.get("listing", {})
    filter_result = result.get("filter_result", {})
    criteria = result.get("evaluation_criteria", {})

    # 조건 충족 여부
    status = filter_result.get("status", "")
    if status == "PASS":
        st.success("✅ 조건 충족! 이 매물은 내 기준에 맞습니다.")
    elif status == "PARTIAL":
        st.warning("⚠️ 일부 조건 미충족")
    else:
        st.error("❌ 조건 미충족")

    # 기본 정보
    st.subheader("📋 매물 정보")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("단지명", listing.get("complex_name", "-"))
        st.metric("보증금", f"{listing.get('deposit', 0):,}만원")
    with col2:
        st.metric("면적", f"{listing.get('area_sqm', 0)}㎡ ({listing.get('area_pyeong', 0)}평)")
        st.metric("층수", f"{listing.get('floor') or '-'}층")
    with col3:
        st.metric("세대수", listing.get("households") or "정보없음")
        st.metric("준공", f"{listing.get('built_year') or '-'}년")

    # 내 기준과 비교
    st.subheader("⚖️ 내 기준과 비교")

    col1, col2 = st.columns(2)
    with col1:
        deposit = listing.get("deposit", 0)
        max_dep = criteria.get("max_deposit", 0)
        if deposit <= max_dep:
            st.success(f"✅ 예산: {deposit:,} ≤ {max_dep:,}만원")
        else:
            st.error(f"❌ 예산: {deposit:,} > {max_dep:,}만원")

    with col2:
        hh = listing.get("households") or 0
        min_hh = criteria.get("min_households", 0)
        if hh >= min_hh or hh == 0:
            if hh > 0:
                st.success(f"✅ 세대수: {hh} ≥ {min_hh}")
            else:
                st.info(f"ℹ️ 세대수: 정보없음")
        else:
            st.error(f"❌ 세대수: {hh} < {min_hh}")

    col3, col4 = st.columns(2)
    with col3:
        area = listing.get("area_sqm", 0)
        min_area = criteria.get("min_area", 0)
        if area >= min_area:
            st.success(f"✅ 최소면적: {area}㎡ ≥ {min_area}㎡")
        else:
            st.error(f"❌ 최소면적: {area}㎡ < {min_area}㎡")

    with col4:
        max_area = criteria.get("max_area", 300)
        if area <= max_area:
            st.success(f"✅ 최대면적: {area}㎡ ≤ {max_area}㎡")
        else:
            st.error(f"❌ 최대면적: {area}㎡ > {max_area}㎡")

    # 실거래가 분석
    price_analysis = result.get("price_analysis")
    if price_analysis:
        st.subheader("📈 실거래가 분석")

        rent_analysis = price_analysis.get("rent_analysis")
        trade_analysis = price_analysis.get("trade_analysis")
        jeonse_analysis = price_analysis.get("jeonse_ratio_analysis")

        col1, col2 = st.columns(2)

        with col1:
            if rent_analysis:
                st.write("**전세 시세 (최근 3개월)**")
                st.write(f"- 평균: {rent_analysis['avg_deposit']:,}만원")
                st.write(f"- 범위: {rent_analysis['min_deposit']:,} ~ {rent_analysis['max_deposit']:,}만원")
                st.write(f"- 거래: {rent_analysis['count']}건")

        with col2:
            if trade_analysis:
                st.write("**매매 시세 (최근 3개월)**")
                st.write(f"- 평균: {trade_analysis['avg_price']:,}만원")
                st.write(f"- 범위: {trade_analysis['min_price']:,} ~ {trade_analysis['max_price']:,}만원")
                st.write(f"- 거래: {trade_analysis['count']}건")

        if jeonse_analysis:
            ratio = jeonse_analysis["jeonse_ratio"]
            risk = jeonse_analysis["risk_level"]

            st.write("---")
            if risk == "위험":
                st.error(f"⚠️ **전세가율: {ratio:.1f}% ({risk})** - 깡통전세 위험!")
            elif risk == "주의":
                st.warning(f"⚠️ **전세가율: {ratio:.1f}% ({risk})** - 주의 필요")
            elif risk == "보통":
                st.info(f"ℹ️ **전세가율: {ratio:.1f}% ({risk})**")
            else:
                st.success(f"✅ **전세가율: {ratio:.1f}% ({risk})**")

    # 점수
    score_result = result.get("score_result")
    if score_result:
        st.subheader("📊 종합 점수")
        total = score_result.get("total_score", 0)
        st.metric("총점", f"{total:.1f}/100")

        breakdown = score_result.get("breakdown", [])
        for item in breakdown:
            score = item.get("score", 0)
            max_score = item.get("max_score", 0)
            pct = score / max_score if max_score > 0 else 0
            st.progress(pct, text=f"{item.get('category', '')}: {score:.1f}/{max_score}")

    # 리스크
    risk_result = result.get("risk_result")
    if risk_result:
        risks = risk_result.get("risks", [])
        if risks:
            st.subheader(f"⚠️ 리스크 ({risk_result.get('risk_score', 0)}/100)")
            for risk in risks:
                level = risk.get("level", "")
                emoji = "🔴" if level == "높음" else "🟡" if level == "보통" else "🟢"
                st.write(f"{emoji} **{risk.get('title', '')}**")
                st.caption(f"   → {risk.get('check_action', '')}")
        else:
            st.success("✅ 특별한 리스크가 발견되지 않았습니다.")

    # 질문
    question_result = result.get("question_result")
    if question_result:
        questions = question_result.get("questions", [])
        if questions:
            st.subheader("❓ 중개사에게 물어볼 질문")
            for i, q in enumerate(questions, 1):
                st.write(f"{i}. {q}")

    # URL 링크
    url = listing.get("url")
    if url:
        st.markdown("---")
        st.markdown(f"[🔗 네이버 부동산에서 보기]({url})")


def run_auto_analysis(transaction_type, max_deposit, max_monthly, regions, property_types,
                      min_area, min_households, commute_destination, max_commute_minutes,
                      must_conditions, max_items):
    """자동 분석 실행"""
    import sys
    import traceback

    if "." not in sys.path:
        sys.path.insert(0, ".")

    try:
        from app.data_sources.naver_land import BlockedError
    except ImportError:
        BlockedError = Exception

    try:
        from app.schemas.user_input import UserInput
        from app.pipeline import PipelineOrchestrator

        user_input = UserInput(
            transaction_type=transaction_type,
            max_deposit=max_deposit,
            max_monthly_rent=max_monthly if max_monthly > 0 else None,
            regions=regions,
            property_types=property_types,
            min_area_sqm=min_area,
            min_households=min_households,
            commute_destination=commute_destination,
            max_commute_minutes=max_commute_minutes,
            must_conditions=must_conditions
        )

        orchestrator = PipelineOrchestrator(max_items_per_region=max_items)
        report = orchestrator.run(user_input=user_input)
        return report.model_dump(), None

    except BlockedError as e:
        return None, f"🚫 API 차단됨: {str(e)}\n\n30분 후 다시 시도하세요."
    except ImportError as e:
        return None, f"모듈 import 오류: {e}\n\n{traceback.format_exc()}"
    except Exception as e:
        return None, f"오류 발생: {e}\n\n{traceback.format_exc()}"


def display_auto_result(result):
    """자동 검색 결과 표시"""
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
        total_count = len(recommendations)
        display_count = st.session_state.display_count
        st.subheader(f"⭐ 추천 매물 ({min(display_count, total_count)}/{total_count}개 표시)")

        for i, rec in enumerate(recommendations[:display_count]):
            listing = rec.get("listing", {})
            title = listing.get("title") or listing.get("complex_name") or "매물"
            deposit = listing.get("deposit", 0)
            area = listing.get("area_pyeong", 0)
            households = listing.get("households")
            risk_result = rec.get("risk_result", {})
            risk_score = risk_result.get("risk_score", 0) if risk_result else 0
            risk_emoji = "🟢" if risk_score < 20 else "🟡" if risk_score < 50 else "🔴"
            households_str = f"{households}세대" if households else "세대수 정보없음"
            property_type = listing.get("property_type", "")

            with st.expander(f"#{i+1} [{property_type}] {title} | {deposit:,}만원 | {area}평 | {households_str} | {risk_emoji}"):
                display_listing_detail(rec)

        if display_count < total_count:
            remaining = total_count - display_count
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button(f"📋 더 보기 (+10개, 남은 매물: {remaining}개)", use_container_width=True, key="load_more"):
                    st.session_state.display_count += 10
                    st.rerun()
        else:
            st.info(f"✅ 전체 {total_count}개 매물을 모두 표시했습니다.")

    filtered_out = result.get("filtered_out", [])
    if filtered_out:
        total_filtered = len(filtered_out)
        filtered_display = st.session_state.filtered_display_count

        st.subheader(f"❌ 탈락 매물 ({min(filtered_display, total_filtered)}/{total_filtered}개 표시)")

        for i, rec in enumerate(filtered_out[:filtered_display]):
            listing = rec.get("listing", {})
            filter_result = rec.get("filter_result", {})
            reasons = filter_result.get("failure_reasons", {}) if filter_result else {}
            title = listing.get("title") or listing.get("complex_name") or "매물"
            deposit = listing.get("deposit", 0)
            area = listing.get("area_pyeong", 0)
            households = listing.get("households")
            households_str = f"{households}세대" if households else "세대수 정보없음"
            property_type = listing.get("property_type", "")

            reason_summary = ", ".join(reasons.values()) if reasons else "조건 미달"
            if len(reason_summary) > 50:
                reason_summary = reason_summary[:50] + "..."

            with st.expander(f"#{i+1} [{property_type}] {title} | {deposit:,}만원 | {area}평 | {households_str} | ❌ {reason_summary}"):
                st.write("**🚫 탈락 사유**")
                if reasons:
                    for field, reason in reasons.items():
                        st.error(f"• {reason}")
                else:
                    st.error("• 조건 미달")

                st.write("---")
                display_listing_detail(rec)

        if filtered_display < total_filtered:
            remaining = total_filtered - filtered_display
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button(f"📋 탈락 매물 더 보기 (+10개, 남은: {remaining}개)", use_container_width=True, key="load_more_filtered"):
                    st.session_state.filtered_display_count += 10
                    st.rerun()


def display_listing_detail(rec):
    """매물 상세 정보 표시"""
    listing = rec.get("listing", {})

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**보증금:** {listing.get('deposit', 0):,}만원")
        st.write(f"**면적:** {listing.get('area_sqm', 0)}㎡ ({listing.get('area_pyeong', 0)}평)")
        st.write(f"**층수:** {listing.get('floor', '-')}/{listing.get('total_floors', '-')}층")
        st.write(f"**향:** {listing.get('direction', '-')}")
    with col2:
        st.write(f"**단지:** {listing.get('complex_name', '-')}")
        st.write(f"**주거유형:** {listing.get('property_type', '-')}")
        st.write(f"**세대수:** {listing.get('households') or '정보없음'}")
        st.write(f"**동수:** {listing.get('buildings') or '-'}동")
        st.write(f"**준공:** {listing.get('built_year') or '-'}년")

    url = listing.get("url")
    if url:
        st.markdown(f"[🔗 네이버 부동산에서 보기]({url})")

    description = listing.get("description", "")
    if description:
        st.write("---")
        st.write("**📈 분석 정보**")
        lines = description.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "[전세가율]" in line:
                if "위험" in line:
                    st.error(line)
                elif "주의" in line:
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
                emoji = "🔴" if level == "높음" else "🟡" if level == "보통" else "🟢"
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
