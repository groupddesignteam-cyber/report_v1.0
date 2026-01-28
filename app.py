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
from src.utils import route_files, LoadedFile, load_uploaded_file, classify_file

# Import UI components (kept for potential future use)
# from src.ui.layout import (
#     render_ads_tab, render_design_tab, render_reservation_tab,
#     render_blog_tab, render_youtube_tab, render_setting_tab
# )

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

# App metadata
APP_VERSION = "v1.1.5"
APP_TITLE = "주식회사 그룹디 전략 보고서"
APP_CREATOR = "전략기획팀 이종광팀장"

# Category metadata for file classification display
CATEGORY_META = {
    'reservation': {'label': '예약', 'color': '#3b82f6'},
    'ads': {'label': '광고', 'color': '#8b5cf6'},
    'blog': {'label': '블로그', 'color': '#10b981'},
    'youtube': {'label': '유튜브', 'color': '#ef4444'},
    'design': {'label': '디자인', 'color': '#f59e0b'},
    'setting': {'label': '세팅', 'color': '#6366f1'},
}


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
    """Render compact upload section with file classification preview."""
    # Header with app info
    st.markdown(f"""
    <div style="text-align: center; padding: 1.5rem 0 1rem;">
        <h1 style="font-size: 1.4rem; font-weight: 800; color: #0F172A; margin: 0; letter-spacing: -0.025em;">{APP_TITLE}</h1>
        <p style="font-size: 0.7rem; color: #94a3b8; margin-top: 0.5rem;">{APP_CREATOR} &middot; {APP_VERSION}</p>
    </div>
    """, unsafe_allow_html=True)

    # Settings
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

    # File type description (above uploader)
    st.markdown("""
    <p style="font-size: 0.75rem; color: #64748b; text-align: center; margin-bottom: 0.5rem;">
        예약 / 블로그 / 광고 / 유튜브 / 디자인 / 세팅 파일을 모두 선택하세요 (자동 분류)
    </p>
    """, unsafe_allow_html=True)

    # File uploader (label hidden, drop zone only)
    uploaded_files = st.file_uploader(
        "파일 업로드",
        type=['xlsx', 'csv'],
        accept_multiple_files=True,
        key="unified_upload",
        label_visibility="collapsed"
    )

    # Classification preview + action button
    if uploaded_files:
        # Classify files in real-time
        classification = {}
        unclassified = []
        for uf in uploaded_files:
            category = classify_file(uf.name)
            if category:
                classification.setdefault(category, []).append(uf.name)
            else:
                unclassified.append(uf.name)

        # Show classification grid
        cols = st.columns(6)
        for idx, (cat_key, meta) in enumerate(CATEGORY_META.items()):
            with cols[idx]:
                file_count = len(classification.get(cat_key, []))
                color = meta['color'] if file_count > 0 else '#cbd5e1'
                bg = f"{meta['color']}10" if file_count > 0 else '#f8fafc'
                check = f'<span style="color:{meta["color"]};">&#10003;</span>' if file_count > 0 else '<span style="color:#cbd5e1;">&#8212;</span>'
                st.markdown(f"""
                <div style="background:{bg}; border:1.5px solid {color}; border-radius:10px;
                            padding:10px 4px; text-align:center; transition:all 0.2s;">
                    <div style="font-size:1.1rem; margin-bottom:2px;">{check}</div>
                    <div style="font-size:0.7rem; color:{color}; font-weight:700;">{meta['label']}</div>
                    <div style="font-size:0.65rem; color:#94a3b8; margin-top:2px;">{file_count}개 파일</div>
                </div>
                """, unsafe_allow_html=True)

        # Unclassified files warning
        if unclassified:
            st.warning(f"분류 불가 파일: {', '.join(unclassified)}")

        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        valid_count = len(uploaded_files) - len(unclassified)
        if st.button(f"  {valid_count}개 파일 분석 시작  ", type="primary", use_container_width=True):
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


