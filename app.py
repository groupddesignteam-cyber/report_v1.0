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
    process_setting,
    process_feedback
)
from src.reporting.feedback_report import generate_feedback_html_report, get_feedback_report_filename

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
APP_VERSION = "v1.3.0"
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

    # Feedback mode state
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = 'marketing'
    if 'feedback_result' not in st.session_state:
        st.session_state.feedback_result = None
    if 'feedback_file_uploaded' not in st.session_state:
        st.session_state.feedback_file_uploaded = False



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
    st.session_state.selector_confirmed = False
    st.session_state.action_plan_items = {}
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
    ('reservation', '예약', '#3b82f6'),
    ('blog', '블로그', '#10b981'),
    ('youtube', '유튜브', '#ef4444'),
    ('design', '디자인', '#f59e0b'),
    ('ads', '네이버 광고', '#8b5cf6'),
]


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

    # Month Selector
    if available_months:
        st.markdown("""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.25rem; margin-bottom:0.75rem;">
            <div style="font-weight:600; color:#1e293b; font-size:0.95rem; margin-bottom:4px;">분석 기간 선택</div>
            <div style="font-size:0.8rem; color:#64748b;">비교할 월을 선택하세요 (전월 + 당월)</div>
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

    # Department Selector
    st.markdown("""
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.25rem; margin-bottom:0.75rem; margin-top:0.5rem;">
        <div style="font-weight:600; color:#1e293b; font-size:0.95rem; margin-bottom:4px;">분석 항목 선택</div>
        <div style="font-size:0.8rem; color:#64748b;">보고서에 포함할 분석 항목을 선택하세요</div>
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
        "파일 업로드",
        type=['xlsx', 'csv'],
        accept_multiple_files=True,
        key="unified_upload",
        label_visibility="collapsed"
    )

    # Classification preview + action button
    if uploaded_files:
        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
        
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

        # Action Button
        st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
        valid_count = len(uploaded_files) - len(unclassified)
        
        # Primary Action Button
        if valid_count > 0:
            if st.button(f"🚀  데이터 분석 시작 ({valid_count}개 파일)", type="primary", use_container_width=True):
                process_uploaded_files(uploaded_files)
        else:
            st.button("파일을 업로드해주세요", disabled=True, use_container_width=True)



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
        dept_key = None
        for key, label, _ in ACTION_PLAN_TEAMS:
            if label == dept or (dept == '네이버 광고' and key == 'ads'):
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


def render_action_plan_editor():
    """Render editable action plan editor with +/- buttons per team."""
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

        team_items = items.get(dept_key, [])

        # Render existing items
        indices_to_remove = []
        for i, item in enumerate(team_items):
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
        if st.button(f"＋ {dept_label} 코멘트 추가", key=f"ap_add_{dept_key}", type="secondary"):
            if dept_key not in items:
                items[dept_key] = []
            items[dept_key].append({'text': ''})
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

    # Generate HTML report (filtered) with user-edited action plan
    custom_action_plan = get_action_plan_for_report()
    html_report = generate_html_report(
        filtered_results,
        clinic_name=settings['clinic_name'],
        report_date=settings['report_date'],
        manager_comment=st.session_state.get('manager_comment', ''),
        action_plan_override=custom_action_plan
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

    # 3 Tabs: Preview / Data / Action Plan
    tab_preview, tab_data, tab_action = st.tabs(["보고서 미리보기", "데이터 확인 및 수정", "실행 계획 편집"])

    with tab_preview:
        render_html_preview(html_report)

    with tab_data:
        render_unified_data_view(filtered_results)

    with tab_action:
        render_action_plan_editor()

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

        if st.button("분석 시작", type="primary", use_container_width=True):
            loaded = load_uploaded_file(uploaded)
            with st.spinner("피드백 데이터 분석 중..."):
                result = process_feedback([loaded])
            if result.get('error'):
                st.error(result['error'])
            else:
                st.session_state.feedback_result = result
                st.session_state.feedback_file_uploaded = True
                st.rerun()


def render_feedback_dashboard():
    """Render the feedback analysis dashboard."""
    import pandas as pd

    result = st.session_state.feedback_result
    if not result:
        st.warning("분석 결과가 없습니다.")
        return

    overview = result.get('overview', {})

    # Header
    col_title, col_reset = st.columns([4, 1])
    with col_title:
        st.markdown(f"""
        <div style="margin-bottom: 0.25rem;">
            <h1 style="margin-bottom: 0; font-size: 1.4rem; color: #f1f5f9;">고객 피드백 분석 결과</h1>
            <p style="color: #94a3b8; font-size: 0.78rem; margin-top: 2px;">
                응답 {overview.get('response_count', 0)}건
                {(' | ' + overview.get('date_range', '')) if overview.get('date_range') else ''}
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col_reset:
        if st.button("새로 시작", key="fb_reset", use_container_width=True):
            st.session_state.feedback_file_uploaded = False
            st.session_state.feedback_result = None
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


def main():
    """Main application entry point."""
    initialize_session_state()

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