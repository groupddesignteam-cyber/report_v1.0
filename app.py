"""
Daily Report Generator - Streamlit Application
Clean UI with Centralized Upload & Data Aggregation
"""

import streamlit as st
from datetime import datetime
import os
import re

# Import processors
from src.processors import (
    process_ads,
    process_design,
    process_reservation,
    process_blog,
    process_youtube,
    process_setting,
    process_feedback
)
from src.reporting.feedback_report import generate_feedback_html_report, get_feedback_report_filename
from src.llm.llm_client import (
    generate_department_draft_and_strategy,
    generate_executive_summary,
    has_llm_client_configured,
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

APP_DEPLOY_TAG = "release-2026.02.23-policy-flow"


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
APP_VERSION = "v3.5.0"
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

    # Analysis selector state
    if 'selected_months' not in st.session_state:
        st.session_state.selected_months = []
    if 'selected_departments' not in st.session_state:
        st.session_state.selected_departments = []
    if 'selector_confirmed' not in st.session_state:
        st.session_state.selector_confirmed = False

    # Action plan editor state
    if 'action_plan_items' not in st.session_state:
        st.session_state.action_plan_items = {}  # {dept_key: [{'text': '...'}]}

    # Ensure package-based action plan registry is synced with latest catalog file.
    _sync_team_package_registry_from_catalog()

    # Initialize package selection state for catalog-driven teams.
    for _tkey, _tcfg in TEAM_PACKAGE_REGISTRY.items():
        for _mkey in _tcfg["modes"]:
            _sk = f"{_tkey}_{_mkey}_selections"
            if _sk not in st.session_state:
                st.session_state[_sk] = []
        _dk = f"{_tkey}_proposal_done"
        if _dk not in st.session_state:
            st.session_state[_dk] = False

    # AI executive summary cache
    if 'ai_exec_summary' not in st.session_state:
        st.session_state.ai_exec_summary = None

    # Feedback mode state
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = 'marketing'
    if 'feedback_result' not in st.session_state:
        st.session_state.feedback_result = None
    if 'feedback_file_uploaded' not in st.session_state:
        st.session_state.feedback_file_uploaded = False
    if 'feedback_raw_df' not in st.session_state:
        st.session_state.feedback_raw_df = None
    if 'feedback_available_months' not in st.session_state:
        st.session_state.feedback_available_months = []
    if 'feedback_selected_months' not in st.session_state:
        st.session_state.feedback_selected_months = []
    if 'feedback_month_confirmed' not in st.session_state:
        st.session_state.feedback_month_confirmed = False



def process_uploaded_files(uploaded_files):
    """Process uploaded files and route to appropriate processors."""
    if not uploaded_files:
        return

    from src.utils import LoadedFile

    # Add new files to session state (avoid duplicates by name)
    existing_names = {f.name for f in st.session_state.all_loaded_files}
    new_files_count = 0
    
    if isinstance(uploaded_files, dict):
        for name, file_bytes in uploaded_files.items():
            if name not in existing_names:
                st.session_state.all_loaded_files.append(LoadedFile(name=name, raw_bytes=file_bytes))
                existing_names.add(name)
                new_files_count += 1
    else:
        for uf in uploaded_files:
            if hasattr(uf, "name"):
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
    st.session_state.selector_confirmed = False
    st.session_state.action_plan_items = {}
    st.session_state.ai_exec_summary = None
    st.rerun()


# Analysis selector constants
ANALYSIS_OPTIONS = [
    ('reservation', '예약 분석'),
    ('ads', '광고 분석'),
    ('blog', '블로그 분석'),
    ('youtube', '유튜브 분석'),
    ('design', '디자인 분석'),
    ('setting', '세팅 현황'),
]

# Action plan team definitions
ACTION_PLAN_TEAMS = [
    ('marketing', '마케팅팀', '#3b82f6'),
    ('design', '디자인팀', '#f59e0b'),
    ('youtube', '영상팀', '#ef4444'),
    ('strategy', '전략기획팀', '#8b5cf6'),
    ('ads', '광고팀', '#10b981'),
    ('content', '콘텐츠팀', '#06b6d4'),
]

DEPT_LABEL_TO_KEY = {
    '예약': 'marketing',
    '블로그': 'content',
    '유튜브': 'youtube',
    '디자인': 'design',
    '디자인팀': 'design',
    '네이버 광고': 'ads',
    '광고': 'ads',
    '광고팀': 'ads',
}


def format_month_label(ym: str) -> str:
    """Convert 'YYYY-MM' to 'YYYY년 M월'."""
    try:
        parts = ym.split('-')
        return f"{parts[0]}년 {int(parts[1])}월"
    except Exception:
        return ym


def detect_available_months() -> list:
    """Scan processed results to find all available YYYY-MM months."""
    results = st.session_state.processed_results
    months = set()

    for dept_key, dept_data in results.items():
        if not dept_data:
            continue

        # Primary: month and prev_month
        if dept_data.get('month'):
            months.add(dept_data['month'])
        if dept_data.get('prev_month'):
            months.add(dept_data['prev_month'])

        # Charts monthly data
        for chart_key in ['monthly_trend', 'views_trend', 'monthly_views',
                          'monthly_content_totals', 'monthly_traffic_totals']:
            for item in dept_data.get('charts', {}).get(chart_key, []):
                if isinstance(item, dict) and item.get('year_month'):
                    months.add(item['year_month'])

        # Blog work monthly_summary
        if dept_key == 'blog':
            for item in dept_data.get('clean_data', {}).get('work', {}).get('monthly_summary', []):
                if isinstance(item, dict) and item.get('year_month'):
                    months.add(item['year_month'])

        # Ads monthly_spend
        if dept_key == 'ads':
            for item in dept_data.get('tables', {}).get('monthly_spend', []):
                if isinstance(item, dict) and item.get('year_month'):
                    months.add(item['year_month'])

    return sorted(months)


def render_analysis_selector():
    """Render month and department selector UI (Step 3)."""
    results = st.session_state.processed_results
    available_months = detect_available_months()

    # Detect which departments have data
    available_depts = []
    for dept_key, dept_label in ANALYSIS_OPTIONS:
        if results.get(dept_key):
            available_depts.append((dept_key, dept_label))

    if not available_depts:
        st.warning("처리된 데이터가 없습니다.")
        return

    # Step 3 Header
    st.markdown("""
    <div style="display:flex; align-items:center; gap:10px; margin:1.5rem 0 1rem;">
        <div style="width:30px; height:30px; background:linear-gradient(135deg, #10b981, #059669); color:white;
                    border-radius:50%; display:flex; align-items:center; justify-content:center;
                    font-weight:700; font-size:0.9rem; box-shadow:0 2px 8px rgba(16,185,129,0.3);">3</div>
        <div style="font-weight:700; color:#0f172a; font-size:1.15rem; letter-spacing:-0.02em;">분석 범위 설정</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    
    with col1:
        # Month Selector
        if available_months:
            st.markdown("""
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.25rem; margin-bottom:0.75rem;">
                <div style="font-weight:600; color:#1e293b; font-size:0.95rem; margin-bottom:4px;">분석 기간 선택</div>
                <div style="font-size:0.8rem; color:#64748b;">비교할 월 선택 (전월 + 당월)</div>
            </div>
            """, unsafe_allow_html=True)
    
            month_labels = [format_month_label(m) for m in available_months]
            month_map = dict(zip(month_labels, available_months))
    
            # Default: last 2 months
            default_months = month_labels[-2:] if len(month_labels) >= 2 else month_labels
    
            selected_month_labels = st.multiselect(
                "월 선택",
                options=month_labels,
                default=default_months,
                key="month_selector_widget",
                label_visibility="collapsed"
            )
    
            selected_months = [month_map[label] for label in selected_month_labels]
        else:
            selected_months = []

    with col2:
        # Department Selector
        st.markdown("""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.25rem; margin-bottom:0.75rem;">
            <div style="font-weight:600; color:#1e293b; font-size:0.95rem; margin-bottom:4px;">분석 항목 선택</div>
            <div style="font-size:0.8rem; color:#64748b;">보고서에 포함할 항목 선택</div>
        </div>
        """, unsafe_allow_html=True)
    
        dept_labels = [label for _, label in available_depts]
        dept_map = {label: key for key, label in available_depts}
    
        selected_dept_labels = st.multiselect(
            "분석 항목",
            options=dept_labels,
            default=dept_labels,
            key="dept_selector_widget",
            label_visibility="collapsed"
        )
    
        selected_depts = [dept_map[label] for label in selected_dept_labels]

    # Visual chips
    if selected_dept_labels:
        chips_html = '<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:0.5rem;">'
        for label in selected_dept_labels:
            dept_key = dept_map[label]
            color = CATEGORY_META.get(dept_key, {}).get('color', '#64748b')
            chips_html += f'''
            <span style="display:inline-flex; align-items:center; gap:4px; padding:5px 14px;
                         background:{color}15; border:1px solid {color}40; border-radius:20px;
                         font-size:0.78rem; font-weight:600; color:{color};">
                <span style="width:6px; height:6px; background:{color}; border-radius:50%;"></span>
                {label}
            </span>'''
        chips_html += '</div>'
        st.markdown(chips_html, unsafe_allow_html=True)

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    # Confirm button
    if selected_depts:
        month_text = ""
        if selected_months:
            month_text = f" ({', '.join(format_month_label(m) for m in sorted(selected_months))})"

        if st.button(
            f"보고서 생성{month_text}",
            type="primary",
            use_container_width=True,
            key="confirm_analysis_selector"
        ):
            st.session_state.selected_months = sorted(selected_months)
            st.session_state.selected_departments = selected_depts
            st.session_state.selector_confirmed = True
            st.rerun()
    else:
        st.info("최소 1개 분석 항목을 선택하세요.")


def filter_results_by_selection() -> dict:
    """Filter processed_results by selected departments and months."""
    import copy
    results = st.session_state.processed_results
    selected_depts = st.session_state.selected_departments
    selected_months = sorted(st.session_state.selected_months)

    filtered = {}
    for dept_key in ['reservation', 'ads', 'blog', 'youtube', 'design', 'setting']:
        if dept_key not in selected_depts:
            filtered[dept_key] = {}
            continue

        dept_data = results.get(dept_key, {})
        if not dept_data or not selected_months or dept_key == 'setting':
            filtered[dept_key] = dept_data
            continue

        target_current = selected_months[-1]
        target_prev = selected_months[-2] if len(selected_months) >= 2 else None

        # 이미 일치하면 그대로 사용
        if dept_data.get('month') == target_current and dept_data.get('prev_month') == target_prev:
            filtered[dept_key] = dept_data
            continue

        # 월 재매핑
        remapped = copy.deepcopy(dept_data)
        remapped['month'] = target_current
        remapped['prev_month'] = target_prev

        # work monthly_summary에서 해당 월 데이터 찾기
        monthly_summaries = remapped.get('clean_data', {}).get('work', {}).get('monthly_summary', [])
        curr_work = next((s for s in monthly_summaries if s.get('year_month') == target_current), {})
        prev_work = next((s for s in monthly_summaries if s.get('year_month') == target_prev), {})

        # current/prev month data 재매핑
        if curr_work:
            remapped['current_month_data'] = remapped.get('current_month_data', {}).copy()
            remapped['current_month_data']['work'] = curr_work
        if prev_work:
            remapped['prev_month_data'] = remapped.get('prev_month_data', {}).copy()
            remapped['prev_month_data']['work'] = prev_work

        # 조회수 재매핑
        views_by_month = remapped.get('clean_data', {}).get('views_monthly', {}).get('total_by_month', {})
        curr_views = views_by_month.get(target_current, 0)
        prev_views = views_by_month.get(target_prev, 0)
        remapped.setdefault('current_month_data', {})['total_views'] = curr_views
        remapped.setdefault('prev_month_data', {})['total_views'] = prev_views

        # growth_rate 재계산
        if prev_views > 0:
            remapped['growth_rate'] = {'views': ((curr_views - prev_views) / prev_views) * 100}
        else:
            remapped['growth_rate'] = {'views': 0}

        # KPI 재계산
        contract_count = curr_work.get('contract_count', 0)
        published_count = curr_work.get('published_count', 0)
        carryover = curr_work.get('base_carryover', curr_work.get('carryover', 0))
        completion_rate = (published_count / contract_count * 100) if contract_count > 0 else 0

        remapped['kpi'] = {
            'publish_completion_rate': round(completion_rate, 2),
            'remaining_cnt': curr_work.get('remaining_count', curr_work.get('remaining', 0)),
            'total_views': curr_views,
            'views_mom_growth': round(remapped['growth_rate'].get('views', 0), 2),
            'published_count': published_count,
            'contract_count': contract_count,
            'carryover_count': carryover,
            'pending_data_count': curr_work.get('pending_data_count', 0),
            'prev_published_count': prev_work.get('published_count', 0),
            'prev_contract_count': prev_work.get('contract_count', 0),
            'prev_carryover_count': prev_work.get('base_carryover', prev_work.get('carryover', 0)),
            'prev_total_views': prev_views
        }

        # 포스팅 목록 재매핑
        all_work_summary = remapped.get('tables', {}).get('work_summary', [])
        if all_work_summary:
            curr_posts = [w for w in all_work_summary if w.get('year_month') == target_current]
            prev_posts = [w for w in all_work_summary if w.get('year_month') == target_prev]
            remapped['tables']['curr_work_summary'] = curr_posts
            remapped['tables']['prev_work_summary'] = prev_posts

            remapped['tables']['posting_list'] = [
                {'title': p.get('post_title', ''), 'url': p.get('post_url', ''),
                 'status': p.get('status', ''), 'write_date': p.get('upload_date', '')}
                for p in curr_posts
                if p.get('post_title', '').lower() not in ('', 'nan')
            ]
            remapped['tables']['prev_posting_list'] = [
                {'title': p.get('post_title', ''), 'url': p.get('post_url', ''),
                 'status': p.get('status', ''), 'write_date': p.get('upload_date', '')}
                for p in prev_posts
                if p.get('post_title', '').lower() not in ('', 'nan')
            ]

        # TOP5 월별 데이터 재매핑
        for key in ['views', 'traffic', 'source']:
            monthly_data = remapped.get('tables', {}).get(f'monthly_{key}_top5', {})
            if isinstance(monthly_data, dict):
                remapped['tables'][f'{key}_top5'] = monthly_data.get(target_current, [])
                remapped['tables'][f'prev_{key}_top5'] = monthly_data.get(target_prev, [])

        filtered[dept_key] = remapped

    return filtered


def render_upload_section():
    """Render compact upload section with file classification preview."""
    # Modern Header with Gradient
    st.markdown(f"""
    <div style="text-align: center; padding: 3rem 0 2rem;">
        <div style="display:inline-block; padding:0.4rem 1rem; background:#eff6ff; border-radius:20px; color:#3b82f6; font-weight:700; font-size:0.8rem; margin-bottom:1rem; letter-spacing:0.05em;">REPORT GENERATOR</div>
        <h1 style="font-size: 2.5rem; font-weight: 900; color: #0f172a; margin: 0; letter-spacing: -0.03em; line-height:1.2;">
            주식회사 그룹디<br>
            <span style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">전략 보고서 생성기</span>
        </h1>
        <p style="font-size: 1rem; color: #64748b; margin-top: 1rem; font-weight:500;">
            {APP_CREATOR} <span style="color:#cbd5e1; margin:0 8px;">|</span> {APP_VERSION}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Step 1: Basic Info
    st.markdown("""
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:1rem;">
        <div style="width:28px; height:28px; background:#0f172a; color:white; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.9rem;">1</div>
        <div style="font-weight:700; color:#0f172a; font-size:1.1rem;">기본 정보 설정</div>
    </div>
    """, unsafe_allow_html=True)

    col_name, col_date = st.columns([3, 2])
    with col_name:
        clinic_name = st.text_input(
            "치과명",
            value=st.session_state.report_settings['clinic_name'],
            placeholder="예: 서울리멤버치과",
            key="main_clinic_name"
        )
        if clinic_name != st.session_state.report_settings['clinic_name']:
            st.session_state.report_settings['clinic_name'] = clinic_name
    with col_date:
        report_date = st.text_input(
            "작성일",
            value=st.session_state.report_settings['report_date'],
            key="main_report_date"
        )
        if report_date != st.session_state.report_settings['report_date']:
            st.session_state.report_settings['report_date'] = report_date

    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

    # Step 2: Upload
    st.markdown("""
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:1rem;">
        <div style="width:28px; height:28px; background:#3b82f6; color:white; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.9rem;">2</div>
        <div style="font-weight:700; color:#0f172a; font-size:1.1rem;">데이터 업로드</div>
    </div>
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:1rem; margin-bottom:1rem; display:flex; align-items:center; gap:12px;">
        <div style="width:40px; height:40px; background:#eff6ff; border-radius:8px; display:flex; align-items:center; justify-content:center; color:#3b82f6; font-size:1.2rem;">📂</div>
        <div>
            <div style="font-weight:600; color:#1e293b; font-size:0.9rem;">분석할 파일을 모두 선택하세요</div>
            <div style="font-size:0.8rem; color:#64748b;">예약, 블로그, 광고, 유튜브, 디자인 등 (파일명 기반 자동 분류)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # File uploader (label hidden, drop zone only)
    uploaded_files = st.file_uploader(
        "파일 업로드 (여러 카테고리의 폴더 전체를 올리시려면 ZIP 파일로 압축해서 1개만 올려주세요)",
        type=['xlsx', 'csv', 'zip'],
        accept_multiple_files=True,
        key="unified_upload",
        label_visibility="collapsed"
    )

    # Initialize accumulated files in session state if not present
    if "pending_uploads" not in st.session_state:
        st.session_state.pending_uploads = {}

    import zipfile
    import os

    # Process newly uploaded files into pending_uploads (to handle multiple subsequent uploads)
    if uploaded_files:
        for uf in uploaded_files:
            if uf.name.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(uf) as z:
                        for filename in z.namelist():
                            if filename.lower().endswith(('.csv', '.xlsx')) and not filename.startswith('__MACOSX'):
                                base_name = os.path.basename(filename)
                                if base_name:
                                    st.session_state.pending_uploads[base_name] = z.read(filename)
                except Exception as e:
                    st.error(f"ZIP 압축 해제 중 오류 발생: {e}")
            else:
                st.session_state.pending_uploads[uf.name] = uf.getvalue()

    # Classification preview + action button
    if st.session_state.pending_uploads:
        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
        
        # Classify files in real-time
        classification = {}
        unclassified = []
        for filename in st.session_state.pending_uploads.keys():
            category = classify_file(filename)
            if category:
                classification.setdefault(category, []).append(filename)
            else:
                unclassified.append(filename)

        # Show classification grid
        cols = st.columns(6)
        for idx, (cat_key, meta) in enumerate(CATEGORY_META.items()):
            with cols[idx]:
                file_count = len(classification.get(cat_key, []))
                # Active/Inactive styles
                if file_count > 0:
                    bg = f"{meta['color']}10" # 10% opacity
                    border = meta['color']
                    icon_color = meta['color']
                    opacity = "1"
                    scale = "transform: scale(1.05);"
                    shadow = f"box-shadow: 0 4px 12px {meta['color']}20;"
                else:
                    bg = "#f8fafc"
                    border = "#e2e8f0"
                    icon_color = "#cbd5e1"
                    opacity = "0.7"
                    scale = ""
                    shadow = ""
                    
                check = f'<span style="color:{icon_color}; font-size:1.2rem;">●</span>' if file_count > 0 else f'<span style="color:{icon_color};">○</span>'
                
                st.markdown(f"""
                <div style="background:{bg}; border:1.5px solid {border}; border-radius:12px;
                            padding:12px 6px; text-align:center; transition:all 0.2s; opacity:{opacity}; {scale} {shadow} height: 100%;">
                    <div style="margin-bottom:4px;">{check}</div>
                    <div style="font-size:0.75rem; color:{icon_color}; font-weight:700; margin-bottom:4px;">{meta['label']}</div>
                    <div style="font-size:0.7rem; color:#64748b;">{file_count}건</div>
                </div>
                """, unsafe_allow_html=True)

        # Unclassified files warning
        if unclassified:
            st.warning(f"⚠️ 분류 불가 파일 ({len(unclassified)}건): {', '.join(unclassified)}")

        # Action Button Area
        st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
        valid_count = len(st.session_state.pending_uploads) - len(unclassified)
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🗑️ 선택 초기화", use_container_width=True):
                st.session_state.pending_uploads = {}
                st.rerun()
                
        with col2:
            if valid_count > 0:
                if st.button(f"🚀  데이터 분석 시작 ({valid_count}개 파일)", type="primary", use_container_width=True):
                    process_uploaded_files(st.session_state.pending_uploads)
                    st.session_state.pending_uploads = {} # Clear after tracking
            else:
                st.button("분석할 파일이 없습니다.", disabled=True, use_container_width=True)



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


def render_unified_data_view(results=None):
    """Unified data view with inline editing capability per department."""
    if results is None:
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


def initialize_action_plan(results):
    """Auto-generate default action plan from data if not yet set."""
    if st.session_state.action_plan_items:
        return  # Already initialized

    from src.processors.summary import generate_summary
    summary = generate_summary(results)

    items = {}
    for ap in summary.get('action_plan', []):
        dept = ap.get('department', '')
        # Map department name to key
        dept_key = DEPT_LABEL_TO_KEY.get(dept)
        if not dept_key:
            for key, label, _ in ACTION_PLAN_TEAMS:
                if label == dept:
                    dept_key = key
                    break
        if dept_key:
            # Strip HTML tags for editable text
            import re
            agenda = re.sub(r'<[^>]+>', '', ap.get('agenda', ''))
            plan = ap.get('plan', '')
            text = f"{agenda}\n{plan}" if agenda else plan
            if dept_key not in items:
                items[dept_key] = []
            items[dept_key].append({'text': text})

    st.session_state.action_plan_items = items


def render_action_plan_editor(filtered_results):
    """Render editable action plan editor with +/- buttons per team and AI generation."""
    items = st.session_state.action_plan_items

    st.markdown("""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:20px 24px; margin-bottom:16px;">
            <p style="font-size:15px; font-weight:700; color:#1e293b; margin:0 0 4px 0;">실행 계획 편집</p>
            <p style="font-size:12px; color:#64748b; margin:0;">각 팀별 코멘트를 추가/수정/삭제할 수 있습니다. 변경 사항은 보고서에 바로 반영됩니다.</p>
        </div>
    """, unsafe_allow_html=True)

    changed = False

    for dept_key, dept_label, dept_color in ACTION_PLAN_TEAMS:
        # Team header with color indicator
        st.markdown(f"""
            <div style="display:flex; align-items:center; gap:8px; margin:16px 0 8px 0;">
                <span style="display:inline-block; width:4px; height:20px; background:{dept_color}; border-radius:2px;"></span>
                <span style="font-size:14px; font-weight:700; color:#1e293b;">{dept_label}</span>
                <span style="font-size:11px; color:#94a3b8;">({len(items.get(dept_key, []))}개)</span>
            </div>
        """, unsafe_allow_html=True)
        
        col_ai, col_empty = st.columns([1, 4])
        with col_ai:
            if st.button(f"✨ {dept_label} AI 업무 제안 생성", key=f"ai_gen_{dept_key}", use_container_width=True):
                with st.spinner(f"'{dept_label}' 맞춤형 업무를 분석 중입니다..."):
                    # Map new teams to KPIs from processed results
                    kpis = {}
                    prev_kpis = {}
                    if dept_key == 'marketing':
                        kpis = filtered_results.get('reservation', {}).get('kpi', {})
                        prev_kpis = filtered_results.get('reservation', {}).get('prev_month_data', {})
                    elif dept_key == 'content':
                        kpis = filtered_results.get('blog', {}).get('kpi', {})
                        prev_kpis = filtered_results.get('blog', {}).get('prev_month_data', {})
                    elif dept_key == 'ads':
                        kpis = filtered_results.get('ads', {}).get('kpi', {})
                        prev_kpis = filtered_results.get('ads', {}).get('prev_month_data', {})
                    elif dept_key == 'youtube':
                        kpis = filtered_results.get('youtube', {}).get('kpi', {})
                        prev_kpis = filtered_results.get('youtube', {}).get('prev_month_data', {})
                    elif dept_key == 'design':
                        kpis = filtered_results.get('design', {}).get('kpi', {})
                        prev_kpis = filtered_results.get('design', {}).get('prev_month_data', {})
                    
                    ai_result = generate_department_draft_and_strategy(dept_label, kpis, prev_kpis)
                    
                    # Update session state
                    if dept_key not in items:
                        items[dept_key] = []
                    
                    # Prepend draft
                    if "draft" in ai_result:
                        items[dept_key].insert(0, {'text': f"[AI 리뷰 총평]\n{ai_result['draft']}", 'is_ai': False, 'selected': True})
                    
                    # Append action plans as AI checklist proposals
                    for ap in ai_result.get("action_plan", []):
                        text_val = ap.get("text", "")
                        title_val = ap.get("title", "")
                        detail_val = ap.get("detail", "")
                        if not title_val and text_val:
                            lines = text_val.split('\n', 1)
                            title_val = lines[0]
                            detail_val = lines[1] if len(lines) > 1 else ""
                        
                        items[dept_key].append({
                            'text': f"{title_val}\n{detail_val}", 
                            'title': title_val, 
                            'detail': detail_val, 
                            'is_ai': True, 
                            'selected': False  # Default to False to allow PM to actively choose
                        })
                    
                    changed = True
                    st.rerun()

        team_items = items.get(dept_key, [])

        # Render existing items
        indices_to_remove = []
        for i, item in enumerate(team_items):
            if item.get('is_ai'):
                title = item.get('title', '')
                detail = item.get('detail', '')
                if not title:
                    lines = item.get('text', '').split('\n', 1)
                    title = lines[0] if lines else ''
                    detail = lines[1] if len(lines) > 1 else ''

                is_selected = item.get('selected', False)
                
                with st.container():
                    st.markdown("<hr style='margin: 8px 0px; border-color:#e2e8f0;'/>", unsafe_allow_html=True)
                    col_info, col_btn, col_del = st.columns([11, 2, 1])
                    with col_info:
                        if is_selected:
                            st.markdown(f"<div style='border-left: 4px solid {dept_color}; padding-left: 12px;'><strong>{title}</strong><br><span style='font-size:13px;color:#64748b;'>{detail}</span></div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='border-left: 4px solid #cbd5e1; padding-left: 12px;'><span style='color:#94a3b8; text-decoration:line-through;'><strong>{title}</strong><br>{detail}</span></div>", unsafe_allow_html=True)
                    with col_btn:
                        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
                        if is_selected:
                            if st.button("✓ 선택됨", key=f"btn_unsel_{dept_key}_{i}", help="클릭하여 제안 취소"):
                                item['selected'] = False
                                changed = True
                        else:
                            if st.button("선택", key=f"btn_sel_{dept_key}_{i}", type="primary", help="클릭하여 리포트에 제안 추가"):
                                item['selected'] = True
                                changed = True
                    with col_del:
                        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
                        if st.button("✕", key=f"ap_del_{dept_key}_{i}", help="삭제"):
                            indices_to_remove.append(i)
            else:
                # Normal Text Area UI
                col_text, col_del = st.columns([12, 1])
                with col_text:
                    new_text = st.text_area(
                        f"{dept_label} #{i+1}",
                        value=item['text'],
                        height=80,
                        key=f"ap_{dept_key}_{i}",
                        label_visibility="collapsed"
                    )
                    if new_text != item['text']:
                        item['text'] = new_text
                        changed = True
                with col_del:
                    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
                    if st.button("✕", key=f"ap_del_{dept_key}_{i}", help="삭제"):
                        indices_to_remove.append(i)

        # Remove deleted items (reverse to keep indices valid)
        if indices_to_remove:
            for idx in sorted(indices_to_remove, reverse=True):
                team_items.pop(idx)
            items[dept_key] = team_items
            st.rerun()

        # Add button
        if st.button(f"＋ {dept_label} 직접 코멘트 추가", key=f"ap_add_{dept_key}", type="secondary"):
            if dept_key not in items:
                items[dept_key] = []
            items[dept_key].append({'text': '', 'is_ai': False, 'selected': True})
            st.rerun()

    st.session_state.action_plan_items = items


def get_action_plan_for_report():
    """Convert session state action plan items to report format."""
    from src.processors.summary import get_next_month_seasonality
    season_info = get_next_month_seasonality()

    action_plan = []
    for dept_key, dept_label, _ in ACTION_PLAN_TEAMS:
        team_items = st.session_state.action_plan_items.get(dept_key, [])
        for item in team_items:
            # Skip unselected AI checklist items
            if item.get('is_ai') and not item.get('selected', True):
                continue
                
            text = item.get('text', '').strip()
            if not text:
                continue
            # Split first line as agenda, rest as plan
            lines = text.split('\n', 1)
            agenda = f"<strong>{lines[0].strip()}</strong>"
            plan = lines[1].strip() if len(lines) > 1 else ''
            action_plan.append({
                'department': dept_label,
                'agenda': agenda,
                'plan': plan
            })

    return {
        'action_plan': action_plan,
        'action_plan_month': f"{season_info['month']}월"
    }


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

    # Analysis selector (Step 3) - 분석 범위 선택
    if not st.session_state.get('selector_confirmed'):
        render_analysis_selector()
        return

    # Apply filtered results
    filtered_results = filter_results_by_selection()

    # Header with actions
    col_title, col_change, col_add, col_reset = st.columns([3, 1, 1, 1])
    with col_title:
        st.markdown(f"""
        <div style="margin-bottom: 0.25rem;">
            <h1 style="margin-bottom: 0; font-size: 1.5rem; color: #f1f5f9;">{settings['clinic_name']}</h1>
            <p style="color: #94a3b8; font-size: 0.8rem; margin-top: 2px;">{settings['report_date']} | 월간 마케팅 분석 보고서</p>
        </div>
        """, unsafe_allow_html=True)
    with col_change:
        if st.button("분석 변경", key="btn_change_analysis", use_container_width=True):
            st.session_state.selector_confirmed = False
            st.rerun()
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
            st.session_state.selector_confirmed = False
            st.session_state.selected_months = []
            st.session_state.selected_departments = []
            st.session_state.action_plan_items = {}
            st.session_state.ai_exec_summary = None
            st.rerun()

    # Data status indicator (shows selected vs available)
    results = filtered_results
    status_html = '<div style="display:flex; gap:12px; justify-content:center; padding:6px 0; margin-bottom:8px;">'
    for cat_key, meta in CATEGORY_META.items():
        has_data = bool(results.get(cat_key))
        has_original = bool(st.session_state.processed_results.get(cat_key))
        if has_data:
            dot_color = meta['color']
            dot_char = '&#9679;'
        elif has_original:
            dot_color = '#94a3b8'
            dot_char = '&#9675;'
        else:
            dot_color = '#334155'
            dot_char = '&#9675;'
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

    # Initialize action plan from data (auto-generate defaults)
    initialize_action_plan(filtered_results)

    # Initialize AI Executive Summary
    if 'ai_exec_summary' not in st.session_state:
        st.session_state.ai_exec_summary = None

    # Generate HTML report (filtered) with user-edited action plan
    custom_action_plan = get_action_plan_for_report()
    # AI 요약이 있으면 하단 '종합 분석 및 전략' 섹션에 포함
    if st.session_state.ai_exec_summary:
        custom_action_plan['content'] = st.session_state.ai_exec_summary
        custom_action_plan['title'] = 'AI 핵심 요약 & 실행 계획'
    html_report = generate_html_report(
        filtered_results,
        clinic_name=settings['clinic_name'],
        report_date=settings['report_date'],
        manager_comment=st.session_state.get('manager_comment', ''),
        action_plan_override=custom_action_plan,
        ai_exec_summary=st.session_state.ai_exec_summary
    )
    filename = get_report_filename(settings['clinic_name'])

    # Download button & AI Summary Generation button
    st.markdown("<div style='height: 0.25rem;'></div>", unsafe_allow_html=True)
    llm_ready = has_llm_client_configured()
    if not llm_ready:
        st.info("AI 요약은 Streamlit Secrets에 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 등록하면 활성화됩니다.")
    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
    with col2:
        if st.button(
            "✨ 팀장용 1분 AI 3줄 요약 자동생성",
            use_container_width=True,
            disabled=not llm_ready,
            help="ANTHROPIC_API_KEY 또는 OPENAI_API_KEY가 설정되어야 실행됩니다.",
        ):
            with st.spinner("전체 데이터를 분석하여 3줄 총평을 생성하는 중입니다..."):
                st.session_state.ai_exec_summary = generate_executive_summary(filtered_results)
            st.rerun()
    with col3:
        st.download_button(
            label="보고서 다운로드 (HTML)",
            data=html_report.encode('utf-8'),
            file_name=filename,
            mime="text/html",
            use_container_width=True
        )

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    # 3 Tabs: Preview / Data / Action Plan
    tab_preview, tab_data, tab_action = st.tabs(["보고서 미리보기", "데이터 확인 및 수정", "실행 계획 편집"])

    with tab_preview:
        render_html_preview(html_report)

    with tab_data:
        render_unified_data_view(filtered_results)

    with tab_action:
        render_action_plan_editor(filtered_results)

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


def render_intro():
    """Render intro animation on first visit — Professional Reveal + Neon 2.0 + Typing."""
    st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500&display=swap');

    #gd-intro-overlay {
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        z-index: 999999;
        background: #0f172a; /* Dark Navy Brand Color */
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-family: 'Montserrat', 'Pretendard', sans-serif;
        animation: gd-slideup 0.8s cubic-bezier(0.7, 0, 0.3, 1) 3.5s forwards; /* Extended duration for typing */
        pointer-events: all;
    }
    
    .intro-content {
        text-align: center;
        color: white;
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    
    .intro-logo {
        animation: gd-scale-in 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s backwards;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        font-size: 3.5rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        margin-bottom: 1.5rem;
    }
    
    .logo-text {
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 10px 30px rgba(59, 130, 246, 0.3);
    }

    /* Neon 2.0 Style */
    .neon-badge {
        font-size: 3.5rem;
        font-weight: 900;
        color: #fff;
        font-style: italic;
        text-shadow:
            0 0 7px #fff,
            0 0 10px #fff,
            0 0 21px #fff,
            0 0 42px #ec4899,
            0 0 82px #ec4899,
            0 0 92px #ec4899;
        animation: neon-flicker 2s infinite alternate;
        padding-right: 10px;
    }
    
    /* Typewriter Subtitle */
    .intro-sub-container {
        display: inline-block;
    }
    
    .intro-sub {
        font-family: 'Pretendard', sans-serif; /* Pretendard Font */
        font-size: 1.1rem; /* Slightly larger for Korean */
        font-weight: 600;
        color: #94a3b8;
        letter-spacing: 0.05em; /* Tighter for Korean */
        overflow: hidden; 
        border-right: 2px solid #3b82f6; 
        white-space: nowrap; 
        margin: 0 auto; 
        max-width: 0;
        animation: 
            typing 1.2s steps(10, end) 1s forwards, /* Adjusted steps for Korean length */
            blink-caret 0.75s step-end infinite;
        padding-right: 5px;
    }

    /* Animations */
    @keyframes gd-slideup {
        0% { transform: translateY(0); opacity: 1; pointer-events: all; }
        99% { transform: translateY(-100%); opacity: 1; pointer-events: none; }
        100% { transform: translateY(-100%); opacity: 0; pointer-events: none; visibility: hidden; }
    }
    
    @keyframes gd-scale-in {
        0% { opacity: 0; transform: scale(0.8) translateY(20px); }
        100% { opacity: 1; transform: scale(1) translateY(0); }
    }
    
    @keyframes typing {
        from { max-width: 0; }
        to { max-width: 100%; }
    }
    
    @keyframes blink-caret {
        from, to { border-color: transparent }
        50% { border-color: #3b82f6; box-shadow: 0 0 10px #3b82f6; }
    }

    @keyframes neon-flicker {
        0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% {
            text-shadow:
                0 0 4px #fff,
                0 0 10px #fff,
                0 0 18px #fff,
                0 0 38px #ec4899,
                0 0 73px #ec4899;
            opacity: 1;
        }
        20%, 24%, 55% {
            text-shadow: none;
            opacity: 0.8;
        }
    }
    </style>
    
    <div id="gd-intro-overlay">
        <div class="intro-content">
            <div class="intro-logo">
                <span class="logo-text">GROUP D</span>
                <span class="neon-badge">2.0</span>
            </div>
            <div class="intro-sub-container">
                <div class="intro-sub">전략 보고서 시스템</div>
            </div>
        </div>
    </div>
    
    <script>
        // Force cleanup - Adjusted timeout for typing animation
        setTimeout(function() {
            const overlay = document.getElementById('gd-intro-overlay');
            if (overlay) {
                overlay.style.display = 'none';
                overlay.remove();
            }
        }, 4000); // reduced timeout slightly as korean is shorter
    </script>
    """, unsafe_allow_html=True)


def render_mode_switcher():
    """Render mode selection toggle at the top of the app."""
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        st.markdown("""
        <style>
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"] .mode-switcher) {
            margin-bottom: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        mode_labels = {"marketing": "마케팅 리포트", "feedback": "고객 피드백 분석"}
        selected = st.radio(
            "모드 선택",
            options=list(mode_labels.keys()),
            format_func=lambda x: mode_labels[x],
            horizontal=True,
            key="mode_radio",
            label_visibility="collapsed"
        )

        if selected != st.session_state.app_mode:
            st.session_state.app_mode = selected
            st.rerun()


def render_feedback_upload():
    """Render the feedback mode upload page."""
    import pandas as pd

    st.markdown(f"""
    <div style="text-align: center; padding: 2.5rem 0 1.5rem;">
        <div style="display:inline-block; padding:0.35rem 0.9rem; background:#fef3c7;
                    border-radius:20px; color:#d97706; font-weight:700; font-size:0.75rem;
                    margin-bottom:0.8rem; letter-spacing:0.05em;">
            FEEDBACK ANALYSIS
        </div>
        <h1 style="font-size: 2rem; font-weight: 900; color: #f1f5f9; margin: 0;
                    letter-spacing: -0.03em; line-height:1.3;">
            고객 피드백<br>
            <span style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                         -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                분석 리포트
            </span>
        </h1>
        <p style="font-size: 0.85rem; color: #64748b; margin-top: 0.8rem; font-weight:500;">
            {APP_CREATOR} <span style="color:#cbd5e1; margin:0 8px;">|</span> {APP_VERSION}
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:12px;
                padding:1rem; margin-bottom:1rem;">
        <div style="font-weight:600; color:#92400e; font-size:0.85rem; margin-bottom:4px;">
            설문/피드백 파일을 업로드하세요
        </div>
        <div style="font-size:0.78rem; color:#a16207;">
            xlsx 또는 csv 형식 지원. 1행이 컬럼 헤더로 사용되며, 컬럼 유형(점수, 객관식, 주관식 등)은 자동 감지됩니다.
        </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "피드백 파일 업로드",
        type=['xlsx', 'csv'],
        accept_multiple_files=False,
        key="feedback_upload",
        label_visibility="collapsed"
    )

    if uploaded:
        # Quick preview
        try:
            raw = uploaded.read()
            uploaded.seek(0)
            from io import BytesIO
            if uploaded.name.endswith('.xlsx') or uploaded.name.endswith('.xls'):
                preview_df = pd.read_excel(BytesIO(raw))
            else:
                preview_df = pd.read_csv(BytesIO(raw), encoding='utf-8-sig')

            st.markdown(f"**감지된 컬럼 ({len(preview_df.columns)}개):**")
            cols_html = '<div style="display:flex; flex-wrap:wrap; gap:4px; margin-bottom:12px;">'
            for col in preview_df.columns:
                cols_html += f'<span style="padding:2px 8px; background:#f1f5f9; border:1px solid #e2e8f0; border-radius:6px; font-size:11px; color:#475569;">{col[:30]}</span>'
            cols_html += '</div>'
            st.markdown(cols_html, unsafe_allow_html=True)

            st.markdown(f"**데이터 미리보기** ({len(preview_df)}행)")
            st.dataframe(preview_df.head(5), use_container_width=True, height=200)
        except Exception:
            st.info("파일을 읽는 중 미리보기를 표시할 수 없습니다. 분석은 정상 진행됩니다.")

        if st.button("파일 업로드", type="primary", use_container_width=True):
            loaded = load_uploaded_file(uploaded)
            from src.processors.feedback import load_feedback_file, detect_months
            raw_df = load_feedback_file(loaded)
            if raw_df is None or len(raw_df) == 0:
                st.error("유효한 피드백 데이터를 찾을 수 없습니다.")
            else:
                months = detect_months(raw_df)
                st.session_state.feedback_raw_df = raw_df
                st.session_state.feedback_available_months = months
                st.session_state.feedback_selected_months = months  # 기본: 전체 선택
                st.session_state.feedback_month_confirmed = False
                st.session_state.feedback_file_uploaded = True
                st.session_state.feedback_result = None
                st.rerun()


def render_feedback_month_selector():
    """Render month selector for feedback mode."""
    import pandas as pd

    available_months = st.session_state.feedback_available_months

    if not available_months:
        # 타임스탬프 컬럼이 없으면 바로 분석 진행
        st.session_state.feedback_month_confirmed = True
        raw_df = st.session_state.feedback_raw_df
        with st.spinner("피드백 데이터 분석 중..."):
            result = process_feedback([], df_override=raw_df)
        st.session_state.feedback_result = result
        st.rerun()
        return

    st.markdown("""
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:20px 24px; margin:16px 0;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
            <div style="width:28px; height:28px; background:#f59e0b; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-weight:800; font-size:13px;">2</div>
            <div>
                <p style="font-size:14px; font-weight:700; color:#1e293b; margin:0;">분석 기간 선택</p>
                <p style="font-size:11px; color:#64748b; margin:0;">원하는 월을 선택하세요. 선택한 월의 응답만 분석됩니다.</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Month labels
    def format_month(ym):
        try:
            parts = ym.split('-')
            return f"{parts[0]}년 {int(parts[1])}월"
        except Exception:
            return ym

    month_labels = [format_month(m) for m in available_months]

    selected_labels = st.multiselect(
        "분석할 월 선택",
        options=month_labels,
        default=month_labels,
        key="fb_month_select"
    )

    # Map labels back to YYYY-MM
    label_to_ym = dict(zip(month_labels, available_months))
    selected_months = [label_to_ym[l] for l in selected_labels if l in label_to_ym]

    # Show count per month
    raw_df = st.session_state.feedback_raw_df
    if raw_df is not None:
        from src.processors.feedback import classify_column
        for col in raw_df.columns:
            if classify_column(raw_df[col], col) == 'timestamp':
                try:
                    dt_series = pd.to_datetime(raw_df[col], errors='coerce')
                    month_counts = dt_series.dt.strftime('%Y-%m').value_counts().sort_index()
                    counts_html = '<div style="display:flex; flex-wrap:wrap; gap:8px; margin:8px 0;">'
                    for ym in available_months:
                        cnt = month_counts.get(ym, 0)
                        is_selected = ym in selected_months
                        bg = '#fef3c7' if is_selected else '#f1f5f9'
                        border = '#f59e0b' if is_selected else '#e2e8f0'
                        color = '#92400e' if is_selected else '#94a3b8'
                        counts_html += f'<span style="padding:4px 12px; background:{bg}; border:1px solid {border}; border-radius:8px; font-size:12px; color:{color}; font-weight:600;">{format_month(ym)}: {cnt}건</span>'
                    counts_html += '</div>'
                    st.markdown(counts_html, unsafe_allow_html=True)
                except Exception:
                    pass
                break

    if not selected_months:
        st.warning("최소 1개 월을 선택하세요.")
        return

    if st.button("분석 시작", type="primary", use_container_width=True):
        from src.processors.feedback import filter_df_by_months
        filtered_df = filter_df_by_months(raw_df, selected_months)
        st.session_state.feedback_selected_months = selected_months
        st.session_state.feedback_month_confirmed = True
        with st.spinner("피드백 데이터 분석 중..."):
            result = process_feedback([], df_override=filtered_df)
        st.session_state.feedback_result = result
        st.rerun()


def render_feedback_dashboard():
    """Render the feedback analysis dashboard."""
    import pandas as pd

    # Month selector step
    if not st.session_state.feedback_month_confirmed:
        render_feedback_month_selector()
        return

    result = st.session_state.feedback_result
    if not result:
        st.warning("분석 결과가 없습니다.")
        return

    overview = result.get('overview', {})

    # Selected months label
    selected = st.session_state.feedback_selected_months
    available = st.session_state.feedback_available_months
    if selected and available and len(selected) < len(available):
        def fmt(ym):
            try:
                parts = ym.split('-')
                return f"{int(parts[1])}월"
            except Exception:
                return ym
        month_label = ', '.join([fmt(m) for m in selected])
    else:
        month_label = '전체'

    # Header
    col_title, col_month, col_reset = st.columns([3, 1, 1])
    with col_title:
        st.markdown(f"""
        <div style="margin-bottom: 0.25rem;">
            <h1 style="margin-bottom: 0; font-size: 1.4rem; color: #f1f5f9;">고객 피드백 분석 결과</h1>
            <p style="color: #94a3b8; font-size: 0.78rem; margin-top: 2px;">
                응답 {overview.get('response_count', 0)}건 ({month_label})
                {(' | ' + overview.get('date_range', '')) if overview.get('date_range') else ''}
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col_month:
        if st.button("기간 변경", key="fb_change_month", use_container_width=True):
            st.session_state.feedback_month_confirmed = False
            st.session_state.feedback_result = None
            st.rerun()
    with col_reset:
        if st.button("새로 시작", key="fb_reset", use_container_width=True):
            st.session_state.feedback_file_uploaded = False
            st.session_state.feedback_result = None
            st.session_state.feedback_raw_df = None
            st.session_state.feedback_available_months = []
            st.session_state.feedback_selected_months = []
            st.session_state.feedback_month_confirmed = False
            st.rerun()

    # Generate HTML report
    html_report = generate_feedback_html_report(result)
    filename = get_feedback_report_filename()

    # Download button
    st.markdown("<div style='height: 0.25rem;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.download_button(
            label="피드백 보고서 다운로드 (HTML)",
            data=html_report.encode('utf-8'),
            file_name=filename,
            mime="text/html",
            use_container_width=True
        )

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    # 3 Tabs
    tab_preview, tab_dashboard, tab_detail = st.tabs([
        "보고서 미리보기", "대시보드", "응답자별 상세"
    ])

    with tab_preview:
        render_html_preview(html_report)

    with tab_dashboard:
        render_feedback_streamlit_view(result)

    with tab_detail:
        render_respondent_detail_view(result)


def render_feedback_streamlit_view(result: dict):
    """Render interactive feedback analysis in Streamlit."""
    import pandas as pd

    columns = result.get('columns', [])
    overview = result.get('overview', {})

    # Overview metrics
    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("총 응답 수", f"{overview.get('response_count', 0)}건")
    with metric_cols[1]:
        avg_sat = overview.get('avg_satisfaction', 0)
        st.metric("전체 평균 만족도", f"{avg_sat}점" if avg_sat > 0 else "-")
    with metric_cols[2]:
        st.metric("분석 컬럼 수", f"{overview.get('column_count', 0)}개")

    # Score analysis
    score_data = result.get('score_analysis', {})
    if score_data:
        st.markdown("### 영역별 만족도")
        for col_name, data in score_data.items():
            label = data.get('short_label', col_name[:30])
            mean = data.get('mean', 0)
            color = '#ef4444' if mean < 3 else '#f59e0b' if mean < 4 else '#10b981'

            col_label, col_bar, col_score = st.columns([2, 5, 1])
            with col_label:
                st.markdown(f"**{label}**")
            with col_bar:
                st.progress(min(mean / 5.0, 1.0))
            with col_score:
                st.markdown(f"<span style='font-weight:800; color:{color};'>{mean}점</span>", unsafe_allow_html=True)

    # Multi-select analysis
    ms_data = result.get('multiselect_analysis', {})
    if ms_data:
        for col_name, data in ms_data.items():
            st.markdown(f"### 객관식 분석")
            st.caption(col_name)
            for opt in data.get('options', [])[:10]:
                col_opt, col_cnt = st.columns([5, 1])
                with col_opt:
                    st.markdown(f"- {opt['label']}")
                with col_cnt:
                    st.markdown(f"**{opt['count']}건** ({opt['pct']}%)")

    # Single-select analysis
    ss_data = result.get('singleselect_analysis', {})
    if ss_data:
        for col_name, data in ss_data.items():
            st.markdown(f"### 응답 분포")
            st.caption(col_name)
            vals = data.get('values', [])
            if vals:
                chart_df = pd.DataFrame(vals)
                st.bar_chart(chart_df.set_index('label')['count'])

    # Free text analysis
    ft_data = result.get('freetext_analysis', {})
    if ft_data:
        st.markdown("### 주관식 응답 요약")
        for col_name, data in ft_data.items():
            with st.expander(f"{col_name} ({data.get('response_count', 0)}건)"):
                keywords = data.get('top_keywords', [])
                if keywords:
                    kw_html = '<div style="display:flex; flex-wrap:wrap; gap:4px; margin-bottom:12px;">'
                    for kw in keywords[:12]:
                        kw_html += f'<span style="padding:2px 8px; background:#f1f5f9; border:1px solid #e2e8f0; border-radius:6px; font-size:12px;">{kw["word"]} <span style="color:#94a3b8;">{kw["count"]}</span></span>'
                    kw_html += '</div>'
                    st.markdown(kw_html, unsafe_allow_html=True)

                st.markdown("**대표 응답:**")
                for sample in data.get('samples', [])[:5]:
                    st.markdown(f"> {sample}")

    # Recommendations
    recs = result.get('recommendations', [])
    if recs:
        st.markdown("### 개선 제안")
        for rec in recs:
            st.info(rec)


def render_respondent_detail_view(result: dict):
    """Render per-respondent detail view."""
    import pandas as pd

    details = result.get('respondent_details', [])
    columns = result.get('columns', [])
    id_col_name = result.get('overview', {}).get('identifier_col', '')

    if not details:
        st.info("응답자 데이터가 없습니다.")
        return

    for i, row in enumerate(details):
        label = str(row.get(id_col_name, f"응답자 {i+1}")) if id_col_name else f"응답자 {i+1}"
        if label.lower() == 'nan' or not label.strip():
            label = f"응답자 {i+1}"

        with st.expander(f"{label}"):
            for col_info in columns:
                col_name = col_info['name']
                value = row.get(col_name, '')
                val_str = str(value).strip()
                if val_str and val_str.lower() not in ('nan', 'nat', 'none', ''):
                    st.markdown(f"**{col_name}:** {val_str}")


# --- Product suggestion checklist overrides (v2) ---
PRODUCT_KPI_LABEL_MAP = {
    "total_reservations": "총 예약수",
    "new_reservations": "신규 예약수",
    "cancel_count": "취소 건수",
    "cancel_rate": "취소율",
    "cpa": "CPA",
    "roas": "ROAS",
    "ctr": "CTR",
    "cvr": "CVR",
    "ad_spend": "광고비",
    "impressions": "노출수",
    "clicks": "클릭수",
    "views": "조회수",
    "total_views": "총 조회수",
    "views_mom_growth": "조회수 증감률",
    "publish_completion_rate": "발행 완료율",
    "published_count": "발행 수",
    "contract_count": "계약 수",
}


PRODUCT_TEMPLATES = {
    "marketing": [
        ("예약 이탈 방지 패키지", "예약 1일/3일 전 리마인드와 취소 사유 대응 스크립트를 적용합니다. {metric_hint}"),
        ("재예약 전환 패키지", "내원 후 7일/14일 후속 메시지와 상담 멘트를 표준화합니다. {metric_hint}"),
        ("신규 문의 응대 패키지", "첫 문의 10분 내 응대 기준과 상담 체크리스트를 운영합니다. {metric_hint}"),
        ("휴면 고객 재활성 패키지", "최근 미내원 고객 대상 재방문 혜택/문구 A/B를 실행합니다. {metric_hint}"),
        ("접수 스크립트 개선 패키지", "전화/채팅 문의에서 예약 전환률을 높이는 스크립트를 배포합니다. {metric_hint}"),
    ],
    "design": [
        ("시즌 프로모션 목업 디자인 2건", "다음 시즌 키비주얼 기반으로 원내/외 노출용 목업 2종을 제작합니다. {metric_hint}"),
        ("원내 POP/배너 디자인 3건", "대기실, 카운터, 상담실 동선 기준의 안내물 3종을 제작합니다. {metric_hint}"),
        ("콘텐츠 썸네일 템플릿 5종", "블로그/영상 공통 톤의 템플릿 세트를 제작해 제작 속도를 개선합니다. {metric_hint}"),
        ("이벤트 랜딩 비주얼 2종", "전환형 랜딩 상단 비주얼 2안을 제작해 A/B 테스트합니다. {metric_hint}"),
        ("리뷰/후기 카드뉴스 템플릿 6종", "실제 사례 기반 카드형 템플릿 6종을 제작합니다. {metric_hint}"),
    ],
    "youtube": [
        ("숏폼 영상 패키지 4편", "핵심 진료/FAQ 중심 숏폼 4편을 월간 편성으로 제작합니다. {metric_hint}"),
        ("원장 코멘트 영상 2편", "신뢰도 강화를 위한 전문 코멘트 영상 2편을 제작합니다. {metric_hint}"),
        ("블로그 재가공 영상 패키지 3편", "기존 상위 블로그를 영상으로 전환해 채널 효율을 높입니다. {metric_hint}"),
        ("전환형 CTA 영상 2편", "상담/예약 유도 문구 중심의 엔드카드 영상 2편을 제작합니다. {metric_hint}"),
        ("시리즈형 교육 콘텐츠 3편", "연속 시청 유도를 위한 시리즈 구조 콘텐츠 3편을 기획합니다. {metric_hint}"),
    ],
    "strategy": [
        ("월간 통합 KPI 리뷰 리포트", "팀별 핵심 KPI와 이슈를 한 페이지로 정리해 주간 점검에 사용합니다. {metric_hint}"),
        ("원소스 멀티유즈 실행안", "블로그-영상-광고 소재를 연결한 공통 실행 프로세스를 정의합니다. {metric_hint}"),
        ("우선순위 매트릭스 운영안", "효과/난이도 기준으로 과제를 분류해 실행 순서를 고정합니다. {metric_hint}"),
        ("월간 실험 로드맵 3안", "A/B 테스트 주제와 성공 기준을 월 단위로 명시합니다. {metric_hint}"),
        ("팀장 승인용 원페이지 보고서", "의사결정에 필요한 지표/리스크/다음 액션을 1페이지로 표준화합니다. {metric_hint}"),
    ],
    "ads": [
        ("검색광고 키워드 재구성 패키지", "전환 중심 키워드로 캠페인을 재구성하고 비효율 키워드를 정리합니다. {metric_hint}"),
        ("광고 소재 A/B 테스트 4종", "카피/비주얼 조합 4종을 테스트해 성과 상위 소재를 확정합니다. {metric_hint}"),
        ("리타겟팅 캠페인 패키지", "사이트 방문/상담 이탈 고객 대상 리타겟팅 시나리오를 운영합니다. {metric_hint}"),
        ("전환추적/태그 점검 패키지", "핵심 전환 이벤트의 태깅 누락을 점검해 지표 신뢰도를 확보합니다. {metric_hint}"),
        ("예산 배분 최적화 3안", "채널별 성과 기반으로 월간 예산 배분 시나리오 3안을 제공합니다. {metric_hint}"),
    ],
    "content": [
        ("블로그 기획 패키지 4편", "수요 높은 키워드 중심으로 월간 블로그 4편을 고정 편성합니다. {metric_hint}"),
        ("사례형 콘텐츠 패키지 2편", "실제 케이스 기반의 전/후 스토리형 콘텐츠 2편을 발행합니다. {metric_hint}"),
        ("검색형 FAQ 콘텐츠 3편", "문의 빈도가 높은 질문을 검색형 콘텐츠 3편으로 전환합니다. {metric_hint}"),
        ("랜딩 연계 상세 포스트 2건", "광고 랜딩과 직접 연결되는 설명형 포스트 2건을 제작합니다. {metric_hint}"),
        ("월간 콘텐츠 캘린더 세트", "키워드/발행일/채널을 통합한 실행 캘린더를 운영합니다. {metric_hint}"),
    ],
}


def _product_safe_float(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.replace(",", "").replace("%", "").strip()
        if not text:
            return None
        try:
            return float(text)
        except Exception:
            return None
    return None


def _product_kpi_label(key: str) -> str:
    return PRODUCT_KPI_LABEL_MAP.get(key, key.replace("_", " "))


def _product_kpi_value(key: str, value: float) -> str:
    lower = key.lower()
    if any(token in lower for token in ("rate", "ratio", "growth", "ctr", "cvr", "roas")):
        return f"{value:.1f}%"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:.1f}" if value != int(value) else f"{int(value)}"


def _product_kpi_for_team(results, dept_key: str):
    source_map = {
        "marketing": "reservation",
        "content": "blog",
        "youtube": "youtube",
        "design": "design",
        "ads": "ads",
    }
    source = source_map.get(dept_key)
    if source:
        return (results.get(source, {}) if results else {}).get("kpi", {})

    if dept_key == "strategy":
        merged = {}
        for source in ("reservation", "blog", "youtube", "design", "ads"):
            kpi = (results.get(source, {}) if results else {}).get("kpi", {})
            if not isinstance(kpi, dict):
                continue
            for key, value in kpi.items():
                if str(key).startswith("prev_"):
                    continue
                numeric = _product_safe_float(value)
                if numeric is not None:
                    merged[f"{source}_{key}"] = numeric
        return merged

    return {}


def _product_metric_hint(kpis: dict) -> str:
    if not isinstance(kpis, dict):
        return "현재 업로드된 분석 데이터를 기준으로 우선순위를 설정합니다."

    candidates = []
    for key, value in kpis.items():
        if str(key).startswith("prev_"):
            continue
        numeric = _product_safe_float(value)
        if numeric is not None:
            candidates.append((key, numeric))

    if not candidates:
        return "현재 업로드된 분석 데이터를 기준으로 우선순위를 설정합니다."

    top = sorted(candidates, key=lambda x: abs(x[1]), reverse=True)[:2]
    pairs = [f"{_product_kpi_label(k)} {_product_kpi_value(k, v)}" for k, v in top]
    return "핵심 지표: " + ", ".join(pairs)


def _product_items_for_team(results, dept_key: str, dept_label: str):
    metric_hint = _product_metric_hint(_product_kpi_for_team(results, dept_key))
    templates = PRODUCT_TEMPLATES.get(dept_key, [])
    return [
        {
            "title": title,
            "detail": detail.format(metric_hint=metric_hint),
            "selected": True,
            "source": "auto",
            "team": dept_label,
        }
        for title, detail in templates[:5]
    ]


def _normalize_product_items(raw_items):
    normalized = {}
    for dept_key, _, _ in ACTION_PLAN_TEAMS:
        team_items = raw_items.get(dept_key, []) if isinstance(raw_items, dict) else []
        out = []
        for item in team_items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            detail = str(item.get("detail", "")).strip()
            if not title:
                legacy_text = str(item.get("text", "")).strip()
                if legacy_text:
                    lines = legacy_text.split("\n", 1)
                    title = lines[0].strip()
                    if not detail and len(lines) > 1:
                        detail = lines[1].strip()
            if not title and not detail:
                continue
            out.append({
                "title": title,
                "detail": detail,
                "selected": bool(item.get("selected", True)),
                "source": item.get("source", "manual"),
                "price": item.get("price", 0),
                "mode_type": item.get("mode_type", ""),
            })
        normalized[dept_key] = out
    return normalized


def _fill_defaults_for_team(results, dept_key: str, dept_label: str, existing_items: list):
    items = list(existing_items)
    defaults = _product_items_for_team(results, dept_key, dept_label)
    seen = {str(x.get("title", "")).strip() for x in items}
    for candidate in defaults:
        if len(items) >= 5:
            break
        title = str(candidate.get("title", "")).strip()
        if title in seen:
            continue
        items.append(candidate)
        seen.add(title)
    return items


def initialize_action_plan(results):
    """팀별 상품 제안 5개 체크리스트를 초기화합니다."""
    current = st.session_state.action_plan_items if isinstance(st.session_state.action_plan_items, dict) else {}
    if current:
        st.session_state.action_plan_items = _normalize_product_items(current)
        return

    initialized = {}
    for dept_key, dept_label, _ in ACTION_PLAN_TEAMS:
        initialized[dept_key] = _product_items_for_team(results, dept_key, dept_label)
    st.session_state.action_plan_items = initialized


def render_action_plan_editor(filtered_results):
    """팀별 상품 제안을 체크/수정/추가하는 편집 UI."""
    items = _normalize_product_items(st.session_state.action_plan_items)
    changed = False

    st.markdown("""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:20px 24px; margin-bottom:16px;">
            <p style="font-size:15px; font-weight:700; color:#1e293b; margin:0 0 4px 0;">실행 상품 제안 편집</p>
            <p style="font-size:12px; color:#64748b; margin:0;">
                팀별 분석 기반 상품 제안 5개가 자동 생성됩니다. 체크/해제, 내용 수정, 신규 추가 후 보고서에 반영할 수 있습니다.
            </p>
        </div>
    """, unsafe_allow_html=True)

    for dept_key, dept_label, dept_color in ACTION_PLAN_TEAMS:
        team_items = items.get(dept_key, [])
        selected_count = sum(1 for x in team_items if x.get("selected", True))

        st.markdown(f"""
            <div style="display:flex; align-items:center; gap:8px; margin:18px 0 8px 0;">
                <span style="display:inline-block; width:4px; height:20px; background:{dept_color}; border-radius:2px;"></span>
                <span style="font-size:14px; font-weight:700; color:#1e293b;">{dept_label}</span>
                <span style="font-size:11px; color:#94a3b8;">({selected_count}/{len(team_items)} 선택)</span>
            </div>
        """, unsafe_allow_html=True)

        col_regen, col_add = st.columns([2, 1])
        with col_regen:
            if st.button(f"{dept_label} 상품 5개 자동 재생성", key=f"ap_v2_regen_{dept_key}", use_container_width=True):
                items[dept_key] = _product_items_for_team(filtered_results, dept_key, dept_label)
                st.session_state.action_plan_items = items
                st.rerun()
        with col_add:
            if st.button(f"+ {dept_label} 직접 추가", key=f"ap_v2_add_{dept_key}", use_container_width=True):
                items.setdefault(dept_key, []).append({
                    "title": "",
                    "detail": "",
                    "selected": True,
                    "source": "manual",
                })
                st.session_state.action_plan_items = items
                st.rerun()

        remove_idx = []
        for i, item in enumerate(team_items):
            row_key = f"{dept_key}_{i}"
            col_sel, col_body, col_del = st.columns([1.2, 10, 1])
            with col_sel:
                selected = st.checkbox(
                    "선택",
                    value=item.get("selected", True),
                    key=f"ap_v2_selected_{row_key}",
                    label_visibility="collapsed",
                )
            with col_body:
                title = st.text_input(
                    f"{dept_label} 상품명 {i+1}",
                    value=item.get("title", ""),
                    key=f"ap_v2_title_{row_key}",
                    placeholder="예: 시즌 프로모션 목업 디자인 2건",
                    label_visibility="collapsed",
                )
                detail = st.text_area(
                    f"{dept_label} 설명 {i+1}",
                    value=item.get("detail", ""),
                    key=f"ap_v2_detail_{row_key}",
                    height=68,
                    placeholder="선택 이유 / 실행 기준 / 기대 효과",
                    label_visibility="collapsed",
                )
            with col_del:
                st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
                if st.button("삭제", key=f"ap_v2_del_{row_key}", help="해당 제안 삭제"):
                    remove_idx.append(i)

            if selected != item.get("selected", True):
                item["selected"] = selected
                changed = True
            if title != item.get("title", ""):
                item["title"] = title
                changed = True
            if detail != item.get("detail", ""):
                item["detail"] = detail
                changed = True

        if remove_idx:
            for idx in sorted(remove_idx, reverse=True):
                team_items.pop(idx)
            items[dept_key] = team_items
            st.session_state.action_plan_items = items
            st.rerun()

        st.markdown("<div style='height: 0.35rem;'></div>", unsafe_allow_html=True)

    if changed:
        st.session_state.action_plan_items = items


def get_action_plan_for_report():
    """선택된 상품 제안을 보고서 action_plan 형식으로 변환합니다."""
    from src.processors.summary import get_next_month_seasonality
    season_info = get_next_month_seasonality()

    items = _normalize_product_items(st.session_state.action_plan_items)
    st.session_state.action_plan_items = items

    action_plan = []
    for dept_key, dept_label, _ in ACTION_PLAN_TEAMS:
        for item in items.get(dept_key, []):
            if not item.get("selected", True):
                continue
            title = str(item.get("title", "")).strip()
            detail = str(item.get("detail", "")).strip()
            if not title:
                continue
            action_plan.append({
                "department": dept_label,
                "agenda": f"<strong>{title}</strong>",
                "plan": detail,
            })

    return {
        "action_plan": action_plan,
        "action_plan_month": f"{season_info['month']}월",
    }


def _extract_blog_contract_count(results: dict) -> float:
    """Extract blog contract count from current filtered report results."""
    blog = (results or {}).get("blog", {})

    kpi = blog.get("kpi", {})
    value = _product_safe_float(kpi.get("contract_count"))
    if value is not None:
        return max(value, 0.0)

    curr_work = blog.get("current_month_data", {}).get("work", {})
    value = _product_safe_float(curr_work.get("contract_count"))
    if value is not None:
        return max(value, 0.0)

    monthly = blog.get("clean_data", {}).get("work", {}).get("monthly_summary", [])
    if monthly and isinstance(monthly, list):
        last = monthly[-1]
        if isinstance(last, dict):
            value = _product_safe_float(last.get("contract_count"))
            if value is not None:
                return max(value, 0.0)
    return 0.0


def _find_replacement_catalog_path():
    """Locate replacement catalog xlsx in Downloads."""
    from pathlib import Path

    explicit = os.environ.get("REPLACEMENT_PLAN_XLSX")
    if explicit and os.path.exists(explicit):
        return explicit

    candidates = []
    downloads = Path.home() / "Downloads"
    if downloads.exists():
        candidates.extend(downloads.glob("*대체상품*액션플랜*.xlsx"))
    local_download = Path.cwd() / "downloads"
    if local_download.exists():
        candidates.extend(local_download.glob("*대체상품*액션플랜*.xlsx"))

    valid = [f for f in candidates if not f.name.startswith("~$")]
    if not valid:
        return None

    valid.sort(key=lambda path: (path.stat().st_mtime, path.name))
    return str(valid[-1])


@st.cache_data(show_spinner=False)
def _load_replacement_catalog_rows(path: str, mtime: float):
    """Read and normalize replacement catalog rows from xlsx."""
    import pandas as pd

    del mtime  # cache key only

    raw = pd.read_excel(path, sheet_name=0, header=2)
    if raw.empty:
        return []

    df = raw.iloc[:, 0:11].copy()
    df.columns = [
        "type",
        "category",
        "item",
        "owner_dept",
        "status",
        "executor",
        "cost_excl_labor",
        "price_vat_excl",
        "posting_ratio",
        "replacement_per_posting",
        "note",
    ]

    for col in ["type", "category", "item", "owner_dept", "status", "executor", "note"]:
        df[col] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})

    for col in ["type", "category", "owner_dept"]:
        df[col] = df[col].replace("", pd.NA).ffill().fillna("")

    df["owner_dept"] = (
        df["owner_dept"]
        .str.replace(r"\s*,\s*", ", ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    for col in ["posting_ratio", "replacement_per_posting", "cost_excl_labor", "price_vat_excl"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[df["replacement_per_posting"].notna()].copy()
    df = df[df["item"].astype(str).str.strip() != ""].copy()
    return df.to_dict("records")


def _get_replacement_catalog_rows():
    path = _find_replacement_catalog_path()
    if not path or not os.path.exists(path):
        return []
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = 0.0
    return _load_replacement_catalog_rows(path, mtime)


def _owner_tokens(owner_dept: str):
    return [x.strip() for x in str(owner_dept or "").split(",") if x.strip()]


def _catalog_candidates_for_team(rows: list, dept_key: str, blog_contract_count: float):
    if not rows:
        return []

    def is_match(row):
        owner = _owner_tokens(row.get("owner_dept", ""))
        category = str(row.get("category", ""))
        item = str(row.get("item", ""))

        if dept_key == "strategy":
            return True
        if dept_key == "marketing":
            return "마케팅팀" in owner
        if dept_key == "design":
            return "디자인팀" in owner
        if dept_key == "content":
            return ("콘텐츠팀" in owner) or ("블로그" in category) or ("블로그" in item)
        if dept_key == "youtube":
            return ("영상팀" in owner) or ("영상" in category) or ("영상" in item)
        if dept_key == "ads":
            return ("광고" in category) or ("광고" in item) or ("마케팅팀" in owner)
        return False

    out = []
    for row in rows:
        if not is_match(row):
            continue
        rpp = _product_safe_float(row.get("replacement_per_posting"))
        if rpp is None:
            continue
        needed = float(blog_contract_count) * float(rpp)
        out.append(
            {
                "category": str(row.get("category", "")).strip(),
                "item": str(row.get("item", "")).strip(),
                "owner_dept": str(row.get("owner_dept", "")).strip(),
                "status": str(row.get("status", "")).strip(),
                "executor": str(row.get("executor", "")).strip(),
                "replacement_per_posting": float(rpp),
                "estimated_needed_count": float(needed),
                "note": str(row.get("note", "")).strip(),
            }
        )
    return out


def _compact_kpi_context(results: dict):
    context = {}
    for key, value in (results or {}).items():
        if not isinstance(value, dict) or not value:
            continue
        context[key] = {
            "kpi": value.get("kpi", {}),
            "month": value.get("month"),
            "prev_month": value.get("prev_month"),
        }
    return context


def _fallback_product_items_from_catalog(candidates: list, dept_label: str, max_items: int = 5):
    if not candidates:
        return []

    status_rank = {"가능": 0, "보류": 1, "불가": 2}
    ordered = sorted(
        candidates,
        key=lambda x: (
            status_rank.get(str(x.get("status", "")), 3),
            float(x.get("replacement_per_posting", 0)),
        ),
    )

    items = []
    seen = set()
    for c in ordered:
        title = f"{c.get('item', '')} ({c.get('category', '')})".strip()
        if not title or title in seen:
            continue
        seen.add(title)

        rpp = float(c.get("replacement_per_posting", 0))
        needed = float(c.get("estimated_needed_count", 0))
        detail = (
            f"주관: {c.get('owner_dept', '-')}, 상태: {c.get('status', '-')}, 실행: {c.get('executor', '-')} | "
            f"포스팅 1건당 대체 {rpp:g}건 | 블로그 계약 건수 기준 예상 {needed:g}건"
        )
        if c.get("note"):
            detail += f" | 비고: {c.get('note')}"

        items.append(
            {
                "title": title,
                "detail": detail,
                "selected": True,
                "source": "catalog_fallback",
                "team": dept_label,
            }
        )
        if len(items) >= max_items:
            break
    return items


def _product_items_for_team(results, dept_key: str, dept_label: str):
    """
    v3:
    1) Use report data + blog contract count
    2) Use replacement catalog rows
    3) Ask LLM for team recommendations
    4) Fallback to rule-based ranking
    5) Final fallback to templates
    """
    blog_contract_count = _extract_blog_contract_count(results)
    team_kpi = _product_kpi_for_team(results, dept_key)
    catalog_rows = _get_replacement_catalog_rows()
    candidates = _catalog_candidates_for_team(catalog_rows, dept_key, blog_contract_count)

    llm_items = []
    if candidates:
        from src.llm.llm_client import generate_team_product_recommendations

        llm_result = generate_team_product_recommendations(
            team_name=dept_label,
            blog_contract_count=blog_contract_count,
            team_kpis=team_kpi,
            all_report_context=_compact_kpi_context(results),
            catalog_candidates=candidates,
            max_items=5,
        )

        for rec in llm_result:
            title = str(rec.get("title", "")).strip()
            if not title:
                continue
            detail = str(rec.get("detail", "")).strip()
            rpp = _product_safe_float(rec.get("replacement_per_posting"))
            needed = _product_safe_float(rec.get("estimated_needed_count"))
            if rpp is not None and needed is not None:
                detail = (
                    f"{detail} | 포스팅 1건당 대체 {rpp:g}건 | "
                    f"블로그 계약 건수 기준 예상 {needed:g}건"
                )
            llm_items.append(
                {
                    "title": title,
                    "detail": detail,
                    "selected": True,
                    "source": "catalog_llm",
                    "team": dept_label,
                }
            )
            if len(llm_items) >= 5:
                break

    items = list(llm_items)
    if len(items) < 5 and candidates:
        fallback = _fallback_product_items_from_catalog(candidates, dept_label, max_items=5)
        seen = {x.get("title", "") for x in items}
        for item in fallback:
            if item.get("title", "") in seen:
                continue
            items.append(item)
            seen.add(item.get("title", ""))
            if len(items) >= 5:
                break

    if len(items) < 5:
        metric_hint = _product_metric_hint(team_kpi)
        templates = PRODUCT_TEMPLATES.get(dept_key, [])
        seen = {x.get("title", "") for x in items}
        for title, detail in templates:
            if title in seen:
                continue
            items.append(
                {
                    "title": title,
                    "detail": detail.format(metric_hint=metric_hint),
                    "selected": True,
                    "source": "template",
                    "team": dept_label,
                }
            )
            seen.add(title)
            if len(items) >= 5:
                break

    return items[:5]


STATUS_AVAILABLE = "\uac00\ub2a5"
STATUS_HOLD = "\ubcf4\ub958"
STATUS_BLOCKED = "\ubd88\uac00"

TEAM_OWNER_LABELS_V2 = {
    "marketing": ["\ub9c8\ucf00\ud305\ud300"],
    "design": ["\ub514\uc790\uc778\ud300"],
    "content": ["\ucf58\ud150\uce20\ud300"],
    "youtube": ["\uc601\uc0c1\ud300"],
    "ads": ["\uad11\uace0\ud300", "\ub9c8\ucf00\ud305\ud300"],
}

TEAM_MATCH_KEYWORDS_V2 = {
    "marketing": [
        "\ub9ac\ubdf0", "\ubc29\ubb38\uc790\ub9ac\ubdf0", "\ub9d8\uce74\ud398", "\uc9c0\uc2ddin",
        "\ub124\uc774\ubc84", "\uc608\uc57d", "\uc778\ubb3c\ub4f1\ub85d",
    ],
    "design": [
        "\ub514\uc790\uc778", "\ubc30\ub108", "\uc381\ub124\uc77c", "\ud648\ud398\uc774\uc9c0",
        "\uc0c1\uc138\ud398\uc774\uc9c0", "\ub79c\ub529", "pop",
    ],
    "content": [
        "\ube14\ub85c\uadf8", "\ud3ec\uc2a4\ud305", "\ucf58\ud150\uce20", "\uce7c\ub7fc",
        "\uccb4\ud5d8\ub2e8", "\ubc30\ud3ec\ud615",
    ],
    "youtube": [
        "\uc601\uc0c1", "\uc720\ud29c\ube0c", "\uc20f\ud3fc", "\ucd2c\uc601", "\ud3b8\uc9d1",
    ],
    "ads": [
        "\uad11\uace0", "\uac80\uc0c9\uad11\uace0", "\ucea0\ud398\uc778", "\ub9ac\ud0c0\uac9f\ud305", "\ubc30\ub108\uad11\uace0",
    ],
}


def _contains_any_v2(text: str, keywords: list) -> int:
    target = str(text or "").lower()
    return sum(1 for kw in keywords if str(kw).lower() in target)


def _team_candidate_score_v2(row: dict, dept_key: str) -> float:
    status = str(row.get("status", "")).strip()
    owner = _owner_tokens(row.get("owner_dept", ""))
    category = str(row.get("category", ""))
    item = str(row.get("item", ""))
    note = str(row.get("note", ""))

    score = 0.0
    if status == STATUS_AVAILABLE:
        score += 100.0
    elif status == STATUS_HOLD:
        score += 40.0
    elif status == STATUS_BLOCKED:
        score -= 120.0

    owner_labels = TEAM_OWNER_LABELS_V2.get(dept_key, [])
    if any(label in owner for label in owner_labels):
        score += 45.0

    keywords = TEAM_MATCH_KEYWORDS_V2.get(dept_key, [])
    score += 8.0 * _contains_any_v2(category, keywords)
    score += 12.0 * _contains_any_v2(item, keywords)
    score += 4.0 * _contains_any_v2(note, keywords)

    rpp = _product_safe_float(row.get("replacement_per_posting"))
    if rpp is not None and rpp > 0:
        score += min(35.0, 18.0 / rpp)
    return score


def _catalog_candidates_for_team(rows: list, dept_key: str, blog_contract_count: float):
    """v4 candidate selector: team relevance + status priority + dedupe + ranking."""
    if not rows:
        return []

    def is_match(row):
        owner = _owner_tokens(row.get("owner_dept", ""))
        category = str(row.get("category", ""))
        item = str(row.get("item", ""))

        if dept_key == "strategy":
            return True
        if dept_key == "marketing":
            return "\ub9c8\ucf00\ud305\ud300" in owner
        if dept_key == "design":
            return "\ub514\uc790\uc778\ud300" in owner
        if dept_key == "content":
            return ("\ucf58\ud150\uce20\ud300" in owner) or ("\ube14\ub85c\uadf8" in category) or ("\ube14\ub85c\uadf8" in item)
        if dept_key == "youtube":
            return ("\uc601\uc0c1\ud300" in owner) or ("\uc601\uc0c1" in category) or ("\uc601\uc0c1" in item)
        if dept_key == "ads":
            return ("\uad11\uace0" in category) or ("\uad11\uace0" in item) or ("\ub9c8\ucf00\ud305\ud300" in owner)
        return False

    out = []
    for row in rows:
        if not is_match(row):
            continue
        rpp = _product_safe_float(row.get("replacement_per_posting"))
        if rpp is None:
            continue
        needed = float(blog_contract_count) * float(rpp)
        record = {
            "category": str(row.get("category", "")).strip(),
            "item": str(row.get("item", "")).strip(),
            "owner_dept": str(row.get("owner_dept", "")).strip(),
            "status": str(row.get("status", "")).strip(),
            "executor": str(row.get("executor", "")).strip(),
            "replacement_per_posting": float(rpp),
            "estimated_needed_count": float(needed),
            "note": str(row.get("note", "")).strip(),
        }
        record["score"] = _team_candidate_score_v2(record, dept_key)
        out.append(record)

    # Prefer non-blocked rows unless not enough.
    non_blocked = [r for r in out if str(r.get("status", "")).strip() != STATUS_BLOCKED]
    pool = non_blocked if len(non_blocked) >= 5 else out

    # Deduplicate by item/category while keeping best score.
    best_by_key = {}
    for row in pool:
        k = (str(row.get("item", "")).strip(), str(row.get("category", "")).strip())
        prev = best_by_key.get(k)
        if prev is None or float(row.get("score", 0)) > float(prev.get("score", 0)):
            best_by_key[k] = row

    ranked = sorted(
        best_by_key.values(),
        key=lambda x: (float(x.get("score", 0)), -float(x.get("replacement_per_posting", 0) or 0)),
        reverse=True,
    )
    return ranked[:30]


def _fallback_product_items_from_catalog(candidates: list, dept_label: str, max_items: int = 5):
    """v4 fallback: status + score + replacement efficiency."""
    if not candidates:
        return []

    status_rank = {STATUS_AVAILABLE: 0, STATUS_HOLD: 1, STATUS_BLOCKED: 2}
    ordered = sorted(
        candidates,
        key=lambda x: (
            status_rank.get(str(x.get("status", "")).strip(), 3),
            -float(x.get("score", 0)),
            float(x.get("replacement_per_posting", 0)),
        ),
    )

    items = []
    seen = set()
    for c in ordered:
        title = f"{c.get('item', '')} ({c.get('category', '')})".strip()
        if not title or title in seen:
            continue
        seen.add(title)

        rpp = float(c.get("replacement_per_posting", 0))
        needed = float(c.get("estimated_needed_count", 0))
        detail = (
            f"주관: {c.get('owner_dept', '-')}, 상태: {c.get('status', '-')}, 실행: {c.get('executor', '-')} | "
            f"포스팅 1건당 대체 {rpp:g}건 | 블로그 계약 건수 기준 예상 {needed:g}건"
        )
        if c.get("note"):
            detail += f" | 비고: {c.get('note')}"

        items.append(
            {
                "title": title,
                "detail": detail,
                "selected": True,
                "source": "catalog_fallback",
                "team": dept_label,
            }
        )
        if len(items) >= max_items:
            break
    return items


DESIGN_CARRYOVER_POLICY = {
    "homepage_10": {
        "title": "[이월치환] 홈페이지 10만원 패키지",
        "price": 100000,
        "tasks": [
            "홈페이지 내 슬라이드 Tap구역 2개 추가",
            "퀵메뉴 연동 (미연동 시)",
        ],
    },
    "homepage_20": {
        "title": "[이월치환-예외] 홈페이지 20만원 패키지",
        "price": 200000,
        "tasks": [
            "홈페이지 내 컨텐츠 1구역 추가",
            "DB바 + 관리자 페이지 연동",
            "디바이스별 반응형 추가",
            "임시페이지 별도 제작 (PC/MB)",
            "심화 모션 추가",
            "SEO 최적화 (미적용 시)",
        ],
    },
    "draft_10": {
        "title": "[이월치환] 시안 제작 10만원 패키지",
        "price": 100000,
        "tasks": [
            "사이니지 2종",
            "구인공고 1종",
            "이벤트 시안 1종(1건당 최대 2장)",
            "X 배너 1종",
            "피켓 2종",
        ],
    },
    "draft_20": {
        "title": "[이월치환-예외] 시안 제작 20만원 패키지",
        "price": 200000,
        "tasks": [
            "사이니지 5종",
            "이벤트 시안 5종(1건당 최대 2장)",
            "X 배너 2종",
            "피켓 4종",
        ],
    },
}

DESIGN_PM_POLICY = {
    "homepage_5": {
        "title": "[PM제안] 홈페이지 5만원 패키지",
        "price": 50000,
        "tasks": [
            "슬라이드 배너 제작 1종",
            "퀵메뉴 연동 (미연동 시)",
            "홈페이지 내 슬라이드 Tap구역 1개 추가",
        ],
    },
    "homepage_10": {
        "title": "[PM제안] 홈페이지 10만원 패키지",
        "price": 100000,
        "tasks": [
            "홈페이지 내 슬라이드 Tap구역 2개 추가",
            "홈페이지 내 슬라이드 배너 제작 2종",
        ],
    },
    "draft_5": {
        "title": "[PM제안] 시안 5만원 패키지",
        "price": 50000,
        "tasks": [
            "이벤트 시안 1종(1건당 최대 2장)",
            "사이니지 1종",
            "네이버 플레이스 시안 1종",
            "홍보성 시안 1종",
        ],
    },
    "draft_10": {
        "title": "[PM제안] 시안 10만원 패키지",
        "price": 100000,
        "tasks": [
            "사이니지 2종",
            "피켓 2종",
            "블로그 스킨 시안 (위젯 없이)",
            "인스타 세팅 시안물 3개",
            "인쇄 시안물 (디자인팀 협의: X배너/약력판넬/명함)",
        ],
    },
}


TEAM_PACKAGE_REGISTRY_CATALOG_TEAMS = {
    "content": {"label": "콘텐츠팀", "icon": "📝", "color": "#06b6d4"},
    "youtube": {"label": "영상팀", "icon": "🎬", "color": "#ef4444"},
    "ads": {"label": "광고팀", "icon": "📣", "color": "#10b981"},
}

# ---------------------------------------------------------------------------
# Marketing Team: PM 제안 상품 정책 (엑셀 '대체상품 및 액션플랜' 기준)
# ---------------------------------------------------------------------------
MARKETING_PM_POLICY = {
    # -- 방문자리뷰 --
    "review_kakaomap": {"title": "카카오맵 리뷰", "price": 10000, "tasks": ["건당 대체 20건"]},
    "review_gangnam": {"title": "강남언니 리뷰", "price": 20000, "tasks": ["건당 대체 10건"]},
    # -- 블로그리뷰 --
    "blogreview_experience": {"title": "체험단", "price": 200000, "tasks": ["밑작업 2건+후기글 1건+마무리 1건", "건당 대체 1건"]},
    "blogreview_deploy": {"title": "배포형 게시물", "price": 10000, "tasks": ["건당 대체 20건"]},
    # -- 맘카페 --
    "momcafe_qa": {"title": "맘카페 (질문형/후기형)", "price": 50000, "tasks": ["김도영 대표측 실행", "건당 대체 4건"]},
    # -- 지식in --
    "knowledge_hidoc": {"title": "하이닥-지식인 연동", "price": 50000, "tasks": ["건당 대체 4건"]},
    # -- 네이버 인물등록 --
    "naverperson_all": {"title": "전 채널 연결 (네이버 인물등록)", "price": 50000, "tasks": ["건당 대체 4건"]},
    # -- 추가 플랫폼 세팅(입점) --
    "platform_modudoc": {"title": "모두닥 입점", "price": 100000, "tasks": ["상세페이지 별도", "건당 대체 2건"]},
    "platform_gangnam": {"title": "강남언니 입점", "price": 100000, "tasks": ["상세페이지 별도", "건당 대체 2건"]},
    "platform_babitalk": {"title": "바비톡 입점", "price": 100000, "tasks": ["상세페이지 별도", "건당 대체 2건"]},
    "platform_cashidoc": {"title": "캐시닥 입점", "price": 100000, "tasks": ["상세페이지 별도", "건당 대체 2건"]},
    "platform_yeoshin": {"title": "여신티켓 입점", "price": 100000, "tasks": ["상세페이지 별도", "건당 대체 2건"]},
    "platform_safedoc": {"title": "세이프닥 입점", "price": 100000, "tasks": ["상세페이지 별도", "건당 대체 2건"]},
    "platform_danggeun": {"title": "당근 입점", "price": 100000, "tasks": ["광고/추가 컨텐츠 별도", "건당 대체 2건"]},
    "platform_insta": {"title": "인스타그램 세팅", "price": 100000, "tasks": ["프로필/하이라이트/고정 포스트 3개", "건당 대체 2건"]},
    # -- 추가 콘텐츠 --
    "addcontent_kakao": {"title": "카카오 소식글", "price": 50000, "tasks": ["일상글 / AI생성 구강상식", "건당 대체 4건"]},
    "addcontent_danggeun": {"title": "당근 소식글", "price": 50000, "tasks": ["일상글 / AI생성 구강상식", "건당 대체 4건"]},
    # -- 언론배포 --
    "press_internet": {"title": "인터넷 기사 (언론배포)", "price": 600000, "tasks": ["언론사별 상이", "건당 대체 0.33건"]},
    # -- 온라인 광고 --
    "onlinead_image_powerlink": {"title": "이미지 파워링크", "price": 200000, "tasks": ["심의/세팅 대행, 충전·심의비 별도", "건당 대체 1건"]},
    "onlinead_powercontent": {"title": "파워컨텐츠", "price": 300000, "tasks": ["심의/세팅 대행, 충전·심의비 별도", "건당 대체 0.67건"]},
    "onlinead_brand": {"title": "브랜드광고", "price": 300000, "tasks": ["심의/세팅 대행, 충전·심의비 별도", "건당 대체 0.67건"]},
    "onlinead_danggeun": {"title": "당근 광고", "price": 100000, "tasks": ["심의/세팅 대행, 충전·심의비 별도", "건당 대체 2건"]},
    "onlinead_gfa": {"title": "GFA 광고", "price": 150000, "tasks": ["심의/세팅 대행, 충전·심의비 별도", "건당 대체 1.33건"]},
    "onlinead_meta": {"title": "Meta 광고", "price": 300000, "tasks": ["심의/세팅 대행, 충전·심의비 별도", "건당 대체 0.67건"]},
    "onlinead_google": {"title": "구글 광고", "price": 300000, "tasks": ["심의/세팅 대행, 충전·심의비 별도", "건당 대체 0.67건"]},
    "onlinead_kakao": {"title": "카카오 광고", "price": 300000, "tasks": ["심의/세팅 대행, 충전·심의비 별도", "건당 대체 0.67건"]},
    # -- 오프라인 광고 --
    "offlinead_mail": {"title": "생활우편", "price": 100000, "tasks": ["의료광고 심의 항목", "건당 대체 2건"]},
    "offlinead_bus": {"title": "버스광고", "price": 100000, "tasks": ["의료광고 심의 항목", "건당 대체 2건"]},
    "offlinead_busstop": {"title": "정류장광고", "price": 100000, "tasks": ["의료광고 심의 항목", "건당 대체 2건"]},
    "offlinead_subway": {"title": "지하철광고", "price": 100000, "tasks": ["의료광고 심의 항목", "건당 대체 2건"]},
    "offlinead_truck": {"title": "탑차광고", "price": 100000, "tasks": ["의료광고 심의 항목", "건당 대체 2건"]},
    "offlinead_elevator": {"title": "엘리베이터광고", "price": 300000, "tasks": ["의료광고 심의 항목", "건당 대체 0.67건"]},
    "offlinead_mart": {"title": "마트광고", "price": 100000, "tasks": ["의료광고 심의 항목", "건당 대체 2건"]},
    "offlinead_cinema": {"title": "영화관광고", "price": 500000, "tasks": ["의료광고 심의 항목", "건당 대체 0.4건"]},
    "offlinead_flyer": {"title": "전단지", "price": 100000, "tasks": ["의료광고 심의 항목", "건당 대체 2건"]},
}


TEAM_PACKAGE_REGISTRY = {
    "design": {
        "label": "디자인팀",
        "icon": "🎨",
        "color": "#f59e0b",
        "modes": {
            "carryover": {
                "label": "이월전환",
                "icon": "🔄",
                "desc": "디자인팀에서 적용 가능한 이월 기반 제안 패키지입니다.",
                "policy": {
                    "homepage_10": {
                        "title": DESIGN_CARRYOVER_POLICY["homepage_10"]["title"],
                        "price": DESIGN_CARRYOVER_POLICY["homepage_10"]["price"],
                        "tasks": DESIGN_CARRYOVER_POLICY["homepage_10"]["tasks"],
                    },
                    "draft_10": {
                        "title": DESIGN_CARRYOVER_POLICY["draft_10"]["title"],
                        "price": DESIGN_CARRYOVER_POLICY["draft_10"]["price"],
                        "tasks": DESIGN_CARRYOVER_POLICY["draft_10"]["tasks"],
                    },
                },
                "source_tag": "design_carryover_policy",
                "requires_carryover": True,
            },
            "pm": {
                "label": "PM 제안",
                "icon": "🧩",
                "desc": "홈페이지/랜딩 페이지 기준 PM 제안 패키지입니다.",
                "policy": {
                    "homepage_5": {
                        "title": DESIGN_PM_POLICY["homepage_5"]["title"],
                        "price": DESIGN_PM_POLICY["homepage_5"]["price"],
                        "tasks": DESIGN_PM_POLICY["homepage_5"]["tasks"],
                    },
                    "homepage_10": {
                        "title": DESIGN_PM_POLICY["homepage_10"]["title"],
                        "price": DESIGN_PM_POLICY["homepage_10"]["price"],
                        "tasks": DESIGN_PM_POLICY["homepage_10"]["tasks"],
                    },
                },
                "source_tag": "design_pm_policy",
                "requires_carryover": False,
            },
        },
        "groups": [
            {"prefix": "homepage", "label": "홈페이지"},
            {"prefix": "draft", "label": "드래프트"},
        ],
    },
    "marketing": {
        "label": "마케팅팀",
        "icon": "📈",
        "color": "#3b82f6",
        "modes": {
            "pm": {
                "label": "PM 제안",
                "icon": "💡",
                "desc": "블로그 계약 건수 기반 마케팅 대체상품 제안입니다.",
                "policy": MARKETING_PM_POLICY,
                "source_tag": "marketing_pm_policy",
                "requires_carryover": False,
            },
        },
        "groups": [
            {"prefix": "review", "label": "방문자리뷰"},
            {"prefix": "blogreview", "label": "블로그리뷰"},
            {"prefix": "momcafe", "label": "맘카페"},
            {"prefix": "knowledge", "label": "지식in"},
            {"prefix": "naverperson", "label": "네이버 인물등록"},
            {"prefix": "platform", "label": "추가 플랫폼 세팅 (입점)"},
            {"prefix": "addcontent", "label": "추가 콘텐츠"},
            {"prefix": "press", "label": "언론배포"},
            {"prefix": "onlinead", "label": "온라인 광고"},
            {"prefix": "offlinead", "label": "오프라인 광고"},
        ],
    },
}


def _team_policy_group_slug(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "misc"
    slug = re.sub(r"[^0-9a-zA-Z가-힣]+", "_", raw)
    slug = slug.strip("_")
    return slug or "misc"


def _build_catalog_package_policy(dept_key: str, max_items: int = 10):
    blog_counts = _extract_blog_counts(st.session_state.get("processed_results", {}))
    contract_count = float(blog_counts.get("contract_count", 0.0))
    rows = _get_replacement_catalog_rows()
    candidates = _catalog_candidates_for_team(rows, dept_key, contract_count)

    policy = {}
    if not candidates:
        return policy, []

    seen = set()
    group_count = {}
    for idx, cand in enumerate(candidates):
        item = str(cand.get("item", "")).strip()
        if not item:
            continue
        category = str(cand.get("category", "")).strip() or "기타"
        dedupe_key = (category, item)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        slug = _team_policy_group_slug(category)
        policy_key = f"{slug}_{idx:02d}"
        group_count.setdefault(slug, {"label": category, "prefix": slug, "count": 0})
        group_count[slug]["count"] += 1

        rpp = _product_safe_float(cand.get("replacement_per_posting"))
        price = _product_safe_float(cand.get("price_vat_excl"))
        if price is None:
            price = _product_safe_float(cand.get("cost_excl_labor"))
        if price is None:
            price = _extract_unit_price_krw(item)
        if price is None:
            price = 0.0

        tasks = [category]
        if rpp is not None:
            tasks.append(f"건당 {rpp:g}배치")
        status = str(cand.get("status", "")).strip()
        if status:
            tasks.append(f"상태: {status}")
        note = str(cand.get("note", "")).strip()
        if note:
            tasks.append(note[:40])

        policy[policy_key] = {
            "title": item if category == "기타" else f"{item} ({category})",
            "price": float(price),
            "tasks": tasks[:3],
        }
        if len(policy) >= max_items:
            break

    groups = [
        {"prefix": meta["prefix"], "label": meta["label"]}
        for meta in sorted(group_count.values(), key=lambda x: x["count"], reverse=True)
    ]
    return policy, groups


def _build_catalog_team_package_entry(dept_key: str, meta: dict) -> dict:
    policy, groups = _build_catalog_package_policy(dept_key)
    if not groups:
        groups = [{"prefix": "etc", "label": "기타 제안"}]
    return {
        "label": str(meta.get("label", dept_key)),
        "icon": str(meta.get("icon", "🧰")),
        "color": str(meta.get("color", "#6b7280")),
        "modes": {
            "catalog": {
                "label": "카탈로그 제안",
                "icon": "🧾",
                "desc": "대체상품 목록 기반으로 구성된 제안입니다.",
                "policy": policy,
                "source_tag": f"{dept_key}_catalog_policy",
                "requires_carryover": False,
            }
        },
        "groups": groups,
    }


def _sync_team_package_registry_from_catalog():
    # 정적 등록 팀(design, marketing 등)은 보존하고 카탈로그 팀만 동적 추가
    static_keys = set(TEAM_PACKAGE_REGISTRY.keys())
    dynamic_entries = {
        dept_key: _build_catalog_team_package_entry(dept_key, meta)
        for dept_key, meta in TEAM_PACKAGE_REGISTRY_CATALOG_TEAMS.items()
        if dept_key not in static_keys
    }
    TEAM_PACKAGE_REGISTRY.update(dynamic_entries)


def _extract_blog_counts(results: dict) -> dict:
    """Return blog contract/carryover counts from current report scope."""
    blog = (results or {}).get("blog", {})
    kpi = blog.get("kpi", {})
    curr_work = blog.get("current_month_data", {}).get("work", {})

    contract = _product_safe_float(kpi.get("contract_count"))
    if contract is None:
        contract = _product_safe_float(curr_work.get("contract_count"))
    if contract is None:
        monthly = blog.get("clean_data", {}).get("work", {}).get("monthly_summary", [])
        if monthly and isinstance(monthly, list) and isinstance(monthly[-1], dict):
            contract = _product_safe_float(monthly[-1].get("contract_count"))
    if contract is None:
        contract = 0.0

    carryover = _product_safe_float(kpi.get("carryover_count"))
    if carryover is None:
        carryover = _product_safe_float(curr_work.get("base_carryover"))
    if carryover is None:
        carryover = _product_safe_float(curr_work.get("carryover"))
    if carryover is None:
        monthly = blog.get("clean_data", {}).get("work", {}).get("monthly_summary", [])
        if monthly and isinstance(monthly, list) and isinstance(monthly[-1], dict):
            carryover = _product_safe_float(monthly[-1].get("base_carryover"))
            if carryover is None:
                carryover = _product_safe_float(monthly[-1].get("carryover"))
    if carryover is None:
        carryover = 0.0

    return {
        "contract_count": max(float(contract), 0.0),
        "carryover_count": max(float(carryover), 0.0),
    }


def _extract_blog_contract_count(results: dict) -> float:
    """Compatibility wrapper."""
    return _extract_blog_counts(results).get("contract_count", 0.0)


def _build_design_policy_items(blog_counts: dict, dept_label: str):
    """Build design items where carryover policy is applied only to carryover count."""
    contract_count = float(blog_counts.get("contract_count", 0.0))
    carryover_count = float(blog_counts.get("carryover_count", 0.0))
    carryover_replacement_units = carryover_count * 0.5

    items = []

    if carryover_count > 0:
        base_detail = (
            f"기준: 이월 {carryover_count:g}건 → 치환 {carryover_replacement_units:g}건 "
            f"(이월 1건당 0.5 치환). 기본 10만원, 부득이한 경우 20만원까지 허용."
        )
        items.append(
            {
                "title": DESIGN_CARRYOVER_POLICY["homepage_10"]["title"],
                "detail": base_detail + " | 실행: " + ", ".join(DESIGN_CARRYOVER_POLICY["homepage_10"]["tasks"]),
                "selected": True,
                "source": "design_carryover_policy",
                "team": dept_label,
            }
        )
        items.append(
            {
                "title": DESIGN_CARRYOVER_POLICY["draft_10"]["title"],
                "detail": base_detail + " | 실행: " + ", ".join(DESIGN_CARRYOVER_POLICY["draft_10"]["tasks"]),
                "selected": True,
                "source": "design_carryover_policy",
                "team": dept_label,
            }
        )
        items.append(
            {
                "title": DESIGN_CARRYOVER_POLICY["homepage_20"]["title"],
                "detail": "예외 확장안(20만원) | 실행: " + ", ".join(DESIGN_CARRYOVER_POLICY["homepage_20"]["tasks"]),
                "selected": False,
                "source": "design_carryover_policy",
                "team": dept_label,
            }
        )
        items.append(
            {
                "title": DESIGN_CARRYOVER_POLICY["draft_20"]["title"],
                "detail": "예외 확장안(20만원) | 실행: " + ", ".join(DESIGN_CARRYOVER_POLICY["draft_20"]["tasks"]),
                "selected": False,
                "source": "design_carryover_policy",
                "team": dept_label,
            }
        )

    if contract_count > 0:
        # PM 제안은 계약건수 기반 제안(이월 전용 아님)
        pm_tier = "10" if contract_count >= 3 else "5"
        items.append(
            {
                "title": DESIGN_PM_POLICY[f"homepage_{pm_tier}"]["title"],
                "detail": f"계약 {contract_count:g}건 기반 PM 제안 | 실행: " + ", ".join(DESIGN_PM_POLICY[f"homepage_{pm_tier}"]["tasks"]),
                "selected": True,
                "source": "design_pm_policy",
                "team": dept_label,
            }
        )
        items.append(
            {
                "title": DESIGN_PM_POLICY[f"draft_{pm_tier}"]["title"],
                "detail": f"계약 {contract_count:g}건 기반 PM 제안 | 실행: " + ", ".join(DESIGN_PM_POLICY[f"draft_{pm_tier}"]["tasks"]),
                "selected": True,
                "source": "design_pm_policy",
                "team": dept_label,
            }
        )

    # Deduplicate while preserving order
    out = []
    seen = set()
    for item in items:
        t = str(item.get("title", "")).strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(item)
    return out[:5]


def _product_items_for_team_base(results, dept_key: str, dept_label: str):
    """Existing engine (catalog + llm + fallback + template) wrapped as base."""
    blog_counts = _extract_blog_counts(results)
    blog_contract_count = blog_counts.get("contract_count", 0.0)
    team_kpi = dict(_product_kpi_for_team(results, dept_key) or {})
    team_kpi["blog_contract_count"] = blog_counts.get("contract_count", 0.0)
    team_kpi["blog_carryover_count"] = blog_counts.get("carryover_count", 0.0)

    catalog_rows = _get_replacement_catalog_rows()
    candidates = _catalog_candidates_for_team(catalog_rows, dept_key, blog_contract_count)

    llm_items = []
    if candidates:
        from src.llm.llm_client import generate_team_product_recommendations

        llm_result = generate_team_product_recommendations(
            team_name=dept_label,
            blog_contract_count=blog_contract_count,
            team_kpis=team_kpi,
            all_report_context=_compact_kpi_context(results),
            catalog_candidates=candidates,
            max_items=5,
        )

        for rec in llm_result:
            title = str(rec.get("title", "")).strip()
            if not title:
                continue
            detail = str(rec.get("detail", "")).strip()
            rpp = _product_safe_float(rec.get("replacement_per_posting"))
            needed = _product_safe_float(rec.get("estimated_needed_count"))
            if rpp is not None and needed is not None:
                detail = f"{detail} | 포스팅 1건당 대체 {rpp:g}건 | 블로그 계약 건수 기준 예상 {needed:g}건"
            llm_items.append(
                {
                    "title": title,
                    "detail": detail,
                    "selected": True,
                    "source": "catalog_llm",
                    "team": dept_label,
                }
            )
            if len(llm_items) >= 5:
                break

    items = list(llm_items)
    if len(items) < 5 and candidates:
        fallback = _fallback_product_items_from_catalog(candidates, dept_label, max_items=5)
        seen = {x.get("title", "") for x in items}
        for item in fallback:
            if item.get("title", "") in seen:
                continue
            items.append(item)
            seen.add(item.get("title", ""))
            if len(items) >= 5:
                break

    if len(items) < 5:
        metric_hint = _product_metric_hint(team_kpi)
        templates = PRODUCT_TEMPLATES.get(dept_key, [])
        seen = {x.get("title", "") for x in items}
        for title, detail in templates:
            if title in seen:
                continue
            items.append(
                {
                    "title": title,
                    "detail": detail.format(metric_hint=metric_hint),
                    "selected": True,
                    "source": "template",
                    "team": dept_label,
                }
            )
            seen.add(title)
            if len(items) >= 5:
                break

    return items[:5]


def _product_items_for_team(results, dept_key: str, dept_label: str):
    """
    v5:
    - blog contract/carryover split
    - design carryover policy applies to carryover only
    - PM list applies to contract-driven proposal
    """
    if dept_key != "design":
        return _product_items_for_team_base(results, dept_key, dept_label)

    blog_counts = _extract_blog_counts(results)
    policy_items = _build_design_policy_items(blog_counts, dept_label)
    if len(policy_items) >= 5:
        return policy_items[:5]

    base_items = _product_items_for_team_base(results, dept_key, dept_label)
    seen = {x.get("title", "") for x in policy_items}
    merged = list(policy_items)
    for item in base_items:
        if item.get("title", "") in seen:
            continue
        merged.append(item)
        seen.add(item.get("title", ""))
        if len(merged) >= 5:
            break
    return merged[:5]


def _get_design_option_settings():
    """PM option state for design recommendation generation."""
    if "design_policy_mode" not in st.session_state:
        st.session_state.design_policy_mode = "mixed"
    if "design_include_20" not in st.session_state:
        st.session_state.design_include_20 = True
    if "design_pm_tier" not in st.session_state:
        st.session_state.design_pm_tier = "auto"
    return {
        "mode": st.session_state.design_policy_mode,
        "include_20": bool(st.session_state.design_include_20),
        "pm_tier": st.session_state.design_pm_tier,
    }


def _build_design_policy_items_with_options(blog_counts: dict, dept_label: str, settings: dict):
    contract_count = float(blog_counts.get("contract_count", 0.0))
    carryover_count = float(blog_counts.get("carryover_count", 0.0))
    carryover_units = carryover_count * 0.5

    mode = settings.get("mode", "mixed")
    include_20 = bool(settings.get("include_20", True))
    pm_tier_opt = settings.get("pm_tier", "auto")

    include_carryover = mode in ("mixed", "carryover_only")
    include_pm = mode in ("mixed", "pm_only")

    items = []

    if include_carryover and carryover_count > 0:
        base_detail = (
            f"기준: 이월 {carryover_count:g}건 → 치환 {carryover_units:g}건 "
            f"(이월 1건당 0.5 치환). 기본 10만원, 부득이한 경우 20만원까지 허용."
        )
        items.append(
            {
                "title": DESIGN_CARRYOVER_POLICY["homepage_10"]["title"],
                "detail": base_detail + " | 실행: " + ", ".join(DESIGN_CARRYOVER_POLICY["homepage_10"]["tasks"]),
                "selected": True,
                "source": "design_carryover_policy",
                "team": dept_label,
            }
        )
        items.append(
            {
                "title": DESIGN_CARRYOVER_POLICY["draft_10"]["title"],
                "detail": base_detail + " | 실행: " + ", ".join(DESIGN_CARRYOVER_POLICY["draft_10"]["tasks"]),
                "selected": True,
                "source": "design_carryover_policy",
                "team": dept_label,
            }
        )
        if include_20:
            items.append(
                {
                    "title": DESIGN_CARRYOVER_POLICY["homepage_20"]["title"],
                    "detail": "예외 확장안(20만원) | 실행: " + ", ".join(DESIGN_CARRYOVER_POLICY["homepage_20"]["tasks"]),
                    "selected": False,
                    "source": "design_carryover_policy",
                    "team": dept_label,
                }
            )
            items.append(
                {
                    "title": DESIGN_CARRYOVER_POLICY["draft_20"]["title"],
                    "detail": "예외 확장안(20만원) | 실행: " + ", ".join(DESIGN_CARRYOVER_POLICY["draft_20"]["tasks"]),
                    "selected": False,
                    "source": "design_carryover_policy",
                    "team": dept_label,
                }
            )

    if include_pm and contract_count > 0:
        if pm_tier_opt == "5":
            pm_tier = "5"
        elif pm_tier_opt == "10":
            pm_tier = "10"
        else:
            pm_tier = "10" if contract_count >= 3 else "5"

        items.append(
            {
                "title": DESIGN_PM_POLICY[f"homepage_{pm_tier}"]["title"],
                "detail": f"계약 {contract_count:g}건 기반 PM 제안 | 실행: " + ", ".join(DESIGN_PM_POLICY[f"homepage_{pm_tier}"]["tasks"]),
                "selected": True,
                "source": "design_pm_policy",
                "team": dept_label,
            }
        )
        items.append(
            {
                "title": DESIGN_PM_POLICY[f"draft_{pm_tier}"]["title"],
                "detail": f"계약 {contract_count:g}건 기반 PM 제안 | 실행: " + ", ".join(DESIGN_PM_POLICY[f"draft_{pm_tier}"]["tasks"]),
                "selected": True,
                "source": "design_pm_policy",
                "team": dept_label,
            }
        )

    out = []
    seen = set()
    for item in items:
        t = str(item.get("title", "")).strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(item)
    return out[:5]


def _product_items_for_team(results, dept_key: str, dept_label: str):
    """
    v6:
    - PM selectable design options
    - blog contract/carryover split
    - design carryover policy applies to carryover only
    """
    if dept_key != "design":
        return _product_items_for_team_base(results, dept_key, dept_label)

    settings = _get_design_option_settings()
    blog_counts = _extract_blog_counts(results)
    policy_items = _build_design_policy_items_with_options(blog_counts, dept_label, settings)
    if len(policy_items) >= 5:
        return policy_items[:5]

    base_items = _product_items_for_team_base(results, dept_key, dept_label)
    seen = {x.get("title", "") for x in policy_items}
    merged = list(policy_items)
    for item in base_items:
        if item.get("title", "") in seen:
            continue
        merged.append(item)
        seen.add(item.get("title", ""))
        if len(merged) >= 5:
            break
    return merged[:5]


_render_action_plan_editor_core = render_action_plan_editor


def render_action_plan_editor(filtered_results):
    """Wrapper: PM option panel first, then existing editor."""
    _get_design_option_settings()

    mode_options = {
        "mixed": "혼합 (이월치환 + PM제안)",
        "carryover_only": "이월치환만",
        "pm_only": "PM제안만",
    }
    tier_options = {
        "auto": "자동",
        "5": "5만원",
        "10": "10만원",
    }

    st.markdown("""
        <div style="background:#fff7ed; border:1px solid #fed7aa; border-radius:12px; padding:14px 16px; margin-bottom:12px;">
            <p style="font-size:14px; font-weight:700; color:#9a3412; margin:0 0 4px 0;">PM 옵션 (디자인팀)</p>
            <p style="font-size:12px; color:#7c2d12; margin:0;">보고서 생성 전에 디자인팀 추천 기준을 먼저 선택하세요. 선택 후 '옵션 적용'을 누르면 추천 목록이 재생성됩니다.</p>
        </div>
    """, unsafe_allow_html=True)

    col_mode, col_tier, col_exc, col_apply = st.columns([2.2, 1.4, 1.3, 1.1])
    with col_mode:
        st.selectbox(
            "디자인 추천 모드",
            options=list(mode_options.keys()),
            format_func=lambda x: mode_options[x],
            key="design_policy_mode",
        )
    with col_tier:
        st.selectbox(
            "PM 티어",
            options=list(tier_options.keys()),
            format_func=lambda x: tier_options[x],
            key="design_pm_tier",
        )
    with col_exc:
        st.checkbox("20만원 예외 포함", key="design_include_20")
    with col_apply:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("옵션 적용", use_container_width=True, key="design_policy_apply_btn"):
            items = _normalize_product_items(st.session_state.action_plan_items)
            design_label = next((label for k, label, _ in ACTION_PLAN_TEAMS if k == "design"), "디자인팀")
            regenerated = _product_items_for_team(filtered_results, "design", design_label)
            items["design"] = regenerated
            st.session_state.action_plan_items = items
            st.rerun()

    _render_action_plan_editor_core(filtered_results)


CONTENT_SPECIAL_RATIO_CLIENTS = (
    "믿음치과",
    "서울클리어교정치과_하남미사",
    "올바로치과",
)

CONTENT_SPECIAL_RATIO_ITEM_KEYS = {
    "clinical_report",
    "expert_posting",
    "aeo_medical_posting",
}

CONTENT_CARRYOVER_POLICY = {
    "base_10": {
        "title": "[이월치환] 콘텐츠 10만원 기준안",
        "price": 100000,
        "tasks": [
            "이월 1건당 0.5 치환 기준 적용",
            "10만원 범위 내 대체상품 조합 제안",
        ],
    },
    "exception_20": {
        "title": "[이월치환-예외] 콘텐츠 20만원 확장안",
        "price": 200000,
        "tasks": [
            "부득이한 경우 20만원까지 확장",
            "고단가 상품(임상/전문가형/AEO) 우선 검토",
        ],
    },
}

CONTENT_CONTRACT_POLICY = [
    {
        "key": "service_momcafe",
        "title": "[서비스] 맘카페",
        "price": 0,
        "tasks": [
            "기존 포스팅 복붙",
            "맘카페 입점 비용 별도",
            "노출 보장 없음",
        ],
        "selected": False,
        "is_service": True,
    },
    {
        "key": "kin_economy",
        "title": "[5,000원] 지식인-이코노미 1건",
        "price": 5000,
        "tasks": [
            "네이버 지식인 치과 질문 답변",
            "AI 활용 답변",
        ],
        "selected": True,
    },
    {
        "key": "kin_standard",
        "title": "[10,000원] 지식인-스탠다드 1건",
        "price": 10000,
        "tasks": [
            "원하는 키워드 기반 치과 질문/답변",
            "자문자답 가능",
            "AI 활용 답변",
        ],
        "selected": True,
        "note": "플랫폼 이용료 별도",
    },
    {
        "key": "custom_standard",
        "title": "[75,000원] 커스텀 포스팅-스탠다드 1건",
        "price": 75000,
        "tasks": ["커스텀 포스팅 1건 제작"],
        "selected": True,
    },
    {
        "key": "custom_premium",
        "title": "[150,000원] 커스텀 포스팅-프리미엄 1건",
        "price": 150000,
        "tasks": ["커스텀 포스팅 1건 제작(프리미엄)"],
        "selected": True,
    },
    {
        "key": "clinical_report",
        "title": "[200,000원] 임상 레포트 1건",
        "price": 200000,
        "tasks": ["임상 레포트 1건 제작"],
        "selected": True,
    },
    {
        "key": "expert_posting",
        "title": "[200,000원] 정보성(전문가형) 포스팅 1건",
        "price": 200000,
        "tasks": ["전문가형 정보성 포스팅 1건 제작"],
        "selected": True,
    },
    {
        "key": "aeo_medical_posting",
        "title": "[200,000원] AEO 의학정보 포스팅 1건",
        "price": 200000,
        "tasks": ["AEO 의학정보 포스팅 1건 제작"],
        "selected": True,
    },
    {
        "key": "momcafe_standard",
        "title": "[200,000원] 맘카페-스탠다드 1건",
        "price": 200000,
        "tasks": ["맘카페 스탠다드 1건"],
        "selected": True,
        "note": "맘카페 입점 비용 별도",
    },
    {
        "key": "dynamic_posting",
        "title": "[300,000원] 다이나믹 포스팅 1건",
        "price": 300000,
        "tasks": ["다이나믹 포스팅 1건 제작"],
        "selected": True,
    },
    {
        "key": "branding_column",
        "title": "[400,000원] 브랜딩 칼럼 포스팅 1건",
        "price": 400000,
        "tasks": ["브랜딩 칼럼 포스팅 1건 제작"],
        "selected": True,
    },
    {
        "key": "aeo_homepage_column",
        "title": "[400,000원] AEO 홈페이지 칼럼 1건",
        "price": 400000,
        "tasks": ["AEO 홈페이지 칼럼 1건 제작"],
        "selected": True,
    },
]


def _is_content_team(dept_key: str, dept_label: str = "") -> bool:
    key = str(dept_key or "").lower()
    label = str(dept_label or "")
    if key in {"content", "contents", "blog", "blog_content"}:
        return True
    if "content" in key or "blog" in key:
        return True
    if "콘텐츠" in label or "컨텐츠" in label or "content" in label.lower():
        return True
    return False


def _is_content_special_ratio_client(results: dict) -> bool:
    blob = str(results or {})
    return any(name in blob for name in CONTENT_SPECIAL_RATIO_CLIENTS)


def _content_price_cap_from_setting(price_cap_setting: str, contract_count: float) -> int:
    if price_cap_setting == "200000":
        return 200000
    if price_cap_setting == "400000":
        return 400000
    if price_cap_setting == "all":
        return 0
    # auto
    return 200000 if contract_count < 3 else 400000


def _get_content_option_settings():
    if "content_policy_mode" not in st.session_state:
        st.session_state.content_policy_mode = "mixed"
    if "content_price_cap" not in st.session_state:
        st.session_state.content_price_cap = "auto"
    if "content_include_20" not in st.session_state:
        st.session_state.content_include_20 = True
    if "content_include_service" not in st.session_state:
        st.session_state.content_include_service = False
    if "content_apply_special_ratio" not in st.session_state:
        st.session_state.content_apply_special_ratio = True

    return {
        "mode": st.session_state.content_policy_mode,
        "price_cap": st.session_state.content_price_cap,
        "include_20": bool(st.session_state.content_include_20),
        "include_service": bool(st.session_state.content_include_service),
        "apply_special_ratio": bool(st.session_state.content_apply_special_ratio),
    }

def _format_replacement_units(units: float) -> str:
    try:
        return f"{float(units):.1f}"
    except Exception:
        return "0.0"


def _calculate_carryover_mode_usage(policy_dict: dict, selected_keys: list) -> dict:
    used_replacement_units = 0.0
    selected_count = 0
    for pk in selected_keys if isinstance(selected_keys, list) else []:
        pkg = (policy_dict or {}).get(pk) if isinstance(policy_dict, dict) else None
        if not isinstance(pkg, dict):
            continue
        selected_count += 1
        used_replacement_units += _product_safe_float(pkg.get("price", 0.0)) or 0.0
    return {
        "selected_count": selected_count,
        "used_replacement_units": used_replacement_units,
        "used_carryover_count": used_replacement_units * 2.0,
    }


_PACKAGE_CARD_CSS = """
<style>
.pkg-team-hdr {font-family: "Pretendard Variable","Noto Sans KR",sans-serif; font-size: 13px; font-weight: 800; letter-spacing: -0.3px; padding: 5px 14px; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; margin: 4px 0 6px 0;}
.pkg-grp {font-size: 11px; font-weight: 700; color: #9ca3af; margin: 12px 0 6px 0;}
.pkg-card {font-family: "Pretendard Variable","Noto Sans KR",sans-serif; border: 1.5px solid #e5e7eb; border-radius: 10px; background: #fff; padding: 12px 14px; margin-bottom: 8px;}
.pkg-card.sel {border-color: #818cf8; background: linear-gradient(135deg, #f5f3ff 0%, #eef2ff 100%);}
.pkg-card-head {display:flex; justify-content: space-between; align-items: center; margin-bottom: 6px;}
.pkg-card-title {font-size: 13px; font-weight: 700; color: #1f2937;}
.pkg-card-price {font-size: 13px; font-weight: 800; color: #6366f1; white-space: nowrap;}
.pkg-card-tasks {display:flex; flex-wrap: wrap; gap: 4px 8px;}
.pkg-card-task {font-size: 11px; color: #6b7280; line-height: 1.5; background: #f3f4f6; padding: 2px 8px; border-radius: 4px;}
.pkg-card.sel .pkg-card-task {background: #e0e7ff; color: #4338ca;}
.pkg-done-banner {border: 1.5px solid #22c55e; border-radius: 10px; background: linear-gradient(135deg, #f0fdf4 0%, #fff 100%); padding: 10px 14px; display: flex; align-items: center; gap: 8px;}
</style>
"""


def _render_team_package_cards(team_key: str, mode_key: str, policy_dict: dict, groups: list):
    st.markdown(_PACKAGE_CARD_CSS, unsafe_allow_html=True)
    config = TEAM_PACKAGE_REGISTRY.get(team_key, {})
    team_color = config.get("color", "#6b7280")
    team_label = config.get("label", team_key)
    team_icon = config.get("icon", "🏢")
    sel_key = f"{team_key}_{mode_key}_selections"
    current_sel = list(st.session_state.get(sel_key, []))
    changed = False

    st.markdown(
        f'<div class="pkg-team-hdr" style="color:{team_color}; background:{team_color}12;">'
        f'{team_icon} {team_label}</div>',
        unsafe_allow_html=True,
    )

    for grp in groups:
        prefix = grp["prefix"]
        pkgs = {k: v for k, v in policy_dict.items() if k.startswith(prefix)}
        if not pkgs:
            continue
        st.markdown(f'<p class="pkg-grp">{grp["label"]}</p>', unsafe_allow_html=True)
        cols = st.columns(2)
        for idx, (pk, pdata) in enumerate(pkgs.items()):
            with cols[idx % 2]:
                is_sel = pk in current_sel
                price = pdata.get("price", 0.0)
                price_str = f"{int(price // 10000)}만원" if isinstance(price, (int, float)) and price > 0 else "-"
                tasks = pdata.get("tasks", [])
                task_chips = "".join(f'<span class="pkg-card-task">{t}</span>' for t in tasks)
                cls = "pkg-card sel" if is_sel else "pkg-card"
                st.markdown(
                    f'<div class="{cls}">'
                    f'  <div class="pkg-card-head"><span class="pkg-card-title">{pdata["title"]}</span><span class="pkg-card-price">{price_str}</span></div>'
                    f'  <div class="pkg-card-tasks">{task_chips}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                new_val = st.checkbox("선택" if not is_sel else "선택됨", value=is_sel, key=f"pkg_{team_key}_{mode_key}_{pk}")
                if new_val != is_sel:
                    if new_val:
                        current_sel.append(pk)
                    else:
                        current_sel.remove(pk)
                    changed = True

    if changed:
        dedup = []
        seen = set()
        for key in current_sel:
            if key in seen:
                continue
            seen.add(key)
            dedup.append(key)
        st.session_state[sel_key] = dedup


def _confirm_team_package_selection(team_key: str, config: dict, blog_counts: dict):
    modes = config["modes"]
    dept_label = config["label"]
    done_key = f"{team_key}_proposal_done"
    contract_count = float(blog_counts.get("contract_count", 0.0))
    carryover_count = float(blog_counts.get("carryover_count", 0.0))
    carryover_units = carryover_count * 0.5

    items = []
    for mode_key, mode_cfg in modes.items():
        sel_key = f"{team_key}_{mode_key}_selections"
        policy_dict = mode_cfg.get("policy", {})
        selected_keys = st.session_state.get(sel_key, [])
        if not selected_keys:
            continue
        source_tag = mode_cfg.get("source_tag", f"{team_key}_{mode_key}_policy")
        for pk in selected_keys:
            pkg = policy_dict.get(pk)
            if not pkg:
                continue
            if mode_cfg.get("requires_carryover"):
                detail = (
                    f"디자인 이월 {carryover_count:g}건 기준, 사용량 {carryover_units:g}건(1건=0.5). "
                    f"실행: {', '.join(pkg['tasks'])}"
                )
            else:
                detail = f"계약 {contract_count:g}건 기준. 실행: {', '.join(pkg['tasks'])}"
            items.append({
                "title": pkg["title"],
                "detail": detail,
                "selected": True,
                "source": source_tag,
                "team": dept_label,
                "price": pkg.get("price", 0),
                "mode_type": mode_key,
            })
    if not items:
        st.warning("패키지를 선택해 주세요.")
        return

    all_items = _normalize_product_items(st.session_state.action_plan_items)
    all_items[team_key] = items
    st.session_state.action_plan_items = all_items
    st.session_state[done_key] = True
    st.toast(f"{dept_label} 선택 완료: {len(items)}개 항목 저장됨")
    st.rerun()


def _render_team_proposal_flow(team_key: str, filtered_results):
    config = TEAM_PACKAGE_REGISTRY.get(team_key)
    if not config:
        return

    blog_counts = _extract_blog_counts(filtered_results)
    carryover_count = float(blog_counts.get("carryover_count", 0.0))
    carryover_cap_units = carryover_count * 0.5
    modes = config["modes"]
    groups = config["groups"]
    team_label = config["label"]
    done_key = f"{team_key}_proposal_done"

    if st.session_state.get(done_key, False):
        current_items = _normalize_product_items(st.session_state.action_plan_items)
        team_items = current_items.get(team_key, [])
        count = len(team_items)
        titles = ", ".join(it.get("title", "")[:20] for it in team_items[:3])
        if count > 3:
            titles += f" +{count - 3}개"
        st.markdown(
            f"""
            <div class="pkg-done-banner">
                <span style="font-size:13px; font-weight:800; color:#16a34a;">✅ {team_label} 제안 완료</span>
                <span style="font-size:11px; color:#4e5968; margin-left:6px;">{count}개 제안 | {titles}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("초기화 후 다시 고르기", key=f"pkg_{team_key}_reset"):
            st.session_state[done_key] = False
            for mk in modes:
                st.session_state[f"{team_key}_{mk}_selections"] = []
            all_items = _normalize_product_items(st.session_state.action_plan_items)
            all_items[team_key] = []
            st.session_state.action_plan_items = all_items
            st.rerun()
        return

    for mode_key, mode_cfg in modes.items():
        sel_key = f"{team_key}_{mode_key}_selections"
        sel_count = len(st.session_state.get(sel_key, []))
        expander_label = f'{mode_cfg.get("icon", "🔖")} {mode_cfg.get("label", mode_key)}'
        if sel_count > 0:
            expander_label += f"  ({sel_count}개 선택)"
        with st.expander(expander_label, expanded=False):
            if mode_cfg.get("requires_carryover") and carryover_count <= 0:
                st.info("이월 데이터가 없으면 이월 기반 제안은 비활성화됩니다.")
                continue
            if mode_cfg.get("requires_carryover"):
                st.caption(f"이월 {carryover_count:g}건, 사용 가능량 {carryover_cap_units:g}건(1건=0.5). 기본 10개, 최대 20개.")
            _render_team_package_cards(team_key, mode_key, mode_cfg.get("policy", {}), groups)

    total = sum(len(st.session_state.get(f"{team_key}_{mk}_selections", [])) for mk in modes)
    btn_label = f"Step 2: 선택 완료 ({total}개 선택됨)" if total > 0 else "Step 2: 선택 완료 (상품을 먼저 선택해주세요)"
    if st.button(
        btn_label,
        key=f"pkg_{team_key}_confirm",
        use_container_width=True,
        type="primary",
        disabled=(total == 0),
    ):
        _confirm_team_package_selection(team_key, config, blog_counts)


def _build_content_policy_items_with_options(results: dict, blog_counts: dict, dept_label: str, settings: dict):
    contract_count = float(blog_counts.get("contract_count", 0.0))
    carryover_count = float(blog_counts.get("carryover_count", 0.0))
    carryover_units = carryover_count * 0.5

    mode = settings.get("mode", "mixed")
    include_20 = bool(settings.get("include_20", True))
    include_service = bool(settings.get("include_service", False))
    apply_special_ratio = bool(settings.get("apply_special_ratio", True))

    include_carryover = mode in ("mixed", "carryover_only")
    include_contract = mode in ("mixed", "contract_only")
    price_cap = _content_price_cap_from_setting(str(settings.get("price_cap", "auto")), contract_count)
    special_client = apply_special_ratio and _is_content_special_ratio_client(results)

    items = []

    if include_carryover and carryover_count > 0:
        base_detail = (
            f"기준: 이월 {carryover_count:g}건 -> 치환 {carryover_units:g}건 "
            f"(이월 1건당 0.5 치환). 기본 10만원, 예외 20만원까지 고려."
        )
        items.append(
            {
                "title": CONTENT_CARRYOVER_POLICY["base_10"]["title"],
                "detail": base_detail + " | 실행: " + ", ".join(CONTENT_CARRYOVER_POLICY["base_10"]["tasks"]),
                "selected": True,
                "source": "content_carryover_policy",
                "team": dept_label,
            }
        )
        if include_20:
            items.append(
                {
                    "title": CONTENT_CARRYOVER_POLICY["exception_20"]["title"],
                    "detail": "예외 확장안(20만원) | 실행: " + ", ".join(CONTENT_CARRYOVER_POLICY["exception_20"]["tasks"]),
                    "selected": False,
                    "source": "content_carryover_policy",
                    "team": dept_label,
                }
            )

    if include_contract and contract_count > 0:
        for row in CONTENT_CONTRACT_POLICY:
            if row.get("is_service") and not include_service:
                continue
            price = int(row.get("price", 0) or 0)
            if price_cap > 0 and price > price_cap:
                continue

            replacement_ratio = 1.0
            if special_client and row.get("key") in CONTENT_SPECIAL_RATIO_ITEM_KEYS:
                replacement_ratio = 2.0
            expected_count = contract_count * replacement_ratio

            detail = (
                f"계약 {contract_count:g}건 기준 예상 {expected_count:g}건 제안 | "
                f"실행: {', '.join(row.get('tasks', []))}"
            )
            if row.get("note"):
                detail += f" | 비고: {row.get('note')}"
            if special_client and row.get("key") in CONTENT_SPECIAL_RATIO_ITEM_KEYS:
                detail += " | 특례 거래처(임상/의학정보 1:2) 적용"

            items.append(
                {
                    "title": row.get("title", ""),
                    "detail": detail,
                    "selected": bool(row.get("selected", True)),
                    "source": "content_contract_policy",
                    "team": dept_label,
                }
            )

    out = []
    seen = set()
    for item in items:
        title = str(item.get("title", "")).strip()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(item)
    return out[:5]


_product_items_for_team_v6 = _product_items_for_team


def _product_items_for_team(results, dept_key: str, dept_label: str):
    """
    v7:
    - Keep design options flow (v6)
    - Add content-team policy (carryover 0.5, special 1:2 client rule, price-tier proposals)
    """
    if _is_content_team(dept_key, dept_label):
        settings = _get_content_option_settings()
        blog_counts = _extract_blog_counts(results)
        policy_items = _build_content_policy_items_with_options(results, blog_counts, dept_label, settings)
        if len(policy_items) >= 5:
            return policy_items[:5]

        base_items = _product_items_for_team_base(results, dept_key, dept_label)
        seen = {x.get("title", "") for x in policy_items}
        merged = list(policy_items)
        for item in base_items:
            if item.get("title", "") in seen:
                continue
            merged.append(item)
            seen.add(item.get("title", ""))
            if len(merged) >= 5:
                break
        return merged[:5]

    return _product_items_for_team_v6(results, dept_key, dept_label)


_render_action_plan_editor_v6 = render_action_plan_editor


def _find_content_team_key_and_label():
    for key, label, _ in ACTION_PLAN_TEAMS:
        if _is_content_team(key, label):
            return key, label
    return None, "콘텐츠팀"


def render_action_plan_editor(filtered_results):
    """Unified option studio (content + design), then original editor."""
    _get_content_option_settings()
    _get_design_option_settings()

    content_mode_options = {
        "mixed": "혼합 (이월치환 + 계약기반)",
        "carryover_only": "이월치환만",
        "contract_only": "계약기반만",
    }
    content_price_cap_options = {
        "auto": "자동",
        "200000": "20만원 이하",
        "400000": "40만원 이하",
        "all": "전체 가격대",
    }
    design_mode_options = {
        "mixed": "혼합 (이월치환 + PM제안)",
        "carryover_only": "이월치환만",
        "pm_only": "PM제안만",
    }
    design_tier_options = {
        "auto": "자동",
        "5": "5만원",
        "10": "10만원",
    }

    st.markdown(
        """
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
        .policy-studio-wrap {
            border: 1px solid #dbe4f0;
            border-radius: 14px;
            background: linear-gradient(180deg, #f8fbff 0%, #f3f8ff 100%);
            padding: 16px 18px 14px 18px;
            margin-bottom: 14px;
        }
        .policy-studio-title {
            font-family: "Pretendard Variable", "Noto Sans KR", sans-serif;
            font-size: 15px;
            font-weight: 780;
            color: #0f2a4d;
            margin: 0 0 4px 0;
            letter-spacing: -0.01em;
        }
        .policy-studio-desc {
            font-family: "Pretendard Variable", "Noto Sans KR", sans-serif;
            font-size: 12px;
            color: #294b74;
            margin: 0;
        }
        .policy-team-card {
            border: 1px solid #d5dfec;
            border-radius: 12px;
            background: #ffffff;
            padding: 12px 14px;
            margin-bottom: 8px;
        }
        .policy-team-title {
            font-family: "Pretendard Variable", "Noto Sans KR", sans-serif;
            font-size: 13px;
            font-weight: 740;
            color: #16355f;
            margin: 0 0 3px 0;
            letter-spacing: -0.01em;
        }
        .policy-team-sub {
            font-family: "Pretendard Variable", "Noto Sans KR", sans-serif;
            font-size: 11px;
            color: #567297;
            margin: 0;
        }
        .policy-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 2px;
            margin-bottom: 6px;
        }
        .policy-chip {
            font-family: "Pretendard Variable", "Noto Sans KR", sans-serif;
            font-size: 11px;
            font-weight: 620;
            color: #0f2a4d;
            background: #eaf2ff;
            border: 1px solid #c6dbff;
            border-radius: 999px;
            padding: 4px 10px;
        }
        </style>
        <div class="policy-studio-wrap">
            <p class="policy-studio-title">추천 옵션 스튜디오</p>
            <p class="policy-studio-desc">팀별 기준을 먼저 선택한 뒤 적용하면, 추천 목록이 즉시 재생성됩니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    content_key, content_label = _find_content_team_key_and_label()
    has_design = any(k == "design" for k, _, _ in ACTION_PLAN_TEAMS)
    design_label = next((label for k, label, _ in ACTION_PLAN_TEAMS if k == "design"), "디자인팀")

    st.markdown(
        f"""
        <div class="policy-chip-row">
            <span class="policy-chip">콘텐츠 모드: {content_mode_options.get(st.session_state.content_policy_mode, "혼합")}</span>
            <span class="policy-chip">콘텐츠 상한: {content_price_cap_options.get(st.session_state.content_price_cap, "자동")}</span>
            <span class="policy-chip">디자인 모드: {design_mode_options.get(st.session_state.design_policy_mode, "혼합")}</span>
            <span class="policy-chip">디자인 PM: {design_tier_options.get(st.session_state.design_pm_tier, "자동")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_content, col_design = st.columns(2)

    with col_content:
        st.markdown(
            """
            <div class="policy-team-card">
                <p class="policy-team-title">콘텐츠팀 옵션</p>
                <p class="policy-team-sub">이월/계약 기반 대체상품 추천 기준</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.selectbox(
            "콘텐츠 추천 모드",
            options=list(content_mode_options.keys()),
            format_func=lambda x: content_mode_options[x],
            key="content_policy_mode",
        )
        st.selectbox(
            "가격 상한",
            options=list(content_price_cap_options.keys()),
            format_func=lambda x: content_price_cap_options[x],
            key="content_price_cap",
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox("20만원 예외 포함", key="content_include_20")
        with c2:
            st.checkbox("서비스(맘카페) 포함", key="content_include_service")
        with c3:
            st.checkbox("특례 1:2 적용", key="content_apply_special_ratio")
        if st.button("콘텐츠팀 옵션 적용", use_container_width=True, key="content_policy_apply_btn"):
            if content_key:
                items = _normalize_product_items(st.session_state.action_plan_items)
                items[content_key] = _product_items_for_team(filtered_results, content_key, content_label)
                st.session_state.action_plan_items = items
                st.rerun()
            else:
                st.info("현재 팀 목록에서 콘텐츠팀을 찾지 못했습니다.")

    with col_design:
        st.markdown(
            """
            <div class="policy-team-card">
                <p class="policy-team-title">디자인팀 옵션</p>
                <p class="policy-team-sub">이월치환/PM 제안 추천 기준</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.selectbox(
            "디자인 추천 모드",
            options=list(design_mode_options.keys()),
            format_func=lambda x: design_mode_options[x],
            key="design_policy_mode",
        )
        st.selectbox(
            "PM 티어",
            options=list(design_tier_options.keys()),
            format_func=lambda x: design_tier_options[x],
            key="design_pm_tier",
        )
        st.checkbox("20만원 예외 포함", key="design_include_20")
        if st.button("디자인팀 옵션 적용", use_container_width=True, key="design_policy_apply_btn"):
            if has_design:
                items = _normalize_product_items(st.session_state.action_plan_items)
                items["design"] = _product_items_for_team(filtered_results, "design", design_label)
                st.session_state.action_plan_items = items
                st.rerun()
            else:
                st.info("현재 팀 목록에서 디자인팀을 찾지 못했습니다.")

    _, all_apply_col = st.columns([5.2, 1.8])
    with all_apply_col:
        if st.button("전체 옵션 적용", use_container_width=True, key="all_policy_apply_btn"):
            items = _normalize_product_items(st.session_state.action_plan_items)
            if content_key:
                items[content_key] = _product_items_for_team(filtered_results, content_key, content_label)
            if has_design:
                items["design"] = _product_items_for_team(filtered_results, "design", design_label)
            st.session_state.action_plan_items = items
            st.rerun()

    _render_action_plan_editor_core(filtered_results)


def _extract_dashboard_period_label(results: dict) -> str:
    try:
        blog = (results or {}).get("blog", {})
        monthly = blog.get("clean_data", {}).get("work", {}).get("monthly_summary", [])
        labels = []
        for row in monthly if isinstance(monthly, list) else []:
            if isinstance(row, dict) and row.get("month"):
                labels.append(str(row.get("month")))
        if len(labels) >= 2:
            return f"{labels[-2]} ~ {labels[-1]}"
        if len(labels) == 1:
            return labels[-1]
    except Exception:
        pass
    return "현재 분석 기간"


def _inject_report_shell_style():
    st.markdown(
        """
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
        :root {
            --report-bg: #f4f6fa;
            --report-card: #ffffff;
            --report-border: #dde4ee;
            --report-text-strong: #182b47;
            --report-text-muted: #60708a;
            --report-accent: #2b67f6;
            --report-accent-soft: #e7efff;
        }
        html, body, [class*="css"]  {
            font-family: "Pretendard Variable", "Noto Sans KR", sans-serif;
        }
        .stApp {
            background: linear-gradient(180deg, #f8fafe 0%, var(--report-bg) 100%);
        }
        .main .block-container {
            max-width: 1240px;
            padding-top: 1.1rem;
            padding-bottom: 2rem;
        }
        [data-testid="stSidebar"] {
            background: #f8fafc;
            border-right: 1px solid var(--report-border);
        }
        [data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
        }
        .report-topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid var(--report-border);
            background: var(--report-card);
            border-radius: 14px;
            padding: 10px 14px;
            margin-bottom: 10px;
        }
        .report-brand {
            font-size: 18px;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: var(--report-text-strong);
        }
        .report-meta {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .report-pill {
            font-size: 12px;
            color: #17407d;
            background: #edf4ff;
            border: 1px solid #cfe0ff;
            border-radius: 999px;
            padding: 5px 10px;
            font-weight: 640;
        }
        .report-avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #2f6dff;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 760;
        }
        .report-profile {
            display: flex;
            align-items: center;
            gap: 12px;
            border: 1px solid var(--report-border);
            background: var(--report-card);
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 14px;
        }
        .report-profile-name {
            font-size: 30px;
            line-height: 1.1;
            color: #12345f;
            font-weight: 790;
            letter-spacing: -0.02em;
            margin: 0;
        }
        .report-profile-sub {
            font-size: 12px;
            color: var(--report-text-muted);
            margin: 0;
            font-weight: 620;
        }
        .report-side-card {
            border: 1px solid var(--report-border);
            background: #ffffff;
            border-radius: 12px;
            padding: 12px 12px 10px 12px;
            margin-bottom: 10px;
        }
        .report-side-title {
            font-size: 12px;
            font-weight: 740;
            color: #173b6a;
            margin: 0 0 6px 0;
            letter-spacing: -0.01em;
        }
        .report-side-item {
            font-size: 11px;
            color: #5b7091;
            margin: 0 0 4px 0;
        }
        [data-testid="stMetric"] {
            border: 1px solid var(--report-border);
            border-radius: 12px;
            background: var(--report-card);
            padding: 11px 12px;
        }
        [data-testid="stMetricLabel"] {
            color: var(--report-text-muted);
            font-size: 12px;
            font-weight: 620;
        }
        [data-testid="stMetricValue"] {
            color: #15355f;
            font-weight: 780;
        }
        div[data-testid="stExpander"] details {
            border: 1px solid var(--report-border);
            border-radius: 12px;
            background: #fff;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--report-border);
            border-radius: 12px;
            overflow: hidden;
            background: #fff;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            border-bottom: 1px solid var(--report-border);
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px 10px 0 0;
            height: 38px;
            padding: 0 14px;
            border: 1px solid transparent;
            color: #60708a;
            font-weight: 640;
        }
        .stTabs [aria-selected="true"] {
            background: #ffffff;
            color: #204884;
            border-color: var(--report-border);
            border-bottom-color: #ffffff;
        }
        .stButton > button {
            border-radius: 10px;
            border: 1px solid #cfd8e6;
            background: #ffffff;
            color: #1e3a62;
            font-weight: 640;
        }
        .stButton > button:hover {
            border-color: #9fb8e5;
            color: #194381;
        }
        hr {
            border-color: #e4eaf3 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_report_shell_header():
    results = st.session_state.get("analysis_results", {}) or {}
    display_name = (
        st.session_state.get("report_owner_name")
        or st.session_state.get("manager_name")
        or "리포트 담당자"
    )
    period_label = _extract_dashboard_period_label(results)
    initial = str(display_name)[0] if str(display_name) else "리"

    st.markdown(
        f"""
        <div class="report-topbar">
            <div class="report-brand">CLAP REPORT</div>
            <div class="report-meta">
                <span class="report-pill">{period_label}</span>
                <span class="report-avatar">{initial}</span>
            </div>
        </div>
        <div class="report-profile">
            <div class="report-avatar" style="width:44px;height:44px;font-size:18px;">{initial}</div>
            <div>
                <p class="report-profile-name">{display_name}</p>
                <p class="report-profile-sub">PERFORMANCE ANALYSIS REPORT</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            """
            <div class="report-side-card">
                <p class="report-side-title">리포트 구성</p>
                <p class="report-side-item">1. 성과 요약</p>
                <p class="report-side-item">2. 팀별 액션 제안</p>
                <p class="report-side-item">3. KPI/원인 분석</p>
                <p class="report-side-item">4. 실행 계획</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


_render_dashboard_core = render_dashboard


def render_dashboard():
    _inject_report_shell_style()
    _render_report_shell_header()
    _render_dashboard_core()


def _inject_report_shell_style_v2():
    st.markdown(
        """
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
        :root {
            --ui-bg: #f3f5f8;
            --ui-card: #ffffff;
            --ui-border: #dde3ec;
            --ui-text: #1d2a3b;
            --ui-muted: #6a7789;
            --ui-primary: #3867f4;
            --ui-primary-soft: #e9eeff;
            --ui-success: #18a874;
            --status-progress: #14a06f;
            --status-pending: #7f8ca0;
            --status-alert: #e57a12;
            --status-danger: #d64545;
        }
        html, body, [class*="css"] {
            font-family: "Pretendard Variable", "Noto Sans KR", sans-serif;
        }
        .stApp {
            background: var(--ui-bg);
        }
        .main .block-container {
            max-width: 1280px;
            padding-top: 0.72rem;
            padding-bottom: 1.8rem;
            padding-left: 1.08rem;
            padding-right: 1.08rem;
        }
        [data-testid="stSidebar"] {
            background: #f8fafc;
            border-right: 1px solid var(--ui-border);
        }
        [data-testid="stSidebar"] .block-container {
            padding-top: 0.78rem;
            padding-left: 0.72rem;
            padding-right: 0.72rem;
        }
        .clap-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            border: 1px solid var(--ui-border);
            border-radius: 12px;
            background: var(--ui-card);
            padding: 9px 14px;
            margin-bottom: 8px;
        }
        .clap-logo {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #0f2139;
            font-size: 25px;
            font-weight: 820;
            letter-spacing: -0.02em;
            margin: 0;
        }
        .clap-logo-mark {
            width: 18px;
            height: 18px;
            border-radius: 4px;
            background: linear-gradient(135deg, #2d66f3 0%, #3fd0b6 100%);
            transform: skewX(-8deg);
        }
        .clap-top-right {
            display: flex;
            align-items: center;
            gap: 7px;
        }
        .clap-pill {
            border: 1px solid #d4dced;
            background: #f8fbff;
            color: #334d73;
            font-size: 11px;
            font-weight: 650;
            border-radius: 999px;
            padding: 5px 9px;
        }
        .clap-icon-btn {
            width: 30px;
            height: 30px;
            border-radius: 999px;
            border: 1px solid #d2d9e8;
            background: #ffffff;
            color: #324968;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 760;
        }
        .clap-avatar {
            width: 30px;
            height: 30px;
            border-radius: 999px;
            background: #3d63f3;
            color: #ffffff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 760;
        }
        .clap-hero {
            border: 1px solid var(--ui-border);
            border-radius: 12px;
            background: var(--ui-card);
            padding: 14px 16px 12px 16px;
            margin-bottom: 10px;
        }
        .clap-hero-subline {
            margin: 0 0 5px 0;
            color: #7b8798;
            font-size: 11px;
            font-weight: 640;
        }
        .clap-hero-row {
            display: flex;
            align-items: center;
            gap: 11px;
        }
        .clap-hero-avatar {
            width: 44px;
            height: 44px;
            border-radius: 999px;
            background: linear-gradient(135deg, #2dcf98 0%, #2d66f3 100%);
            color: #ffffff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: 820;
        }
        .clap-hero-name {
            margin: 0;
            color: #16263c;
            font-size: 42px;
            line-height: 1.03;
            font-weight: 830;
            letter-spacing: -0.02em;
        }
        .clap-hero-role {
            margin: 0;
            color: #63748c;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.04em;
        }
        .clap-tabs {
            margin-top: 9px;
            border-top: 1px solid #e6ebf3;
            padding-top: 9px;
            display: flex;
            gap: 14px;
            font-size: 12px;
            font-weight: 710;
        }
        .clap-tab-item {
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }
        .clap-tab-dot {
            width: 14px;
            height: 14px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 8px;
            font-weight: 800;
            color: #fff;
        }
        .clap-tab-dot.sum { background: #2f66f0; }
        .clap-tab-dot.note { background: #a7b4c7; }
        .clap-tab-on {
            color: #2d5ef0;
            position: relative;
        }
        .clap-tab-on::after {
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            bottom: -8px;
            height: 2px;
            background: #2d5ef0;
            border-radius: 999px;
        }
        .clap-tab-off {
            color: #7b8698;
        }
        .clap-side-brand {
            margin: 0 0 10px 0;
            font-size: 22px;
            font-weight: 840;
            letter-spacing: -0.02em;
            color: #11243f;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .clap-side-group {
            margin: 0 0 9px 0;
            padding: 0;
        }
        .clap-side-title {
            margin: 0 0 6px 0;
            font-size: 11px;
            color: #7a8699;
            font-weight: 720;
            letter-spacing: 0.01em;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }
        .ui-ico {
            width: 14px;
            height: 14px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 8px;
            font-weight: 800;
            color: #fff;
            flex-shrink: 0;
        }
        .ui-ico.growth { background: #2e66ef; }
        .ui-ico.self { background: #17a073; }
        .ui-ico.analytics { background: #e08a17; }
        .ui-ico.settings { background: #8b98ac; }
        .ui-ico.menu {
            width: 11px;
            height: 11px;
            border-radius: 3px;
            font-size: 0;
            background: linear-gradient(135deg, #2d66f3 0%, #3fd0b6 100%);
            transform: skewX(-8deg);
        }
        .clap-side-item {
            margin: 0 0 5px 0;
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 6px 8px 6px 8px;
            color: #3d4d64;
            font-size: 12px;
            font-weight: 640;
            background: transparent;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .clap-side-item::before {
            content: "";
            width: 6px;
            height: 6px;
            border-radius: 999px;
            background: #cad4e4;
        }
        .clap-side-item.active {
            color: #244c9c;
            background: #eaf1ff;
            border-color: #ccdafb;
            font-weight: 710;
        }
        .clap-side-item.active::before {
            background: #2e66ef;
        }
        [data-testid="stMetric"] {
            border: 1px solid var(--ui-border);
            border-radius: 11px;
            background: var(--ui-card);
            padding: 9px 11px;
            box-shadow: 0 1px 0 rgba(20, 40, 80, 0.02);
        }
        [data-testid="stMetricLabel"] {
            color: var(--ui-muted);
            font-size: 11px;
            font-weight: 640;
        }
        [data-testid="stMetricValue"] {
            color: #173355;
            font-weight: 800;
            letter-spacing: -0.01em;
            font-size: 1.45rem;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--ui-border);
            border-radius: 11px;
            overflow: hidden;
            background: #fff;
        }
        div[data-testid="stExpander"] details {
            border: 1px solid var(--ui-border);
            border-radius: 11px;
            background: #fff;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 7px;
            border-bottom: 1px solid #dbe2ed;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 9px 9px 0 0;
            border: 1px solid transparent;
            color: #6b788a;
            font-weight: 680;
            height: 36px;
            padding: 0 13px;
            font-size: 12px;
        }
        .stTabs [aria-selected="true"] {
            background: #ffffff;
            color: #274e9b;
            border-color: #dbe2ed;
            border-bottom-color: #ffffff;
        }
        .stTabs [data-baseweb="tab"]:nth-child(1)::before,
        .stTabs [data-baseweb="tab"]:nth-child(2)::before,
        .stTabs [data-baseweb="tab"]:nth-child(3)::before {
            display: inline-block;
            margin-right: 5px;
            font-size: 11px;
            font-weight: 800;
            color: #73839a;
        }
        .stTabs [data-baseweb="tab"]:nth-child(1)::before { content: "■"; color: #2f66f0; }
        .stTabs [data-baseweb="tab"]:nth-child(2)::before { content: "■"; color: #18a874; }
        .stTabs [data-baseweb="tab"]:nth-child(3)::before { content: "■"; color: #e08a17; }
        .stButton > button {
            border-radius: 10px;
            border: 1px solid #ced8e9;
            background: #fff;
            color: #274061;
            font-weight: 680;
        }
        .stButton > button:hover {
            border-color: #94b0dc;
            color: #214c93;
        }
        hr {
            border-color: #e3e9f2 !important;
        }
        [data-baseweb="notification"] {
            border-radius: 11px !important;
            border: 1px solid #dbe2ed !important;
        }
        @media (max-width: 1180px) {
            .main .block-container {
                padding-left: 0.9rem;
                padding-right: 0.9rem;
            }
            .clap-hero-name { font-size: 34px; }
            .clap-hero { padding: 13px 14px 11px 14px; }
        }
        @media (max-width: 920px) {
            .main .block-container {
                padding-left: 0.75rem;
                padding-right: 0.75rem;
                padding-top: 0.55rem;
            }
            .clap-topbar {
                padding: 8px 10px;
                border-radius: 10px;
            }
            .clap-logo { font-size: 22px; }
            .clap-pill {
                font-size: 10px;
                padding: 4px 8px;
            }
            .clap-icon-btn {
                width: 27px;
                height: 27px;
                font-size: 10px;
            }
            .clap-avatar {
                width: 27px;
                height: 27px;
                font-size: 11px;
            }
            .clap-hero { border-radius: 10px; }
            .clap-hero-name { font-size: 30px; }
            .clap-hero-avatar {
                width: 40px;
                height: 40px;
                font-size: 16px;
            }
            .clap-tabs {
                gap: 10px;
                overflow-x: auto;
                white-space: nowrap;
                padding-bottom: 2px;
            }
            [data-testid="stSidebar"] {
                min-width: 0 !important;
                max-width: 0 !important;
            }
        }
        @media (max-width: 640px) {
            .main .block-container {
                padding-left: 0.55rem;
                padding-right: 0.55rem;
                padding-top: 0.45rem;
            }
            .clap-top-right .clap-icon-btn { display: none; }
            .clap-top-right { gap: 6px; }
            .clap-hero-name { font-size: 25px; }
            .clap-hero-role { font-size: 10px; }
            .clap-hero-subline { font-size: 10px; }
            .clap-tab-item { gap: 4px; }
            .clap-tab-dot {
                width: 12px;
                height: 12px;
                font-size: 7px;
            }
            .stTabs [data-baseweb="tab"] {
                height: 34px;
                padding: 0 10px;
                font-size: 11px;
            }
            [data-testid="stMetricValue"] {
                font-size: 1.2rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_report_sidebar_v2():
    with st.sidebar:
        st.markdown(
            """
            <p class="clap-side-brand"><span class="ui-ico menu"></span>CLAP</p>
            <div class="clap-side-group">
                <p class="clap-side-title"><span class="ui-ico growth">•</span>팀의 성장</p>
                <p class="clap-side-item active">팀의 계약 리포트</p>
                <p class="clap-side-item">미팅 관리</p>
            </div>
            <div class="clap-side-group">
                <p class="clap-side-title"><span class="ui-ico self">•</span>나의 성장</p>
                <p class="clap-side-item">나의 1:1</p>
                <p class="clap-side-item">나의 피드백</p>
                <p class="clap-side-item">나의 리뷰</p>
            </div>
            <div class="clap-side-group">
                <p class="clap-side-title"><span class="ui-ico analytics">•</span>애널리틱스</p>
                <p class="clap-side-item">나의 대시보드</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_report_shell_header_v2():
    results = st.session_state.get("analysis_results", {}) or {}
    display_name = (
        st.session_state.get("report_owner_name")
        or st.session_state.get("manager_name")
        or "리포트 담당자"
    )
    period_label = _extract_dashboard_period_label(results)
    initial = str(display_name)[0] if str(display_name) else "리"

    st.markdown(
        f"""
        <div class="clap-topbar">
            <p class="clap-logo"><span class="clap-logo-mark"></span>CLAP</p>
            <div class="clap-top-right">
                <span class="clap-pill">{period_label}</span>
                <span class="clap-icon-btn">N</span>
                <span class="clap-avatar">{initial}</span>
            </div>
        </div>
        <div class="clap-hero">
            <p class="clap-hero-subline">팀 계약 리포트 1:1</p>
            <div class="clap-hero-row">
                <span class="clap-hero-avatar">{initial}</span>
                <div>
                    <p class="clap-hero-name">{display_name}</p>
                    <p class="clap-hero-role">PERFORMANCE REPORT</p>
                </div>
            </div>
            <div class="clap-tabs">
                <span class="clap-tab-item clap-tab-on"><span class="clap-tab-dot sum">•</span>성과 요약</span>
                <span class="clap-tab-item clap-tab-off"><span class="clap-tab-dot note">•</span>미팅 노트</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


_render_dashboard_core_v2 = _render_dashboard_core


def render_dashboard():
    _inject_report_shell_style_v2()
    _render_report_sidebar_v2()
    _render_report_shell_header_v2()
    _render_dashboard_core_v2()


def _inject_report_shell_style_v3():
    st.markdown(
        """
        <style>
        :root {
            --detail-card-border: #d9e1ec;
            --detail-card-bg: #ffffff;
            --detail-muted: #6b7a8f;
            --detail-strong: #1a2c47;
            --detail-line: #e6ebf3;
            --detail-green: #17a673;
            --detail-gray: #8a97aa;
        }
        .main .block-container {
            padding-top: 0.65rem;
        }
        [data-testid="stSidebar"] {
            min-width: 236px;
            max-width: 236px;
        }
        h1, h2, h3, h4, h5 {
            color: var(--detail-strong) !important;
            letter-spacing: -0.01em;
        }
        .stMarkdown p, .stCaption {
            color: var(--detail-muted);
        }
        .stTabs [data-baseweb="tab-panel"] {
            background: var(--detail-card-bg);
            border: 1px solid var(--detail-card-border);
            border-radius: 0 12px 12px 12px;
            padding: 13px 13px 10px 13px;
            margin-top: -1px;
        }
        .stSelectbox > div > div,
        .stTextInput > div > div,
        .stTextArea textarea,
        .stDateInput > div > div {
            border-radius: 10px !important;
            border-color: #d4ddea !important;
            background: #ffffff !important;
        }
        .stCheckbox label p {
            color: #475a74 !important;
            font-size: 12px !important;
            font-weight: 600 !important;
        }
        .report-action-card {
            border: 1px solid var(--detail-card-border);
            border-radius: 12px;
            background: var(--detail-card-bg);
            padding: 11px 13px;
            margin-bottom: 10px;
        }
        .report-action-title {
            margin: 0 0 7px 0;
            color: #1c2f4e;
            font-size: 14px;
            font-weight: 760;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .report-title-dot {
            width: 14px;
            height: 14px;
            border-radius: 999px;
            background: #2f66f0;
            color: #fff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 8px;
            font-weight: 800;
        }
        .report-chip-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }
        .report-chip {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
            border: 1px solid transparent;
        }
        .report-chip.green {
            background: #e9f9f2;
            color: var(--status-progress);
            border-color: #bdebd7;
        }
        .report-chip.gray {
            background: #f1f4f8;
            color: var(--status-pending);
            border-color: #d5dee9;
        }
        .report-chip.alert {
            background: #fff3e4;
            color: var(--status-alert);
            border-color: #ffd8ab;
        }
        .report-list {
            border: 1px solid var(--detail-line);
            border-radius: 10px;
            overflow: hidden;
        }
        .report-row {
            display: grid;
            grid-template-columns: 20px 1fr auto;
            gap: 8px;
            align-items: center;
            padding: 9px 10px;
            border-bottom: 1px solid var(--detail-line);
            background: #ffffff;
        }
        .report-row:last-child {
            border-bottom: none;
        }
        .report-box {
            width: 12px;
            height: 12px;
            border: 1.5px solid #a8b5c8;
            border-radius: 3px;
            background: #fff;
        }
        .report-box.checked {
            background: #2f6bf1;
            border-color: #2f6bf1;
            box-shadow: inset 0 0 0 2px #ffffff;
        }
        .report-row-title {
            margin: 0;
            color: #283a54;
            font-size: 12px;
            font-weight: 620;
            line-height: 1.35;
        }
        .report-row-tag {
            font-size: 10px;
            color: #476086;
            background: #edf3ff;
            border: 1px solid #d2def8;
            border-radius: 999px;
            padding: 2px 8px;
            font-weight: 700;
        }
        .report-row-tag.done {
            color: #0f8a60;
            background: #ebf9f2;
            border-color: #c2ecd9;
        }
        .report-row-tag.wait {
            color: #6d7f95;
            background: #f1f4f8;
            border-color: #d8e0ea;
        }
        .report-meta-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 8px;
        }
        .report-meta-item {
            border: 1px solid var(--detail-line);
            border-radius: 10px;
            background: #fbfcfe;
            padding: 8px 10px;
        }
        .report-meta-k {
            margin: 0;
            color: #7a8698;
            font-size: 10px;
            font-weight: 700;
        }
        .report-meta-v {
            margin: 2px 0 0 0;
            color: #203651;
            font-size: 12px;
            font-weight: 700;
        }
        .report-divider {
            border-bottom: 1px dashed #d9e1ed;
            margin: 8px 0 12px 0;
        }
        @media (max-width: 920px) {
            [data-testid="stSidebar"] {
                min-width: 0 !important;
                max-width: 0 !important;
            }
            .stTabs [data-baseweb="tab-panel"] {
                padding: 10px 10px 8px 10px;
            }
            .report-action-card {
                padding: 9px 10px;
                border-radius: 10px;
            }
            .report-chip-wrap {
                flex-wrap: wrap;
                gap: 6px;
            }
            .report-row {
                grid-template-columns: 16px 1fr auto;
                padding: 8px 8px;
            }
            .report-row-title {
                font-size: 11px;
            }
            .report-meta-grid {
                grid-template-columns: 1fr;
            }
        }
        @media (max-width: 640px) {
            .report-action-title {
                font-size: 13px;
            }
            .report-row {
                grid-template-columns: 15px 1fr;
            }
            .report-row-tag {
                display: none;
            }
            .report-meta-item {
                padding: 7px 9px;
            }
            .report-meta-v {
                font-size: 11px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _collect_action_item_preview(max_rows: int = 4):
    raw_items = st.session_state.get("action_plan_items", {})
    if not isinstance(raw_items, dict):
        return [], 0, 0

    try:
        items = _normalize_product_items(raw_items)
    except Exception:
        items = raw_items

    rows = []
    total = 0
    checked = 0

    for dept_key, dept_label, _ in ACTION_PLAN_TEAMS:
        team_items = items.get(dept_key, [])
        if not isinstance(team_items, list):
            continue
        for item in team_items:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "")).strip()
            if not title:
                text = str(item.get("text", "")).strip()
                if text:
                    title = text.splitlines()[0].strip()
            if not title:
                continue

            is_checked = bool(item.get("selected", True))
            total += 1
            if is_checked:
                checked += 1

            if len(rows) < max_rows:
                rows.append({"team": dept_label, "title": title, "checked": is_checked})

    return rows, total, checked


def _render_report_context_bar_v3():
    results = st.session_state.get("analysis_results", {}) or {}
    period_label = _extract_dashboard_period_label(results)
    rows, total_count, checked_count = _collect_action_item_preview(max_rows=4)
    pending = max(total_count - checked_count, 0)

    selected_months = st.session_state.get("selected_months", [])
    month_label = ", ".join([str(x) for x in selected_months[:3]]) if selected_months else period_label
    if selected_months and len(selected_months) > 3:
        month_label += f" 외 {len(selected_months)-3}개"

    selected_depts = st.session_state.get("selected_departments", [])
    dept_label = ", ".join([str(x) for x in selected_depts[:3]]) if selected_depts else "전체 팀"
    if selected_depts and len(selected_depts) > 3:
        dept_label += f" 외 {len(selected_depts)-3}개"

    def esc(x):
        return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if rows:
        row_html = []
        for r in rows:
            checked_cls = "report-box checked" if r.get("checked") else "report-box"
            tag_cls = "report-row-tag done" if r.get("checked") else "report-row-tag wait"
            row_html.append(
                f"""
                <div class="report-row">
                    <span class="{checked_cls}"></span>
                    <p class="report-row-title">{esc(r.get("title", ""))}</p>
                    <span class="{tag_cls}">{esc(r.get("team", ""))}</span>
                </div>
                """
            )
        rows_block = "\n".join(row_html)
    else:
        import textwrap
        rows_block = textwrap.dedent("""
        <div class="report-row">
            <span class="report-box"></span>
            <p class="report-row-title">액션 아이템이 아직 생성되지 않았습니다. 분석 범위를 선택하면 자동 생성됩니다.</p>
            <span class="report-row-tag">안내</span>
        </div>
        """).strip()

    import textwrap
    expander_title = f"📌 약속한 액션 아이템 (진행중 {checked_count} / 대기 {pending} / 전체 {total_count})"
    with st.expander(expander_title, expanded=False):
        import textwrap
        html_content = textwrap.dedent(f"""
        <div class="report-action-card" style="box-shadow:none; padding:0; background:transparent; border:none; margin-top:0;">
            <div class="report-list">
                {rows_block}
            </div>
            <div class="report-divider"></div>
            <div class="report-meta-grid">
                <div class="report-meta-item">
                    <p class="report-meta-k">데이터 기간</p>
                    <p class="report-meta-v">{esc(month_label)}</p>
                </div>
                <div class="report-meta-item">
                    <p class="report-meta-k">분석 팀 범위</p>
                    <p class="report-meta-v">{esc(dept_label)}</p>
                </div>
            </div>
        </div>
        """).strip()
        
        st.markdown(html_content, unsafe_allow_html=True)


def _inject_toss_button_style():
    st.markdown(
        """
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
        :root {
            --toss-bg: #f3f6fb;
            --toss-card: #ffffff;
            --toss-border: #dbe6f3;
            --toss-text: #111827;
            --toss-text-muted: #617089;
            --toss-primary: #2563eb;
            --toss-primary-strong: #1d4ed8;
            --toss-primary-soft: #eaf2ff;
            --toss-shadow: 0 10px 28px -18px rgba(37, 99, 235, 0.45);
            --toss-shadow-hover: 0 14px 28px -16px rgba(37, 99, 235, 0.45);
        }
        html, body, [class*="css"] {
            font-family: "Pretendard Variable", "Noto Sans KR", -apple-system, sans-serif !important;
        }
        .stApp {
            background: var(--toss-bg) !important;
        }
        .main .block-container {
            max-width: 1240px !important;
            padding-top: 0.9rem !important;
            padding-bottom: 1.8rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        [data-testid="stSidebar"] {
            min-width: 250px !important;
            background: #ffffff !important;
            border-right: 1px solid var(--toss-border) !important;
        }
        [data-testid="stSidebar"] .block-container {
            padding-top: 0.85rem !important;
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
        }
        [data-testid="stHeader"] {
            background: transparent !important;
        }
        #MainMenu, footer {
            visibility: hidden !important;
        }
        .stButton > button,
        .stDownloadButton > button {
            min-height: 42px !important;
            border-radius: 12px !important;
            border: 1px solid transparent !important;
            background: linear-gradient(180deg, #3b82f6 0%, #2f6ef2 100%) !important;
            color: #ffffff !important;
            font-size: 15px !important;
            font-weight: 740 !important;
            letter-spacing: -0.01em !important;
            box-shadow: var(--toss-shadow) !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease !important;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            transform: translateY(-1px) !important;
            background: linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%) !important;
            box-shadow: var(--toss-shadow-hover) !important;
        }
        .stButton > button:active,
        .stDownloadButton > button:active {
            transform: translateY(0px) !important;
            box-shadow: inset 0 2px 0 rgba(15, 23, 42, 0.12) !important;
            background: linear-gradient(180deg, #1d4ed8 0%, #1e40af 100%) !important;
        }
        .stButton > button:disabled,
        .stDownloadButton > button:disabled {
            background: #cbd5e1 !important;
            border-color: #94a3b8 !important;
            color: #475569 !important;
            box-shadow: none !important;
            cursor: not-allowed !important;
        }
        .stButton > button[kind="secondary"],
        .stButton > button[kind="secondary"]:hover {
            background: #ffffff !important;
            border: 1px solid #d2dced !important;
            color: #1e3a8a !important;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(180deg, var(--toss-primary) 0%, var(--toss-primary-strong) 100%) !important;
        }
        .stFileUploader {
            border-radius: 14px !important;
        }
        [data-testid="stFileUploader"] {
            border: 1px dashed #bfd7ff !important;
            background: #ffffff !important;
            border-radius: 14px !important;
            padding: 1.5rem 1rem !important;
        }
        [data-testid="stFileUploader"] section {
            padding: 0.7rem !important;
        }
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        [data-testid="stTextInput"] > div > div,
        [data-testid="stTextArea"] textarea,
        [data-testid="stDateInput"] input,
        [data-testid="stSelectbox"] > div > div,
        [data-testid="stNumberInput"] > div > div {
            border-radius: 10px !important;
            border-color: var(--toss-border) !important;
            background: #ffffff !important;
        }
        [data-testid="stSelectbox"] > div {
            min-height: 42px !important;
        }
        [data-testid="stAlert"] {
            border-radius: 11px !important;
            border: 1px solid #dbeafe !important;
            background: #eff6ff !important;
        }
        [data-testid="stTabs"] {
            margin-top: 0.1rem !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px !important;
            padding: 4px !important;
            border-radius: 12px !important;
            background: #ffffff !important;
            border: 1px solid var(--toss-border) !important;
            margin-bottom: 0.85rem !important;
        }
        .stTabs [data-baseweb="tab"] {
            height: 40px !important;
            border-radius: 10px !important;
            padding: 0 15px !important;
            border: 1px solid transparent !important;
            color: #4f5f76 !important;
            font-weight: 680 !important;
            font-size: 13px !important;
        }
        .stTabs [data-baseweb="tab"]:hover {
            border-color: #bfdbfe !important;
            color: #1e40af !important;
        }
        .stTabs [aria-selected="true"] {
            color: #1d4ed8 !important;
            background: #eff6ff !important;
            border-color: #bfdbfe !important;
            font-weight: 760 !important;
        }
        .stTab [data-baseweb="tab-highlight"] {
            display: none !important;
        }
        [data-testid="stExpander"] {
            border: 1px solid #dde7f3 !important;
            border-radius: 12px !important;
            background: #ffffff !important;
            box-shadow: none !important;
        }
        [data-testid="stExpander"] summary {
            padding: 0.9rem 0.9rem 0.75rem 0.9rem !important;
            color: #1f3c67 !important;
            font-weight: 700 !important;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid #dbe7f3 !important;
            border-radius: 12px !important;
            background: #ffffff !important;
        }
        [data-testid="stMetric"] {
            border: 1px solid #d6e2f3 !important;
            border-radius: 12px !important;
            background: #ffffff !important;
            padding: 12px 12px 10px 12px !important;
            box-shadow: 0 4px 12px -12px rgba(30, 64, 175, 0.28) !important;
        }
        [data-testid="stMetricLabel"] {
            color: var(--toss-text-muted) !important;
            font-size: 12px !important;
        }
        [data-testid="stMetricValue"] {
            color: #152f55 !important;
            font-weight: 780 !important;
        }
        .report-topbar,
        .clap-topbar {
            border: 1px solid var(--toss-border) !important;
            border-radius: 14px !important;
            background: #ffffff !important;
            box-shadow: 0 10px 22px -16px rgba(30, 64, 175, 0.35) !important;
        }
        .report-profile,
        .clap-hero,
        .report-action-card,
        .clap-card {
            border: 1px solid var(--toss-border) !important;
            border-radius: 14px !important;
            background: #ffffff !important;
            box-shadow: 0 10px 22px -18px rgba(37, 99, 235, 0.35) !important;
        }
        .report-side-card {
            border: 1px solid var(--toss-border) !important;
            border-radius: 12px !important;
            background: #ffffff !important;
        }
        .report-meta-grid,
        .report-side-item,
        .report-chip-wrap,
        .clap-meta-item {
            color: #4e5e74 !important;
        }
        .clap-pill,
        .report-pill,
        .status-pill {
            color: #1d4ed8 !important;
            background: var(--toss-primary-soft) !important;
            border: 1px solid #bfdbfe !important;
            border-radius: 999px !important;
            padding: 4px 10px !important;
            font-weight: 700 !important;
        }
        .policy-team-card,
        .policy-studio-wrap,
        .policy-studio-wrap *,
        .report-action-title,
        .policy-team-title,
        .policy-team-sub {
            color: #1f3f72 !important;
        }
        .policy-studio-wrap {
            border: 1px solid var(--toss-border) !important;
            border-radius: 14px !important;
            background: linear-gradient(180deg, #f8fbff 0%, #f3f7ff 100%) !important;
            box-shadow: 0 14px 24px -22px rgba(37, 99, 235, 0.4) !important;
        }
        .policy-studio-wrap .policy-chip {
            background: #f0f5ff !important;
            border-color: #bed7ff !important;
            color: #1d3f83 !important;
        }
        .clap-side-group,
        .clap-side-card {
            border: 1px solid var(--toss-border) !important;
            border-radius: 12px !important;
            background: #ffffff !important;
            padding: 10px 11px !important;
            margin-bottom: 8px !important;
        }
        .clap-side-brand {
            color: #163b6c !important;
            font-weight: 820 !important;
        }
        @media (max-width: 768px) {
            .stButton > button,
            .stDownloadButton > button {
                min-height: 44px !important;
            }
            .main .block-container {
                padding-left: 0.75rem !important;
                padding-right: 0.75rem !important;
            }
            .stTabs [data-baseweb="tab-list"] {
                gap: 6px !important;
                overflow-x: auto !important;
                white-space: nowrap !important;
            }
            .stTabs [data-baseweb="tab"] {
                height: 36px !important;
                padding: 0 12px !important;
                font-size: 12px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_render_dashboard_core_v3 = _render_dashboard_core_v2


def render_dashboard():
    _inject_report_shell_style_v2()
    _inject_report_shell_style_v3()
    _render_report_sidebar_v2()
    _render_report_shell_header_v2()
    _render_report_context_bar_v3()
    _render_dashboard_core_v3()


BLOG_UNIT_BUDGET_KRW = 200000.0
COUNT_ONLY_SOURCES = {
    "catalog_fallback",
    "catalog_llm",
    "template",
    "design_carryover_policy",
    "design_pm_policy",
    "marketing_pm_policy",
    "content_carryover_policy",
    "content_contract_policy",
}


def _round_half_up_count(value: float, minimum: int = 1) -> int:
    import math
    try:
        num = float(value)
    except Exception:
        return minimum
    if num != num:  # NaN
        return minimum
    rounded = int(math.floor(num + 0.5))
    return max(minimum, rounded)


def _extract_unit_price_krw(text: str):
    import re
    s = str(text or "")
    m_won = re.search(r"([0-9][0-9,]*)\s*원", s)
    if m_won:
        try:
            return float(m_won.group(1).replace(",", ""))
        except Exception:
            pass

    m_manwon = re.search(r"([0-9][0-9,]*)\s*만원", s)
    if m_manwon:
        try:
            return float(m_manwon.group(1).replace(",", "")) * 10000.0
        except Exception:
            pass
    return None


def _extract_expected_count_from_detail(detail: str):
    import re
    s = str(detail or "")
    m = re.search(r"예상\s*([0-9]+(?:\.[0-9]+)?)\s*건", s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def _estimate_count_by_budget(blog_contract_count: float, unit_price_krw=None, fallback_needed=None) -> int:
    contracts = max(float(blog_contract_count or 0.0), 0.0)
    if unit_price_krw is not None:
        try:
            price = float(unit_price_krw)
        except Exception:
            price = 0.0
        if price > 0:
            budget = contracts * BLOG_UNIT_BUDGET_KRW
            return _round_half_up_count(budget / price, minimum=1)

    if fallback_needed is not None:
        try:
            return _round_half_up_count(float(fallback_needed), minimum=1)
        except Exception:
            pass

    if contracts > 0:
        return _round_half_up_count(contracts, minimum=1)
    return 1


def _count_only_detail_text(count: int) -> str:
    return f"예상 제안 {int(count)}건"


def _to_count_only_item(item: dict, contract_count: float, carryover_count: float):
    source = str(item.get("source", "")).strip()
    if source not in COUNT_ONLY_SOURCES:
        return dict(item)

    title = str(item.get("title", "")).strip()
    detail = str(item.get("detail", "")).strip()
    unit_price = _extract_unit_price_krw(title)
    fallback_needed = _extract_expected_count_from_detail(detail)

    if source in {"design_carryover_policy", "content_carryover_policy"}:
        fallback_needed = float(carryover_count) * 0.5

    count = _estimate_count_by_budget(
        blog_contract_count=contract_count,
        unit_price_krw=unit_price,
        fallback_needed=fallback_needed,
    )

    out = dict(item)
    out["detail"] = _count_only_detail_text(count)
    return out


_catalog_candidates_for_team_with_score = _catalog_candidates_for_team


def _catalog_candidates_for_team(rows: list, dept_key: str, blog_contract_count: float):
    candidates = _catalog_candidates_for_team_with_score(rows, dept_key, blog_contract_count)
    if not candidates:
        return []

    price_map = {}
    for row in rows if isinstance(rows, list) else []:
        item = str(row.get("item", "")).strip()
        category = str(row.get("category", "")).strip()
        if not item:
            continue

        price = _product_safe_float(row.get("price_vat_excl"))
        if price is None or price <= 0:
            price = _product_safe_float(row.get("cost_excl_labor"))
        if price is None or price <= 0:
            price = _extract_unit_price_krw(item)
        if price is None or price <= 0:
            continue

        if item not in price_map:
            price_map[item] = float(price)
        compound = f"{item} ({category})".strip()
        if compound not in price_map:
            price_map[compound] = float(price)

    out = []
    for c in candidates:
        item = str(c.get("item", "")).strip()
        category = str(c.get("category", "")).strip()
        compound = f"{item} ({category})".strip()
        unit_price = _product_safe_float(c.get("unit_price"))
        if unit_price is None:
            unit_price = _product_safe_float(price_map.get(item))
        if unit_price is None:
            unit_price = _product_safe_float(price_map.get(compound))
        if unit_price is None:
            unit_price = _extract_unit_price_krw(item)

        rec = dict(c)
        rec["unit_price"] = float(unit_price) if unit_price is not None else None
        rec["blog_contract_count"] = float(blog_contract_count or 0.0)
        out.append(rec)
    return out


def _fallback_product_items_from_catalog(candidates: list, dept_label: str, max_items: int = 5):
    """Count-only fallback for external exposure."""
    if not candidates:
        return []

    status_rank = {STATUS_AVAILABLE: 0, STATUS_HOLD: 1, STATUS_BLOCKED: 2}
    ordered = sorted(
        candidates,
        key=lambda x: (
            status_rank.get(str(x.get("status", "")).strip(), 3),
            -float(x.get("score", 0)),
            float(x.get("replacement_per_posting", 0)),
        ),
    )

    items = []
    seen = set()
    for c in ordered:
        title = f"{c.get('item', '')} ({c.get('category', '')})".strip()
        if not title or title in seen:
            continue
        seen.add(title)

        count = _estimate_count_by_budget(
            blog_contract_count=float(c.get("blog_contract_count", 0.0)),
            unit_price_krw=_product_safe_float(c.get("unit_price")),
            fallback_needed=_product_safe_float(c.get("estimated_needed_count")),
        )
        items.append(
            {
                "title": title,
                "detail": _count_only_detail_text(count),
                "selected": True,
                "source": "catalog_fallback",
                "team": dept_label,
            }
        )
        if len(items) >= max_items:
            break
    return items


def _product_items_for_team_base(results, dept_key: str, dept_label: str):
    """Count-only product proposal generation for external report/UI exposure."""
    blog_counts = _extract_blog_counts(results)
    blog_contract_count = blog_counts.get("contract_count", 0.0)
    team_kpi = dict(_product_kpi_for_team(results, dept_key) or {})
    team_kpi["blog_contract_count"] = blog_counts.get("contract_count", 0.0)
    team_kpi["blog_carryover_count"] = blog_counts.get("carryover_count", 0.0)

    catalog_rows = _get_replacement_catalog_rows()
    candidates = _catalog_candidates_for_team(catalog_rows, dept_key, blog_contract_count)

    llm_items = []
    if candidates:
        from src.llm.llm_client import generate_team_product_recommendations

        llm_result = generate_team_product_recommendations(
            team_name=dept_label,
            blog_contract_count=blog_contract_count,
            team_kpis=team_kpi,
            all_report_context=_compact_kpi_context(results),
            catalog_candidates=candidates,
            max_items=5,
        )

        unit_price_map = {}
        for c in candidates:
            item_name = str(c.get("item", "")).strip()
            category = str(c.get("category", "")).strip()
            price = _product_safe_float(c.get("unit_price"))
            if price is None:
                continue
            if item_name and item_name not in unit_price_map:
                unit_price_map[item_name] = price
            compound = f"{item_name} ({category})".strip()
            if compound and compound not in unit_price_map:
                unit_price_map[compound] = price

        for rec in llm_result:
            title = str(rec.get("title", "")).strip()
            if not title:
                continue
            source_item = str(rec.get("source_item", "")).strip()
            category = str(rec.get("category", "")).strip()
            compound_source = f"{source_item} ({category})".strip()

            unit_price = _product_safe_float(rec.get("unit_price"))
            if unit_price is None:
                unit_price = _product_safe_float(unit_price_map.get(source_item))
            if unit_price is None:
                unit_price = _product_safe_float(unit_price_map.get(compound_source))
            if unit_price is None:
                unit_price = _product_safe_float(unit_price_map.get(title))
            if unit_price is None:
                unit_price = _extract_unit_price_krw(title)

            needed = _product_safe_float(rec.get("estimated_needed_count"))
            count = _estimate_count_by_budget(
                blog_contract_count=blog_contract_count,
                unit_price_krw=unit_price,
                fallback_needed=needed,
            )

            llm_items.append(
                {
                    "title": title,
                    "detail": _count_only_detail_text(count),
                    "selected": True,
                    "source": "catalog_llm",
                    "team": dept_label,
                }
            )
            if len(llm_items) >= 5:
                break

    items = list(llm_items)
    if len(items) < 5 and candidates:
        fallback = _fallback_product_items_from_catalog(candidates, dept_label, max_items=5)
        seen = {x.get("title", "") for x in items}
        for item in fallback:
            if item.get("title", "") in seen:
                continue
            items.append(item)
            seen.add(item.get("title", ""))
            if len(items) >= 5:
                break

    if len(items) < 5:
        templates = PRODUCT_TEMPLATES.get(dept_key, [])
        seen = {x.get("title", "") for x in items}
        default_count = _estimate_count_by_budget(blog_contract_count, unit_price_krw=None, fallback_needed=blog_contract_count)
        for title, _ in templates:
            if title in seen:
                continue
            items.append(
                {
                    "title": title,
                    "detail": _count_only_detail_text(default_count),
                    "selected": True,
                    "source": "template",
                    "team": dept_label,
                }
            )
            seen.add(title)
            if len(items) >= 5:
                break

    return items[:5]


_build_design_policy_items_with_options_raw = _build_design_policy_items_with_options


def _build_design_policy_items_with_options(blog_counts: dict, dept_label: str, settings: dict):
    raw = _build_design_policy_items_with_options_raw(blog_counts, dept_label, settings)
    contract_count = float(blog_counts.get("contract_count", 0.0))
    carryover_count = float(blog_counts.get("carryover_count", 0.0))
    out = []
    for item in raw:
        out.append(_to_count_only_item(item, contract_count, carryover_count))
    return out


_build_content_policy_items_with_options_raw = _build_content_policy_items_with_options


def _build_content_policy_items_with_options(results: dict, blog_counts: dict, dept_label: str, settings: dict):
    raw = _build_content_policy_items_with_options_raw(results, blog_counts, dept_label, settings)
    contract_count = float(blog_counts.get("contract_count", 0.0))
    carryover_count = float(blog_counts.get("carryover_count", 0.0))
    out = []
    for item in raw:
        out.append(_to_count_only_item(item, contract_count, carryover_count))
    return out


def _sanitize_action_plan_items_count_only(items: dict, results: dict):
    normalized = _normalize_product_items(items if isinstance(items, dict) else {})
    blog_counts = _extract_blog_counts(results or {})
    contract_count = float(blog_counts.get("contract_count", 0.0))
    carryover_count = float(blog_counts.get("carryover_count", 0.0))

    # PM이 "선택 완료"한 팀은 원본 유지 (예상 제안 X건으로 치환 방지)
    confirmed_teams = {
        tk for tk in TEAM_PACKAGE_REGISTRY
        if st.session_state.get(f"{tk}_proposal_done", False)
    }

    out = {}
    for dept_key, _, _ in ACTION_PLAN_TEAMS:
        team_items = normalized.get(dept_key, [])
        if dept_key in confirmed_teams:
            out[dept_key] = team_items
            continue
        team_out = []
        for item in team_items:
            team_out.append(_to_count_only_item(item, contract_count, carryover_count))
        out[dept_key] = team_out
    return out


_render_action_plan_editor_with_options = render_action_plan_editor


def render_action_plan_editor(filtered_results):
    items = st.session_state.action_plan_items if isinstance(st.session_state.action_plan_items, dict) else {}
    sanitized = _sanitize_action_plan_items_count_only(items, filtered_results)
    if sanitized != items:
        st.session_state.action_plan_items = sanitized

    _sync_team_package_registry_from_catalog()

    st.markdown("<h3 style='margin:0 0 10px 0;'>실행계획 제안 카탈로그</h3>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:12px; padding:14px 18px; margin-bottom:16px;">
        <p style="font-size:12px; font-weight:600; color:#1e40af; margin:0; line-height:1.8;">
            <strong>Step 1.</strong> 각 팀별 카드에서 제안할 상품을 선택하세요<br>
            <strong>Step 2.</strong> '선택 완료' 버튼을 눌러 보고서에 반영합니다<br>
            <span style="color:#6b7280;">→ 선택한 상품은 보고서 하단 '실행 계획'에 가격·유형과 함께 표시됩니다</span>
        </p>
    </div>
    """, unsafe_allow_html=True)
    for dept_key, _, _ in ACTION_PLAN_TEAMS:
        if dept_key in TEAM_PACKAGE_REGISTRY:
            _render_team_proposal_flow(dept_key, filtered_results)


def get_action_plan_for_report():
    """Export selected action plans for report — PM 확정 팀만 포함."""
    from src.processors.summary import get_next_month_seasonality
    season_info = get_next_month_seasonality()

    raw_items = st.session_state.action_plan_items if isinstance(st.session_state.action_plan_items, dict) else {}

    # PM이 "선택 완료"한 팀만 보고서에 포함
    confirmed_teams = {
        tk for tk in TEAM_PACKAGE_REGISTRY
        if st.session_state.get(f"{tk}_proposal_done", False)
    }

    action_plan = []
    for dept_key, dept_label, _ in ACTION_PLAN_TEAMS:
        if dept_key not in confirmed_teams:
            continue
        for item in raw_items.get(dept_key, []):
            if not item.get("selected", True):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            # 작업내용(tasks) 목록을 보기 좋게 HTML 포맷
            detail = str(item.get("detail", "")).strip()
            tasks_html = ""
            if "실행:" in detail:
                tasks_part = detail.split("실행:")[-1].strip()
                task_list = [t.strip() for t in tasks_part.split(",") if t.strip()]
                if task_list:
                    tasks_html = " · ".join(task_list)
            plan_text = tasks_html if tasks_html else detail
            # 유형 판별: 이월치환=계약포함, PM제안=추가제안
            source = str(item.get("source", "")).strip()
            mode_type = str(item.get("mode_type", "")).strip()
            if "carryover" in source or mode_type == "carryover":
                type_label = "계약포함"
            else:
                type_label = "추가제안"
            price_val = item.get("price", 0) or 0
            action_plan.append(
                {
                    "department": dept_label,
                    "agenda": f"<strong>{title}</strong>",
                    "plan": plan_text,
                    "price": price_val,
                    "item_type": type_label,
                }
            )

    total_extra_cost = sum(
        ap.get("price", 0) for ap in action_plan if ap.get("item_type") == "추가제안"
    )
    return {
        "action_plan": action_plan,
        "action_plan_month": f"{season_info['month']}월",
        "total_extra_cost": total_extra_cost,
    }


def main():
    """Main application entry point."""
    initialize_session_state()
    st.sidebar.caption(f"버전: {APP_DEPLOY_TAG}")
    _inject_toss_button_style()

    # Show intro animation on first visit
    if 'intro_shown' not in st.session_state:
        st.session_state.intro_shown = True
        render_intro()

    # Mode switcher
    render_mode_switcher()

    # Route to selected mode
    if st.session_state.app_mode == 'marketing':
        if not st.session_state.files_uploaded:
            render_upload_section()
        else:
            render_dashboard()
    elif st.session_state.app_mode == 'feedback':
        if not st.session_state.feedback_file_uploaded:
            render_feedback_upload()
        else:
            render_feedback_dashboard()


if __name__ == "__main__":
    main()