def render_unified_data_view():
    """Unified data view with inline editing capability per department."""
    results = st.session_state.processed_results

    departments = [
        ('reservation', '예약', results.get('reservation', {})),
        ('ads', '광고', results.get('ads', {})),
        ('blog', '블로그', results.get('blog', {})),
        ('youtube', '유튜브', results.get('youtube', {})),
        ('design', '디자인', results.get('design', {})),
        ('setting', '세팅', results.get('setting', {})),
    ]

    for dept_key, dept_label, dept_data in departments:
        if not dept_data:
            continue
        render_department_card(dept_key, dept_label, dept_data)


# Field definitions for editable departments
DEPT_FIELDS = {
    'reservation': {
        'prev_key': 'prev_month_data',
        'curr_key': 'current_month_data',
        'fields': [
            ('total_reservations', '총 신청'),
            ('completed_count', '내원 확정'),
            ('canceled_count', '취소/노쇼'),
        ],
        'metrics': [
            ('total_reservations', '총 신청', '건'),
            ('completed_count', '내원 확정', '건'),
            ('canceled_count', '취소/노쇼', '건'),
        ]
    },
    'ads': {
        'prev_key': 'prev_month_data',
        'curr_key': 'current_month_data',
        'fields': [
            ('total_spend', '광고비'),
            ('total_impressions', '노출수'),
            ('total_clicks', '클릭수'),
        ],
        'metrics': [
            ('total_spend', '광고비', '원'),
            ('total_impressions', '노출수', '회'),
            ('total_clicks', '클릭수', '회'),
        ]
    },
    'blog': {
        'prev_key': 'prev_month_data',
        'curr_key': 'current_month_data',
        'fields': [
            ('total_posts', '포스팅'),
            ('total_views', '조회수'),
        ],
        'metrics': [
            ('total_posts', '포스팅', '건'),
            ('total_views', '조회수', '회'),
        ]
    },
    'youtube': {
        'prev_key': 'prev_month_data',
        'curr_key': 'current_month_data',
        'fields': [
            ('total_videos', '영상 수'),
            ('total_views', '조회수'),
        ],
        'metrics': [
            ('total_videos', '영상', '개'),
            ('total_views', '조회수', '회'),
        ]
    },
}


