"""
Daily Report Generator - Streamlit Application
Clean UI with Centralized Upload & Data Aggregation
"""

import streamlit as st
from datetime import datetime
import os

# Import processors
from src.processors import (
    process_ads,
    process_design,
    process_reservation,
    process_blog,
    process_youtube,
    process_setting
)

# Import utilities
from src.utils import route_files, LoadedFile, load_uploaded_file

# Import UI components
from src.ui.layout import (
    render_ads_tab,
    render_design_tab,
    render_reservation_tab,
    render_blog_tab,
    render_youtube_tab,
    render_setting_tab
)

# Import HTML generator
from src.reporting.html_generator import generate_html_report, get_report_filename


# Page configuration
st.set_page_config(
    page_title="월간 마케팅 리포트",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load custom CSS
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), 'src', 'ui', 'style.css')
    if os.path.exists(css_path):
        with open(css_path, 'r', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css()


def initialize_session_state():
    """Initialize session state variables."""
    if 'processed_results' not in st.session_state:
        st.session_state.processed_results = {
            'ads': {},
            'design': {},
            'reservation': {},
            'blog': {},
            'youtube': {},
            'setting': {}
        }
    if 'files_uploaded' not in st.session_state:
        st.session_state.files_uploaded = False

    # Store all loaded files to enable aggregation
    if 'all_loaded_files' not in st.session_state:
        st.session_state.all_loaded_files = []

    # Report settings (editable by user)
    if 'report_settings' not in st.session_state:
        st.session_state.report_settings = {
            'clinic_name': '서울리멤버치과',
            'report_date': datetime.now().strftime('%Y년 %m월 %d일'),
            'report_title_prefix': '월간 분석 보고서'
        }

    # Edit mode flag
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False


def process_uploaded_files(uploaded_files):
    """Process uploaded files and route to appropriate processors."""
    if not uploaded_files:
        return

    # Add new files to session state (avoid duplicates by name)
    existing_names = {f.name for f in st.session_state.all_loaded_files}
    new_files_count = 0
    
    for uf in uploaded_files:
        if uf.name not in existing_names:
            st.session_state.all_loaded_files.append(load_uploaded_file(uf))
            existing_names.add(uf.name)
            new_files_count += 1
    
    if not st.session_state.all_loaded_files:
        st.warning("처리할 파일이 없습니다.")
        return

    # Route ALL accumulated files to processors
    routed_files = route_files(st.session_state.all_loaded_files)

    # Process each department's files
    # 순서 중요: 예약 데이터를 먼저 처리하여 광고의 CPA 계산에 사용
    with st.spinner(f'데이터 처리 중... (총 {len(st.session_state.all_loaded_files)}개 파일)'):
        # 1. 예약 데이터 먼저 처리 (광고 CPA 계산에 필요)
        if routed_files['reservation']:
            st.session_state.processed_results['reservation'] = process_reservation(routed_files['reservation'])

        # 2. 광고 데이터 처리 (예약 데이터로 CPA 계산)
        if routed_files['ads']:
            reservation_data = st.session_state.processed_results.get('reservation')
            st.session_state.processed_results['ads'] = process_ads(routed_files['ads'], reservation_data)

        if routed_files['design']:
            st.session_state.processed_results['design'] = process_design(routed_files['design'])

        if routed_files['blog']:
            st.session_state.processed_results['blog'] = process_blog(routed_files['blog'])

        if routed_files['youtube']:
            st.session_state.processed_results['youtube'] = process_youtube(routed_files['youtube'])

        if routed_files['setting']:
            st.session_state.processed_results['setting'] = process_setting(routed_files['setting'])

    st.session_state.files_uploaded = True
    st.session_state.clinic_name_confirmed = False
    st.rerun()


def render_upload_section():
    """Render compact upload section - everything visible at once."""
    # Minimal header
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0 0.75rem;">
        <h1 style="font-size: 1.5rem; font-weight: 800; color: #0F172A; margin: 0; letter-spacing: -0.025em;">월간 마케팅 리포트</h1>
        <p style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem;">파일 업로드 → 자동 분석 → HTML 보고서 생성</p>
    </div>
    """, unsafe_allow_html=True)

    # Settings + Upload in one view
    col_name, col_date = st.columns([3, 2])
    with col_name:
        clinic_name = st.text_input(
            "치과명",
            value=st.session_state.report_settings['clinic_name'],
            placeholder="서울리멤버치과",
            key="main_clinic_name",
            label_visibility="collapsed"
        )
        if clinic_name != st.session_state.report_settings['clinic_name']:
            st.session_state.report_settings['clinic_name'] = clinic_name
    with col_date:
        report_date = st.text_input(
            "작성일",
            value=st.session_state.report_settings['report_date'],
            key="main_report_date",
            label_visibility="collapsed"
        )
        if report_date != st.session_state.report_settings['report_date']:
            st.session_state.report_settings['report_date'] = report_date

    # File uploader - direct, no extra decoration
    uploaded_files = st.file_uploader(
        "예약/블로그/광고/유튜브/디자인/세팅 파일을 모두 선택하세요 (자동 분류)",
        type=['xlsx', 'csv'],
        accept_multiple_files=True,
        key="unified_upload"
    )

    # Action button
    if uploaded_files:
        if st.button(f"  {len(uploaded_files)}개 파일 분석 시작  ", type="primary", use_container_width=True):
            process_uploaded_files(uploaded_files)



def safe_int(value, default=0):
    """Safely convert value to int, handling None, NaN, and other edge cases."""
    if value is None:
        return default
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def render_data_editor():
    """Render manual data editing interface."""
    st.markdown("### ✏️ 데이터 수동 편집")
    st.caption("각 섹션의 데이터를 수동으로 수정할 수 있습니다. 수정 후 '변경사항 적용' 버튼을 클릭하세요.")

    results = st.session_state.processed_results

    # 예약 데이터 편집
    with st.expander("📅 예약 데이터 편집", expanded=False):
        if results.get('reservation'):
            res_data = results['reservation']
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**전월 데이터**")
                prev_data = res_data.get('prev_month_data') or {}
                prev_total = st.number_input("전월 총 예약건", value=safe_int(prev_data.get('total_reservations', 0)), key="edit_res_prev_total")
                prev_new = st.number_input("전월 신규 예약", value=safe_int(prev_data.get('new_reservations', 0)), key="edit_res_prev_new")
                prev_revisit = st.number_input("전월 재진 예약", value=safe_int(prev_data.get('revisit_reservations', 0)), key="edit_res_prev_revisit")

            with col2:
                st.markdown("**당월 데이터**")
                curr_data = res_data.get('current_month_data') or {}
                curr_total = st.number_input("당월 총 예약건", value=safe_int(curr_data.get('total_reservations', 0)), key="edit_res_curr_total")
                curr_new = st.number_input("당월 신규 예약", value=safe_int(curr_data.get('new_reservations', 0)), key="edit_res_curr_new")
                curr_revisit = st.number_input("당월 재진 예약", value=safe_int(curr_data.get('revisit_reservations', 0)), key="edit_res_curr_revisit")

            if st.button("💾 예약 데이터 저장", key="save_res"):
                results['reservation']['prev_month_data']['total_reservations'] = prev_total
                results['reservation']['prev_month_data']['new_reservations'] = prev_new
                results['reservation']['prev_month_data']['revisit_reservations'] = prev_revisit
                results['reservation']['current_month_data']['total_reservations'] = curr_total
                results['reservation']['current_month_data']['new_reservations'] = curr_new
                results['reservation']['current_month_data']['revisit_reservations'] = curr_revisit
                st.success("예약 데이터가 저장되었습니다!")
                st.rerun()
        else:
            st.info("예약 데이터가 없습니다.")

    # 광고 데이터 편집
    with st.expander("📊 광고 데이터 편집", expanded=False):
        if results.get('ads'):
            ads_data = results['ads']
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**전월 데이터**")
                prev_ads = ads_data.get('prev_month_data') or {}
                prev_spend = st.number_input("전월 광고비", value=safe_int(prev_ads.get('total_spend', 0)), key="edit_ads_prev_spend")
                prev_imp = st.number_input("전월 노출수", value=safe_int(prev_ads.get('total_impressions', 0)), key="edit_ads_prev_imp")
                prev_clicks = st.number_input("전월 클릭수", value=safe_int(prev_ads.get('total_clicks', 0)), key="edit_ads_prev_clicks")

            with col2:
                st.markdown("**당월 데이터**")
                curr_ads = ads_data.get('current_month_data') or {}
                curr_spend = st.number_input("당월 광고비", value=safe_int(curr_ads.get('total_spend', 0)), key="edit_ads_curr_spend")
                curr_imp = st.number_input("당월 노출수", value=safe_int(curr_ads.get('total_impressions', 0)), key="edit_ads_curr_imp")
                curr_clicks = st.number_input("당월 클릭수", value=safe_int(curr_ads.get('total_clicks', 0)), key="edit_ads_curr_clicks")

            if st.button("💾 광고 데이터 저장", key="save_ads"):
                results['ads']['prev_month_data']['total_spend'] = prev_spend
                results['ads']['prev_month_data']['total_impressions'] = prev_imp
                results['ads']['prev_month_data']['total_clicks'] = prev_clicks
                results['ads']['current_month_data']['total_spend'] = curr_spend
                results['ads']['current_month_data']['total_impressions'] = curr_imp
                results['ads']['current_month_data']['total_clicks'] = curr_clicks
                st.success("광고 데이터가 저장되었습니다!")
                st.rerun()
        else:
            st.info("광고 데이터가 없습니다.")

    # 블로그 데이터 편집
    with st.expander("📝 블로그 데이터 편집", expanded=False):
        if results.get('blog'):
            blog_data = results['blog']
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**전월 데이터**")
                prev_blog = blog_data.get('prev_month_data') or {}
                prev_posts = st.number_input("전월 포스팅 수", value=safe_int(prev_blog.get('total_posts', 0)), key="edit_blog_prev_posts")
                prev_views = st.number_input("전월 조회수", value=safe_int(prev_blog.get('total_views', 0)), key="edit_blog_prev_views")

            with col2:
                st.markdown("**당월 데이터**")
                curr_blog = blog_data.get('current_month_data') or {}
                curr_posts = st.number_input("당월 포스팅 수", value=safe_int(curr_blog.get('total_posts', 0)), key="edit_blog_curr_posts")
                curr_views = st.number_input("당월 조회수", value=safe_int(curr_blog.get('total_views', 0)), key="edit_blog_curr_views")

            if st.button("💾 블로그 데이터 저장", key="save_blog"):
                results['blog']['prev_month_data']['total_posts'] = prev_posts
                results['blog']['prev_month_data']['total_views'] = prev_views
                results['blog']['current_month_data']['total_posts'] = curr_posts
                results['blog']['current_month_data']['total_views'] = curr_views
                st.success("블로그 데이터가 저장되었습니다!")
                st.rerun()
        else:
            st.info("블로그 데이터가 없습니다.")

    # 유튜브 데이터 편집
    with st.expander("🎬 유튜브 데이터 편집", expanded=False):
        if results.get('youtube'):
            yt_data = results['youtube']
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**전월 데이터**")
                prev_yt = yt_data.get('prev_month_data') or {}
                prev_videos = st.number_input("전월 영상 수", value=safe_int(prev_yt.get('total_videos', 0)), key="edit_yt_prev_videos")
                prev_yt_views = st.number_input("전월 조회수", value=safe_int(prev_yt.get('total_views', 0)), key="edit_yt_prev_views")

            with col2:
                st.markdown("**당월 데이터**")
                curr_yt = yt_data.get('current_month_data') or {}
                curr_videos = st.number_input("당월 영상 수", value=safe_int(curr_yt.get('total_videos', 0)), key="edit_yt_curr_videos")
                curr_yt_views = st.number_input("당월 조회수", value=safe_int(curr_yt.get('total_views', 0)), key="edit_yt_curr_views")

            if st.button("💾 유튜브 데이터 저장", key="save_yt"):
                results['youtube']['prev_month_data']['total_videos'] = prev_videos
                results['youtube']['prev_month_data']['total_views'] = prev_yt_views
                results['youtube']['current_month_data']['total_videos'] = curr_videos
                results['youtube']['current_month_data']['total_views'] = curr_yt_views
                st.success("유튜브 데이터가 저장되었습니다!")
                st.rerun()
        else:
            st.info("유튜브 데이터가 없습니다.")


def render_html_preview(html_content: str):
    """Render HTML report preview in an iframe."""
    import base64

    # Encode HTML to base64 for iframe src
    b64_html = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')

    # Create iframe with the HTML content
    iframe_html = f"""
    <div style="border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin: 1rem 0;">
        <iframe
            src="data:text/html;base64,{b64_html}"
            width="100%"
            height="800px"
            style="border: none;"
        ></iframe>
    </div>
    """
    st.markdown(iframe_html, unsafe_allow_html=True)


def check_clinic_name_mismatch():
    """Check for clinic name mismatches across data files and return warnings."""
    results = st.session_state.processed_results
    detected_names = set()
    source_names = {}  # {source: clinic_name}

    # 예약 데이터에서 거래처명 추출
    if results.get('reservation'):
        res_data = results['reservation'].get('clean_data', {})
        # 예약 데이터는 파일명에서 추출하거나 별도 필드에서 가져올 수 있음

    # 블로그 데이터에서 거래처명 추출
    if results.get('blog'):
        blog_work = results['blog'].get('clean_data', {}).get('work', {})
        by_clinic = blog_work.get('by_clinic', [])
        for clinic_info in by_clinic:
            clinic_name = clinic_info.get('clinic', '')
            if clinic_name:
                detected_names.add(clinic_name)
                source_names['블로그'] = clinic_name

    # 디자인 데이터에서 거래처명 추출
    if results.get('design'):
        design_clean = results['design'].get('clean_data', {})
        if 'clinic_name' in design_clean:
            clinic_name = design_clean['clinic_name']
            if clinic_name:
                detected_names.add(clinic_name)
                source_names['디자인'] = clinic_name

    # 유튜브 데이터에서 거래처명 추출 (파일명에서)
    if results.get('youtube'):
        yt_clean = results['youtube'].get('clean_data', {})
        if 'clinic_name' in yt_clean:
            clinic_name = yt_clean['clinic_name']
            if clinic_name:
                detected_names.add(clinic_name)
                source_names['유튜브'] = clinic_name

    return detected_names, source_names


def render_dashboard():
    """Render the main dashboard after data processing."""
    settings = st.session_state.report_settings

    # 거래처명 자동 감지 및 불일치 체크
    detected_names, source_names = check_clinic_name_mismatch()
    if len(detected_names) == 1:
        auto_name = list(detected_names)[0]
        if settings['clinic_name'] != auto_name and not st.session_state.get('clinic_name_confirmed'):
            st.session_state.report_settings['clinic_name'] = auto_name
            settings = st.session_state.report_settings
    elif len(detected_names) > 1 and not st.session_state.get('clinic_name_confirmed'):
        name_list = sorted(detected_names)
        with st.container():
            st.warning("데이터에서 서로 다른 거래처명이 감지되었습니다.")
            sources_text = ' / '.join([f'{src}: **{name}**' for src, name in source_names.items()])
            st.caption(sources_text)
            col_select, col_btn = st.columns([3, 1])
            with col_select:
                selected_name = st.selectbox(
                    "분석할 치과를 선택하세요",
                    options=name_list,
                    key="clinic_name_selector",
                    label_visibility="collapsed"
                )
            with col_btn:
                if st.button("설정", type="primary", use_container_width=True):
                    st.session_state.report_settings['clinic_name'] = selected_name
                    st.session_state.clinic_name_confirmed = True
                    st.rerun()
        return  # 선택 전에는 대시보드 표시하지 않음

    # Compact header
    col_title, col_actions = st.columns([3, 1])
    with col_title:
        st.markdown(f"""
        <div style="margin-bottom: 0.5rem;">
            <h1 style="margin-bottom: 0; font-size: 1.5rem;">{settings['clinic_name']}</h1>
            <p style="color: #64748b; font-size: 0.8rem; margin-top: 2px;">{settings['report_date']} | 월간 마케팅 분석 보고서</p>
        </div>
        """, unsafe_allow_html=True)
    with col_actions:
        if st.button("새로 시작", use_container_width=True):
            st.session_state.files_uploaded = False
            st.session_state.processed_results = {}
            st.session_state.all_loaded_files = []
            st.session_state.edit_mode = False
            st.session_state.clinic_name_confirmed = False
            st.rerun()

    # Generate HTML report
    html_report = generate_html_report(
        st.session_state.processed_results,
        clinic_name=settings['clinic_name'],
        report_date=settings['report_date'],
        manager_comment=st.session_state.get('manager_comment', '')
    )
    filename = get_report_filename(settings['clinic_name'])

    # Primary action: Download
    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.download_button(
            label="보고서 다운로드 (HTML)",
            data=html_report.encode('utf-8'),
            file_name=filename,
            mime="text/html",
            use_container_width=True
        )

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    # Tabs: Preview / Data / Edit / Settings
    tab_preview, tab_data, tab_edit, tab_settings = st.tabs([
        "보고서 미리보기", "데이터 확인", "데이터 편집", "설정"
    ])

    with tab_preview:
        render_html_preview(html_report)

    with tab_data:
        results = st.session_state.processed_results
        dept_tabs = st.tabs(["예약", "블로그", "광고", "디자인", "유튜브", "세팅"])

        with dept_tabs[0]:
            render_reservation_tab(results.get('reservation', {}))
        with dept_tabs[1]:
            render_blog_tab(results.get('blog', {}))
        with dept_tabs[2]:
            render_ads_tab(results.get('ads', {}))
        with dept_tabs[3]:
            render_design_tab(results.get('design', {}))
        with dept_tabs[4]:
            render_youtube_tab(results.get('youtube', {}))
        with dept_tabs[5]:
            render_setting_tab(results.get('setting', {}))

    with tab_edit:
        render_data_editor()

    with tab_settings:
        # Clinic name & date
        col1, col2 = st.columns(2)
        with col1:
            new_clinic_name = st.text_input("치과명", value=settings['clinic_name'], key="settings_clinic_name")
        with col2:
            new_report_date = st.text_input("보고서 작성일", value=settings['report_date'], key="settings_report_date")

        if new_clinic_name != settings['clinic_name'] or new_report_date != settings['report_date']:
            if st.button("설정 저장", type="primary"):
                st.session_state.report_settings['clinic_name'] = new_clinic_name
                st.session_state.report_settings['report_date'] = new_report_date
                st.rerun()

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

        # Manager comment
        st.markdown("**담당자 코멘트** (보고서 Executive Summary에 표시)")
        manager_comment = st.text_area(
            "담당자 코멘트",
            value=st.session_state.get('manager_comment', ''),
            height=80,
            placeholder="예: 이번 달은 광고 예산 증액으로 노출이 크게 증가했으며...",
            key="manager_comment_input",
            label_visibility="collapsed"
        )
        st.session_state['manager_comment'] = manager_comment


def main():
    """Main application entry point."""
    initialize_session_state()
    
    if not st.session_state.files_uploaded:
        render_upload_section()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
# git initial tracking trigger