def render_department_card(dept_key: str, label: str, data: dict):
    """Render a department card with direct inline editing."""
    meta = CATEGORY_META.get(dept_key, {'color': '#64748b'})
    is_editable = dept_key in DEPT_FIELDS

    # Header
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:8px; margin-top:0.5rem;">
        <div style="width:4px; height:20px; background:{meta['color']}; border-radius:2px;"></div>
        <span style="font-size:0.9rem; font-weight:700; color:#1e293b;">{label}</span>
    </div>
    """, unsafe_allow_html=True)

    if is_editable:
        render_inline_edit(dept_key, data)
    else:
        render_read_metrics(dept_key, data)

    # Show treatment TOP5 and how_found TOP5 for reservation
    if dept_key == 'reservation':
        render_treatment_top5(data)
        render_how_found_top5(data)

    st.markdown("<hr style='border:none; border-top:1px solid #f1f5f9; margin:0.75rem 0;'>", unsafe_allow_html=True)


def render_read_metrics(dept_key: str, data: dict):
    """Show read-only metrics with current values and deltas."""
    if dept_key in DEPT_FIELDS:
        config = DEPT_FIELDS[dept_key]
        prev_data = data.get(config['prev_key']) or {}
        curr_data = data.get(config['curr_key']) or {}

        cols = st.columns(len(config['metrics']))
        for idx, (field_key, field_label, unit) in enumerate(config['metrics']):
            curr_val = safe_int(curr_data.get(field_key, 0))
            prev_val = safe_int(prev_data.get(field_key, 0))
            delta = curr_val - prev_val
            delta_str = f"{delta:+,}{unit}" if delta != 0 else None
            with cols[idx]:
                st.metric(field_label, f"{curr_val:,}{unit}", delta_str)
    elif dept_key == 'design':
        # Design: show task count summary
        tables = data.get('tables', {})
        curr_list = tables.get('curr_task_list', [])
        prev_list = tables.get('prev_task_list', [])
        curr_count = len(curr_list)
        prev_count = len(prev_list)
        curr_pages = sum(t.get('pages', 0) for t in curr_list)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("당월 작업", f"{curr_count}건")
        with col2:
            st.metric("당월 페이지", f"{curr_pages}p")
        with col3:
            delta = curr_count - prev_count if prev_count else None
            st.metric("전월 작업", f"{prev_count}건")
    elif dept_key == 'setting':
        # Setting: show channel completion summary
        kpi = data.get('kpi', {})
        avg_rate = kpi.get('avg_progress_rate', 0)
        total = kpi.get('total_clinics', 0)
        completed = kpi.get('completed_clinics', 0)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("평균 달성률", f"{avg_rate:.0f}%")
        with col2:
            st.metric("완료 병원", f"{completed}개")
        with col3:
            st.metric("전체 병원", f"{total}개")


def render_treatment_top5(data: dict):
    """Show treatment TOP5 breakdown for reservation data."""
    tables = data.get('tables', {})
    curr_treatment = tables.get('treatment_top5', [])
    prev_treatment = tables.get('prev_treatment_top5', [])

    if not curr_treatment and not prev_treatment:
        return

    st.markdown("""
    <div style="margin-top:0.75rem; margin-bottom:0.25rem;">
        <span style="font-size:0.75rem; font-weight:700; color:#475569;">🦷 희망 진료 TOP5</span>
    </div>
    """, unsafe_allow_html=True)

    col_prev, col_curr = st.columns(2)
    with col_prev:
        if prev_treatment:
            st.caption("전월")
            for i, item in enumerate(prev_treatment[:5], 1):
                name = item.get('treatment', '')
                count = item.get('count', 0)
                st.markdown(f"<span style='font-size:0.72rem; color:#64748b;'>{i}. {name} <b>{count}건</b></span>", unsafe_allow_html=True)
        else:
            st.caption("전월: 데이터 없음")
    with col_curr:
        if curr_treatment:
            st.caption("당월")
            for i, item in enumerate(curr_treatment[:5], 1):
                name = item.get('treatment', '')
                count = item.get('count', 0)
                st.markdown(f"<span style='font-size:0.72rem; color:#1e293b;'>{i}. {name} <b>{count}건</b></span>", unsafe_allow_html=True)
        else:
            st.caption("당월: 데이터 없음")


def render_how_found_top5(data: dict):
    """Show how_found TOP5 breakdown for reservation data."""
    tables = data.get('tables', {})
    curr_how_found = tables.get('how_found_top5', [])
    prev_how_found = tables.get('prev_how_found_top5', [])

    if not curr_how_found and not prev_how_found:
        return

    st.markdown("""
    <div style="margin-top:0.75rem; margin-bottom:0.25rem;">
        <span style="font-size:0.75rem; font-weight:700; color:#475569;">🔍 어떻게 알게 되었나요? TOP5</span>
    </div>
    """, unsafe_allow_html=True)

    col_prev, col_curr = st.columns(2)
    with col_prev:
        if prev_how_found:
            st.caption("전월")
            for i, item in enumerate(prev_how_found[:5], 1):
                name = item.get('how_found', '')
                count = item.get('count', 0)
                st.markdown(f"<span style='font-size:0.72rem; color:#64748b;'>{i}. {name} <b>{count}건</b></span>", unsafe_allow_html=True)
        else:
            st.caption("전월: 데이터 없음")
    with col_curr:
        if curr_how_found:
            st.caption("당월")
            for i, item in enumerate(curr_how_found[:5], 1):
                name = item.get('how_found', '')
                count = item.get('count', 0)
                st.markdown(f"<span style='font-size:0.72rem; color:#1e293b;'>{i}. {name} <b>{count}건</b></span>", unsafe_allow_html=True)
        else:
            st.caption("당월: 데이터 없음")


def render_inline_edit(dept_key: str, data: dict):
    """Render inline edit fields for a department."""
    config = DEPT_FIELDS[dept_key]
    prev_data = data.get(config['prev_key']) or {}
    curr_data = data.get(config['curr_key']) or {}

    col_prev, col_curr = st.columns(2)
    edited_prev = {}
    edited_curr = {}

    with col_prev:
        st.caption("전월")
        for field_key, field_label in config['fields']:
            edited_prev[field_key] = st.number_input(
                field_label,
                value=safe_int(prev_data.get(field_key, 0)),
                key=f"ie_{dept_key}_prev_{field_key}",
                min_value=0
            )

    with col_curr:
        st.caption("당월")
        for field_key, field_label in config['fields']:
            edited_curr[field_key] = st.number_input(
                field_label,
                value=safe_int(curr_data.get(field_key, 0)),
                key=f"ie_{dept_key}_curr_{field_key}",
                min_value=0
            )

    if st.button("저장", key=f"save_ie_{dept_key}", type="primary", use_container_width=True):
        results = st.session_state.processed_results
        if config['prev_key'] not in results[dept_key]:
            results[dept_key][config['prev_key']] = {}
        if config['curr_key'] not in results[dept_key]:
            results[dept_key][config['curr_key']] = {}

        for field_key in edited_prev:
            results[dept_key][config['prev_key']][field_key] = edited_prev[field_key]
        for field_key in edited_curr:
            results[dept_key][config['curr_key']][field_key] = edited_curr[field_key]

        st.toast(f"{CATEGORY_META[dept_key]['label']} 데이터 저장됨")
        st.rerun()


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
    source_to_dept = {'블로그': 'blog', '디자인': 'design', '유튜브': 'youtube'}

    # 디자인 데이터 내 다수 거래처 체크
    design_clinics = []
    design_result = st.session_state.processed_results.get('design', {})
    if design_result:
        design_clinics = design_result.get('clean_data', {}).get('clinic_names', [])
        # '미지정' 제외
        design_clinics = [c for c in design_clinics if c and c != '미지정']

    needs_selection = (len(detected_names) > 1 or len(design_clinics) > 1) and not st.session_state.get('clinic_name_confirmed')

    if not needs_selection and len(detected_names) == 1:
        auto_name = list(detected_names)[0]
        if settings['clinic_name'] != auto_name and not st.session_state.get('clinic_name_confirmed'):
            st.session_state.report_settings['clinic_name'] = auto_name
            settings = st.session_state.report_settings
    elif needs_selection:
        st.warning("여러 거래처가 감지되었습니다. 포함할 데이터를 선택하세요.")

        # 소스별 체크박스 (블로그/유튜브 등 cross-source)
        selections = {}
        if len(detected_names) > 1:
            for src, name in source_names.items():
                if src == '디자인':
                    continue  # 디자인은 아래 selectbox로 처리
                selections[src] = st.checkbox(
                    f"{src}: {name}",
                    value=True,
                    key=f"clinic_check_{src}"
                )

        # 디자인 거래처 선택 (selectbox)
        selected_design_clinic = None
        if len(design_clinics) > 1:
            # 블로그/유튜브 거래처명과 매칭되는 디자인 거래처 찾기
            other_clinic_name = None
            for src in ['블로그', '유튜브']:
                if src in source_names:
                    other_clinic_name = source_names[src]
                    break

            sorted_clinics = sorted(design_clinics)
            default_idx = 0
            if other_clinic_name:
                if other_clinic_name in sorted_clinics:
                    default_idx = sorted_clinics.index(other_clinic_name)
                    st.info(f"'{other_clinic_name}'이(가) 디자인 거래처 목록에서 자동 매칭되었습니다.")
                else:
                    sorted_clinics = ["없음"] + sorted_clinics
                    st.warning(f"'{other_clinic_name}'이(가) 디자인 거래처 목록에 없습니다. 직접 선택하거나 '없음'을 선택하세요.")

            selected_design_clinic = st.selectbox(
                "디자인 거래처 선택",
                options=sorted_clinics,
                index=default_idx,
                key="design_clinic_selector"
            )
            if selected_design_clinic == "없음":
                selected_design_clinic = None

        if st.button("설정", type="primary", use_container_width=True):
            # 체크 해제된 소스 데이터 제거
            for src, checked in selections.items():
                if not checked and src in source_to_dept:
                    dept_key = source_to_dept[src]
                    st.session_state.processed_results[dept_key] = {}

            # 디자인 거래처 필터링 → 재처리
            if selected_design_clinic and len(design_clinics) > 1:
                routed = route_files(st.session_state.all_loaded_files)
                if routed['design']:
                    st.session_state.processed_results['design'] = process_design(
                        routed['design'], filter_clinic=selected_design_clinic
                    )

            # 치과명 설정
            if selected_design_clinic:
                st.session_state.report_settings['clinic_name'] = selected_design_clinic
            else:
                selected_sources = [src for src, checked in selections.items() if checked]
                if selected_sources:
                    st.session_state.report_settings['clinic_name'] = source_names[selected_sources[0]]

            st.session_state.clinic_name_confirmed = True
            st.rerun()
        return

    # Header with actions
    col_title, col_add, col_reset = st.columns([4, 1, 1])
    with col_title:
        st.markdown(f"""
        <div style="margin-bottom: 0.25rem;">
            <h1 style="margin-bottom: 0; font-size: 1.5rem;">{settings['clinic_name']}</h1>
            <p style="color: #64748b; font-size: 0.8rem; margin-top: 2px;">{settings['report_date']} | 월간 마케팅 분석 보고서</p>
        </div>
        """, unsafe_allow_html=True)
    with col_add:
        if st.button("파일 추가", key="btn_add_files", use_container_width=True):
            st.session_state.show_additional_upload = not st.session_state.get('show_additional_upload', False)
            st.rerun()
    with col_reset:
        if st.button("새로 시작", use_container_width=True):
            st.session_state.files_uploaded = False
            st.session_state.processed_results = {}
            st.session_state.all_loaded_files = []
            st.session_state.clinic_name_confirmed = False
            st.session_state.show_additional_upload = False
            st.rerun()

    # Data status indicator
    results = st.session_state.processed_results
    status_html = '<div style="display:flex; gap:12px; justify-content:center; padding:6px 0; margin-bottom:8px;">'
    for cat_key, meta in CATEGORY_META.items():
        has_data = bool(results.get(cat_key))
        dot_color = meta['color'] if has_data else '#cbd5e1'
        dot_char = '&#9679;' if has_data else '&#9675;'
        status_html += f'<span style="font-size:0.72rem; color:{dot_color}; font-weight:600;">{dot_char} {meta["label"]}</span>'
    status_html += '</div>'
    st.markdown(status_html, unsafe_allow_html=True)

    # Additional file upload (toggle)
    if st.session_state.get('show_additional_upload'):
        additional_files = st.file_uploader(
            "추가 파일 선택",
            type=['xlsx', 'csv'],
            accept_multiple_files=True,
            key="additional_upload"
        )
        if additional_files:
            if st.button("추가 파일 처리", type="primary", use_container_width=True):
                process_uploaded_files(additional_files)
                st.session_state.show_additional_upload = False
                st.rerun()

    # Generate HTML report
    html_report = generate_html_report(
        st.session_state.processed_results,
        clinic_name=settings['clinic_name'],
        report_date=settings['report_date'],
        manager_comment=st.session_state.get('manager_comment', '')
    )
    filename = get_report_filename(settings['clinic_name'])

    # Download button
    st.markdown("<div style='height: 0.25rem;'></div>", unsafe_allow_html=True)
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

    # 2 Tabs: Preview / Data
    tab_preview, tab_data = st.tabs(["보고서 미리보기", "데이터 확인 및 수정"])

    with tab_preview:
        render_html_preview(html_report)

    with tab_data:
        render_unified_data_view()

    # Bottom settings expander
    with st.expander("보고서 설정", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_clinic_name = st.text_input("치과명", value=settings['clinic_name'], key="settings_clinic_name")
        with col2:
            new_report_date = st.text_input("보고서 작성일", value=settings['report_date'], key="settings_report_date")

        manager_comment = st.text_area(
            "담당자 코멘트 (보고서 Executive Summary에 표시)",
            value=st.session_state.get('manager_comment', ''),
            height=80,
            placeholder="예: 이번 달은 광고 예산 증액으로 노출이 크게 증가했으며...",
            key="manager_comment_input"
        )
        st.session_state['manager_comment'] = manager_comment

        if new_clinic_name != settings['clinic_name'] or new_report_date != settings['report_date']:
            if st.button("설정 저장", type="primary"):
                st.session_state.report_settings['clinic_name'] = new_clinic_name
                st.session_state.report_settings['report_date'] = new_report_date
                st.rerun()


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