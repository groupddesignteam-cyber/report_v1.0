"""
콘텐츠팀(블로그) 데이터 처리 모듈
- Work CSV: '[콘텐츠팀] 포스팅 업무 현황*.csv'
- Inflow xlsx: '유입분석_월간_*.xlsx'
- Views rank xlsx: '조회수_순위_월간_*.xlsx'
- Views monthly xlsx: '조회수_월간_*.xlsx'

추가 분석 기능:
1. 검색어 심층 분석: URL에서 query/q 파라미터 추출
2. 효자 콘텐츠(스테디셀러) 발굴: 과거 게시물 중 인기글 표시
3. 성과 원인 자동 진단: 조회수 하락 원인 분석
"""

import re
import pandas as pd
import numpy as np
from io import BytesIO
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs, unquote
import warnings
warnings.filterwarnings('ignore')


@dataclass
class LoadedFile:
    name: str
    df: Optional[pd.DataFrame] = None
    raw_bytes: Optional[bytes] = None


def extract_search_keyword_from_url(url: str) -> Optional[str]:
    """
    URL에서 검색 키워드를 추출합니다.
    query=, q=, search=, keyword= 등의 파라미터를 파싱합니다.
    """
    if not url or pd.isna(url):
        return None

    try:
        url_str = str(url).strip()
        if not url_str or url_str.lower() == 'nan':
            return None

        # URL 파싱
        parsed = urlparse(url_str)
        query_params = parse_qs(parsed.query)

        # 검색어 파라미터 우선순위
        search_params = ['query', 'q', 'search', 'keyword', 'searchKeyword', 'where']

        for param in search_params:
            if param in query_params:
                keyword = query_params[param][0]
                # URL 디코딩
                keyword = unquote(keyword)
                # 빈 문자열이 아닌 경우만 반환
                if keyword and keyword.strip():
                    return keyword.strip()

        # 네이버 검색 URL 특수 처리
        if 'naver.com' in url_str:
            # 네이버 검색 결과 URL 패턴
            match = re.search(r'[?&]query=([^&]+)', url_str)
            if match:
                return unquote(match.group(1))

        # 다음 검색 URL 특수 처리
        if 'daum.net' in url_str:
            match = re.search(r'[?&]q=([^&]+)', url_str)
            if match:
                return unquote(match.group(1))

        # 구글 검색 URL 특수 처리
        if 'google.com' in url_str or 'google.co.kr' in url_str:
            match = re.search(r'[?&]q=([^&]+)', url_str)
            if match:
                return unquote(match.group(1))

    except Exception:
        pass

    return None


def parse_write_date(date_str: str) -> Optional[pd.Timestamp]:
    """작성일 문자열을 파싱하여 Timestamp로 변환합니다."""
    if not date_str or pd.isna(date_str):
        return None

    try:
        date_str = str(date_str).strip()
        if not date_str or date_str.lower() == 'nan':
            return None

        # 다양한 날짜 형식 파싱
        dt = pd.to_datetime(date_str, errors='coerce')
        if pd.notna(dt):
            return dt
    except Exception:
        pass

    return None


def is_steady_seller(write_date_str: str, analysis_month: str) -> bool:
    """
    스테디셀러(효자 콘텐츠)인지 판단합니다.
    작성일이 분석 대상 월 이전이면 스테디셀러입니다.
    """
    if not write_date_str or not analysis_month:
        return False

    try:
        write_dt = parse_write_date(write_date_str)
        if write_dt is None:
            return False

        # 분석 월의 첫날
        analysis_dt = pd.to_datetime(f"{analysis_month}-01")

        # 작성일이 분석 월 이전인지 확인
        return write_dt < analysis_dt
    except Exception:
        return False


def generate_performance_diagnosis(
    curr_views: int,
    prev_views: int,
    curr_publish_count: int,
    prev_publish_count: int = None
) -> Dict[str, Any]:
    """
    성과 원인을 자동 진단합니다.
    조회수 하락 시 발행량 부족인지 검색 노출 하락인지 분석합니다.
    """
    diagnosis = {
        'has_issue': False,
        'issue_type': None,
        'severity': 'normal',
        'message': '',
        'recommendation': ''
    }

    if prev_views <= 0:
        return diagnosis

    # 증감률 계산
    growth_rate = ((curr_views - prev_views) / prev_views) * 100

    # 10% 이상 하락 시 진단
    if growth_rate <= -10:
        diagnosis['has_issue'] = True
        diagnosis['severity'] = 'warning' if growth_rate > -30 else 'critical'

        # 발행량 분석
        if curr_publish_count <= 2:
            # 발행량 부족이 원인
            diagnosis['issue_type'] = 'low_publish_count'
            diagnosis['message'] = f"⚠️ 조회수가 {abs(growth_rate):.1f}% 하락했습니다. 이번 달 발행량({curr_publish_count}건)이 매우 적습니다."
            diagnosis['recommendation'] = "📌 발행 주기를 단축하여 콘텐츠 생산량을 늘릴 것을 권장합니다. 월 최소 4건 이상의 포스팅을 목표로 설정하세요."
        else:
            # 검색 노출 하락이 원인
            diagnosis['issue_type'] = 'search_exposure_drop'
            diagnosis['message'] = f"⚠️ 조회수가 {abs(growth_rate):.1f}% 하락했습니다. 발행량({curr_publish_count}건)은 적절하나 검색 노출이 감소한 것으로 보입니다."
            diagnosis['recommendation'] = "📌 키워드 최적화와 콘텐츠 품질 개선이 필요합니다. 인기 검색어를 활용한 제목 수정을 고려하세요."

    elif growth_rate >= 20:
        # 성장 중
        diagnosis['severity'] = 'success'
        diagnosis['message'] = f"✅ 조회수가 {growth_rate:.1f}% 상승했습니다. 좋은 성과입니다!"
        if curr_publish_count > 0:
            diagnosis['recommendation'] = "현재 콘텐츠 전략을 유지하면서 인기 콘텐츠의 패턴을 분석해 보세요."

    return diagnosis


def parse_date_to_year_month(date_value) -> Optional[str]:
    """Parse various date formats to YYYY-MM."""
    if pd.isna(date_value):
        return None

    try:
        if isinstance(date_value, pd.Timestamp):
            return date_value.strftime('%Y-%m')

        date_str = str(date_value).strip()
        if not date_str or date_str.lower() == 'nan':
            return None

        dt = pd.to_datetime(date_str, errors='coerce')
        if pd.notna(dt):
            return dt.strftime('%Y-%m')
    except Exception:
        pass

    return None


def parse_start_date_to_month(date_value) -> Optional[str]:
    """시작일을 월로 변환 (15일 규칙 적용).

    - day < 15: 당월 (예: 2025-12-01 → 2025-12)
    - day >= 15: 다음달 (예: 2025-11-28 → 2025-12)
    """
    if pd.isna(date_value):
        return None

    try:
        date_str = str(date_value).strip()
        if not date_str or date_str.lower() == 'nan':
            return None

        dt = pd.to_datetime(date_str, errors='coerce')
        if pd.isna(dt):
            return None

        if dt.day >= 15:
            # 다음 달로 이동
            if dt.month == 12:
                return f"{dt.year + 1}-01"
            else:
                return f"{dt.year}-{dt.month + 1:02d}"
        else:
            return dt.strftime('%Y-%m')
    except Exception:
        pass

    return None


def parse_date_range_to_year_month(range_str: str) -> Optional[str]:
    """Parse date range like '2025-12-01~2025-12-31' to YYYY-MM from start date."""
    if pd.isna(range_str):
        return None

    try:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', str(range_str))
        if match:
            date_str = match.group(1)
            dt = pd.to_datetime(date_str)
            return dt.strftime('%Y-%m')
    except Exception:
        pass

    return None


def find_header_row_by_columns(df: pd.DataFrame, required_cols: List[str]) -> int:
    """Find row index containing required column names."""
    for idx in range(min(20, len(df))):
        row_values = [str(v).strip() for v in df.iloc[idx].values if pd.notna(v)]
        matches = sum(1 for col in required_cols if any(col in v for v in row_values))
        if matches >= len(required_cols):
            return idx
    return -1


def process_work_csv(files: List[LoadedFile]) -> Dict[str, Any]:
    """Process work CSV: '[콘텐츠팀] 포스팅 업무 현황*.csv'

    헤더 1행 기준으로 컬럼 탐색 (키워드 포함 여부로 매칭):
    - *ID: 계약 그룹 ID (같은 ID = 같은 계약)
    - 계약 건수: 계약된 포스팅 수
    - 발행 완료: 발행 완료된 포스팅 수
    - 누적 이월: 이월 건수
    - 시작일: 계약 시작일 (월별 구분 기준)
    - 포스팅-게시물 제목: 개별 포스팅 제목
    - 포스팅-업로드: 개별 포스팅 발행일
    """
    all_posts = []  # 개별 포스팅 목록
    id_contracts = {}  # ID별 계약 정보 {id: {start_date, contract_count, published_count, ...}}

    for f in files:
        if not f.name.lower().endswith('.csv'):
            continue
        if '콘텐츠' not in f.name and '포스팅' not in f.name:
            continue

        try:
            df = None
            if f.df is not None:
                df = f.df.copy()
            elif f.raw_bytes:
                # 여러 인코딩 시도 (EUC-KR 파일 지원)
                for encoding in ['utf-8-sig', 'euc-kr', 'cp949']:
                    try:
                        df = pd.read_csv(BytesIO(f.raw_bytes), encoding=encoding)
                        # 컬럼명에 한글이 제대로 들어있는지 확인
                        col_check = ''.join(str(c) for c in df.columns)
                        if '계약' in col_check or '포스팅' in col_check or '시작일' in col_check:
                            break  # 정상적으로 읽힌 경우
                    except Exception:
                        continue

            if df is None:
                continue

            col_names = list(df.columns)

            # 헤더명에 키워드 포함 여부로 컬럼 매핑 (1행 기준)
            col_mapping = {}
            for col in col_names:
                col_str = str(col).strip()
                # ID 컬럼 (첫 번째 컬럼 또는 *ID 포함)
                if '*ID' in col_str or col_str == 'ID':
                    col_mapping['id'] = col
                # 거래처명
                elif '거래처' in col_str:
                    col_mapping['clinic'] = col
                # 계약 건수 (키워드: "계약 건수", "계약건수")
                elif '계약' in col_str and '건수' in col_str:
                    col_mapping['contract_count'] = col
                # 발행 완료 (키워드: "발행 완료", "발행완료")
                elif '발행' in col_str and ('완료' in col_str or '건수' in col_str):
                    if 'published_count' not in col_mapping:  # 첫 번째 매칭만
                        col_mapping['published_count'] = col
                # 누적 이월 (키워드: "누적 이월", "이월")
                elif '이월' in col_str:
                    col_mapping['carryover'] = col
                # 남은 작업 건수
                elif '남은' in col_str and '작업' in col_str:
                    col_mapping['remaining'] = col
                # 시작일
                elif col_str == '시작일':
                    col_mapping['start_date'] = col
                # 포스팅-업로드
                elif '포스팅' in col_str and '업로드' in col_str:
                    col_mapping['upload_date'] = col
                # 포스팅-게시물 제목
                elif '포스팅' in col_str and '제목' in col_str:
                    col_mapping['post_title'] = col
                # 포스팅 URL
                elif '포스팅' in col_str and 'URL' in col_str.upper():
                    col_mapping['post_url'] = col
                # 포스팅 상태
                elif '포스팅' in col_str and '상태' in col_str:
                    col_mapping['post_status'] = col
                # 계약상품
                elif '계약상품' in col_str or '계약 상품' in col_str:
                    col_mapping['contract_item'] = col

            # ID 컬럼 ffill (같은 계약 그룹 표시)
            if 'id' in col_mapping:
                df[col_mapping['id']] = df[col_mapping['id']].ffill()

            current_id = None
            for _, row in df.iterrows():
                # ID 가져오기
                row_id = str(row.get(col_mapping.get('id', ''), '')).strip()
                if not row_id or row_id.lower() == 'nan':
                    continue

                # 거래처명 가져오기
                clinic = str(row.get(col_mapping.get('clinic', ''), '')).strip()

                # ID가 바뀌거나 계약 정보가 있는 행이면 계약 정보 저장
                contract_count_val = row.get(col_mapping.get('contract_count', ''), '')
                if pd.notna(contract_count_val) and str(contract_count_val).strip() and str(contract_count_val).strip() != '':
                    contract_count_num = pd.to_numeric(contract_count_val, errors='coerce')
                    contract_count = 0 if pd.isna(contract_count_num) else int(contract_count_num)
                    if contract_count > 0:  # 계약 건수가 있는 행만 계약 정보로 저장
                        published_val = row.get(col_mapping.get('published_count', ''), 0)
                        published_num = pd.to_numeric(published_val, errors='coerce')
                        published_count = 0 if pd.isna(published_num) else int(published_num)

                        carryover_val = row.get(col_mapping.get('carryover', ''), 0)
                        carryover_num = pd.to_numeric(carryover_val, errors='coerce')
                        carryover = 0 if pd.isna(carryover_num) else int(carryover_num)

                        remaining_val = row.get(col_mapping.get('remaining', ''), 0)
                        remaining_num = pd.to_numeric(remaining_val, errors='coerce')
                        remaining = 0 if pd.isna(remaining_num) else int(remaining_num)

                        start_date_val = row.get(col_mapping.get('start_date', ''), '')
                        start_date_str = str(start_date_val).strip() if pd.notna(start_date_val) else ''
                        start_month = parse_start_date_to_month(start_date_str) if start_date_str else None

                        if start_month:
                            id_contracts[row_id] = {
                                'start_month': start_month,
                                'contract_count': contract_count,
                                'published_count': published_count,
                                'carryover': carryover,
                                'remaining': remaining,
                                'clinic': clinic if clinic and clinic.lower() != 'nan' else ''
                            }

                # 포스팅 정보 추출 (포스팅-업로드 날짜가 있는 행)
                upload_val = row.get(col_mapping.get('upload_date', ''), '')
                upload_str = str(upload_val).strip() if pd.notna(upload_val) else ''

                post_title = str(row.get(col_mapping.get('post_title', ''), '')).strip()
                post_url = str(row.get(col_mapping.get('post_url', ''), '')).strip()
                post_status = str(row.get(col_mapping.get('post_status', ''), '')).strip()

                # 포스팅 제목이나 URL이 있으면 포스팅으로 저장
                if (post_title and post_title.lower() != 'nan') or (post_url and post_url.lower() != 'nan'):
                    upload_month = parse_date_to_year_month(upload_str) if upload_str and upload_str.lower() != 'nan' else None

                    # 포스팅의 월은 upload_date 기준, 없으면 해당 ID의 start_month 사용
                    post_month = upload_month
                    if not post_month and row_id in id_contracts:
                        post_month = id_contracts[row_id]['start_month']

                    all_posts.append({
                        'id': row_id,
                        'year_month': post_month,
                        'clinic': clinic if clinic and clinic.lower() != 'nan' else '',
                        'post_title': post_title if post_title.lower() != 'nan' else '',
                        'post_url': post_url if post_url.lower() != 'nan' else '',
                        'upload_date': upload_str if upload_str.lower() != 'nan' else '',
                        'status': post_status if post_status.lower() != 'nan' else ''
                    })

        except Exception as e:
            print(f"Error processing work file {f.name}: {e}")
            continue

    # 월별 계약 정보 집계
    monthly_summary_dict = {}
    for id_key, contract_info in id_contracts.items():
        month = contract_info['start_month']
        if month not in monthly_summary_dict:
            monthly_summary_dict[month] = {
                'year_month': month,
                'contract_count': 0,
                'published_count': 0,
                'carryover': 0,
                'remaining': 0
            }
        monthly_summary_dict[month]['contract_count'] += contract_info['contract_count']
        monthly_summary_dict[month]['published_count'] += contract_info['published_count']
        monthly_summary_dict[month]['carryover'] += contract_info['carryover']
        monthly_summary_dict[month]['remaining'] += contract_info['remaining']

    monthly_summary = pd.DataFrame(list(monthly_summary_dict.values())) if monthly_summary_dict else pd.DataFrame()

    if not monthly_summary.empty:
        monthly_summary['completion_rate'] = np.where(
            monthly_summary['contract_count'] > 0,
            monthly_summary['published_count'] / monthly_summary['contract_count'] * 100,
            0
        )
        # base_carryover: "남은 작업 건수" 컬럼 사용
        monthly_summary['base_carryover'] = monthly_summary['remaining']
        monthly_summary['remaining_count'] = monthly_summary['remaining']

    # 포스팅 DataFrame 생성
    posts_df = pd.DataFrame(all_posts) if all_posts else pd.DataFrame()

    # 거래처 요약 (첫 번째 계약 정보 기준)
    clinic_summary_list = []
    seen_clinics = set()
    for id_key, contract_info in id_contracts.items():
        clinic = contract_info.get('clinic', '')
        if clinic and clinic not in seen_clinics:
            seen_clinics.add(clinic)
            clinic_summary_list.append({
                'clinic': clinic,
                'contract_count': contract_info['contract_count'],
                'published_count': contract_info['published_count'],
                'remaining_count': contract_info['remaining']
            })
    clinic_summary = pd.DataFrame(clinic_summary_list) if clinic_summary_list else pd.DataFrame()

    # 상태별 건수 계산 (월별) - posts_df 기준
    if not monthly_summary.empty and not posts_df.empty:
        for ym in monthly_summary['year_month'].unique():
            month_posts = posts_df[posts_df['year_month'] == ym]
            completed_count = len(month_posts[
                month_posts['status'].str.strip().str.lower().isin(['완료', '발행완료', '발행 완료'])
            ]) if 'status' in month_posts.columns else 0
            monthly_summary.loc[monthly_summary['year_month'] == ym, 'completed_status_count'] = completed_count

    return {
        'monthly_summary': monthly_summary.to_dict('records') if not monthly_summary.empty else [],
        'work_summary': posts_df.to_dict('records') if not posts_df.empty else [],
        'by_clinic': clinic_summary.to_dict('records') if not clinic_summary.empty else []
    }


def extract_month_from_filename(filename: str) -> Optional[str]:
    """Extract month from filename like '11월' or '12월' or date patterns."""
    from datetime import datetime

    # Pattern: 2025-12, 202512, 2026-01 (연도 포함 패턴 우선)
    match = re.search(r'(\d{4})[-_]?(\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern: 11월, 12월 (연도 없는 경우 현재 연도 기준)
    match = re.search(r'(\d{1,2})월', filename)
    if match:
        month = int(match.group(1))
        current_year = datetime.now().year
        return f"{current_year}-{month:02d}"

    return None


def process_inflow_xlsx(files: List[LoadedFile]) -> Dict[str, Any]:
    """
    Process inflow xlsx: '유입분석_월간_*.xlsx'
    추가: URL에서 검색 키워드 추출하여 급상승 검색어 TOP10 생성
    월별 데이터 분리하여 전월/당월 비교 가능
    """
    inflow_data = []  # 상세유입경로 (C열)
    source_data = []  # 유입경로 (A열) - 검색 키워드
    search_keywords = []  # 검색어 수집
    file_months = []

    for f in files:
        if not f.name.lower().endswith('.xlsx'):
            continue
        if '유입분석' not in f.name:
            continue

        # Extract month from filename
        file_month = extract_month_from_filename(f.name)
        if file_month:
            file_months.append(file_month)

        try:
            # Check df first, then raw_bytes
            if f.df is not None:
                df_raw = f.df.copy()
            elif f.raw_bytes:
                df_raw = pd.read_excel(BytesIO(f.raw_bytes), header=None)
            else:
                continue

            # Find header row containing '유입경로' and '비율'
            # In actual data: Row 7 has ['유입경로', '비율', '상세유입경로', '비율']
            # 유입경로 (첫번째 컬럼) 데이터를 사용 (상세유입경로 아님)
            header_idx = -1
            for idx in range(min(15, len(df_raw))):
                row_values = [str(v).strip() for v in df_raw.iloc[idx].values if pd.notna(v)]
                if '유입경로' in row_values:
                    header_idx = idx
                    break

            if header_idx < 0:
                continue

            df = df_raw.iloc[header_idx + 1:].copy()
            df.columns = df_raw.iloc[header_idx].values
            df = df.reset_index(drop=True)

            # 실제 엑셀 구조 (유입분석_ 파일):
            # 헤더 행 (8행, 인덱스 7): ['유입경로', '비율', '상세유입경로', '비율']
            # [0]열 (A열): 유입경로 (네이버 통합검색, 네이버 블로그 등)
            # [1]열 (B열): 비율 (유입경로 비율)
            # [2]열 (C열): 상세유입경로 (검색 키워드) ★ 이 데이터 사용
            # [3]열 (D열): 비율 (키워드 비율) ★ 이 데이터 사용

            # 컬럼명 리스트
            col_names = [str(c).strip() if pd.notna(c) else '' for c in df.columns]

            # A열(유입경로), B열(비율), C열(상세유입경로), D열(비율) 위치 찾기
            source_col_idx = 0  # A열: 유입경로 (기본값)
            source_ratio_col_idx = 1  # B열: 비율 (기본값)
            inflow_col_idx = 2  # C열: 상세유입경로 (기본값)
            inflow_ratio_col_idx = 3  # D열: 비율 (기본값)

            for i, col_name in enumerate(col_names):
                if '상세유입경로' in col_name or '상세' in col_name:
                    inflow_col_idx = i
                    if i + 1 < len(col_names):
                        inflow_ratio_col_idx = i + 1
                elif col_name == '유입경로':
                    source_col_idx = i
                    if i + 1 < len(col_names):
                        source_ratio_col_idx = i + 1

            # 데이터 추출
            for _, row in df.iterrows():
                # A열(유입경로) + B열(비율) 추출
                if source_col_idx < len(row) and source_ratio_col_idx < len(row):
                    src_val = row.iloc[source_col_idx]
                    src_ratio_val = row.iloc[source_ratio_col_idx]
                    src_raw = str(src_val).strip() if pd.notna(src_val) else ''
                    src_ratio = pd.to_numeric(str(src_ratio_val).replace('%', ''), errors='coerce') or 0
                    if src_raw and src_raw.lower() != 'nan' and src_ratio > 0:
                        source_data.append({
                            'source': src_raw,
                            'ratio': round(src_ratio, 2),
                            'file_month': file_month
                        })

                # C열(상세유입경로) + D열(비율) 추출
                if inflow_col_idx < len(row) and inflow_ratio_col_idx < len(row):
                    inflow_val = row.iloc[inflow_col_idx]
                    ratio_val = row.iloc[inflow_ratio_col_idx]
                    inflow_raw = str(inflow_val).strip() if pd.notna(inflow_val) else ''
                    ratio = pd.to_numeric(str(ratio_val).replace('%', ''), errors='coerce') or 0
                    if inflow_raw and inflow_raw.lower() != 'nan' and ratio > 0:
                        inflow_data.append({
                            'source': inflow_raw,
                            'ratio': round(ratio, 2),
                            'file_month': file_month
                        })

        except Exception as e:
            print(f"Error processing inflow file {f.name}: {e}")
            continue

    if not inflow_data and not source_data:
        return {}

    inflow_df = pd.DataFrame(inflow_data) if inflow_data else pd.DataFrame()
    source_df = pd.DataFrame(source_data) if source_data else pd.DataFrame()
    sorted_months = sorted(set(file_months)) if file_months else []

    # 비율 정규화 함수 (합이 100%가 되도록)
    def normalize_ratio(df_agg):
        """비율 합계를 100%로 정규화"""
        total = df_agg['ratio'].sum()
        if total > 0:
            df_agg = df_agg.copy()
            df_agg['ratio'] = (df_agg['ratio'] / total * 100).round(1)
        return df_agg

    # 기타를 맨 아래로 보내고 TOP5 + 기타 = 6개 가져오는 함수
    def get_top5_with_etc(df_agg):
        """기타를 제외한 TOP5 + 기타 = 총 6개 반환 (비율 정규화 적용)"""
        # 먼저 비율 정규화
        df_agg = normalize_ratio(df_agg)

        etc_row = df_agg[df_agg['source'] == '기타']
        non_etc = df_agg[df_agg['source'] != '기타']
        top5_non_etc = non_etc.nlargest(5, 'ratio')
        # 기타가 있으면 마지막에 추가
        if not etc_row.empty:
            result = pd.concat([top5_non_etc, etc_row], ignore_index=True)
        else:
            result = top5_non_etc
        return result.to_dict('records')

    # 월별로 상세유입경로 TOP5 + 기타 분리
    monthly_traffic_top5 = {}
    top5 = []
    if not inflow_df.empty:
        for month in sorted_months:
            month_data = inflow_df[inflow_df['file_month'] == month]
            if not month_data.empty:
                month_agg = month_data.groupby('source')['ratio'].sum().reset_index()
                monthly_traffic_top5[month] = get_top5_with_etc(month_agg)

        # 전체 집계 (하위 호환성)
        inflow_agg = inflow_df.groupby('source')['ratio'].sum().reset_index()
        top5 = get_top5_with_etc(inflow_agg)

    # 월별로 유입경로(검색키워드) TOP5 + 기타 분리
    monthly_source_top5 = {}
    source_top5 = []
    if not source_df.empty:
        for month in sorted_months:
            month_data = source_df[source_df['file_month'] == month]
            if not month_data.empty:
                month_agg = month_data.groupby('source')['ratio'].sum().reset_index()
                monthly_source_top5[month] = get_top5_with_etc(month_agg)

        # 전체 집계
        source_agg = source_df.groupby('source')['ratio'].sum().reset_index()
        source_top5 = get_top5_with_etc(source_agg)

    # 검색어 TOP10 집계 (월별)
    search_keywords_top10 = []
    monthly_search_keywords = {}
    if search_keywords:
        kw_df = pd.DataFrame(search_keywords)
        # 월별 검색어
        for month in sorted_months:
            month_kw = kw_df[kw_df['file_month'] == month]
            if not month_kw.empty:
                month_kw_agg = month_kw.groupby('keyword')['ratio'].sum().reset_index()
                month_kw_agg = month_kw_agg.sort_values('ratio', ascending=False)
                monthly_search_keywords[month] = month_kw_agg.head(10).to_dict('records')

        # 전체 검색어
        kw_agg = kw_df.groupby('keyword')['ratio'].sum().reset_index()
        kw_agg = kw_agg.sort_values('ratio', ascending=False)
        search_keywords_top10 = kw_agg.head(10).to_dict('records')

    return {
        'traffic_top5': top5,
        'source_top5': source_top5,  # 유입경로(검색키워드) TOP5
        'search_keywords_top10': search_keywords_top10,  # 급상승 검색어 TOP10
        'file_months': sorted_months,
        'monthly_traffic_top5': monthly_traffic_top5,  # 월별 상세유입경로 TOP5
        'monthly_source_top5': monthly_source_top5,  # 월별 유입경로 TOP5
        'monthly_search_keywords': monthly_search_keywords  # 월별 검색어 TOP10
    }


def process_views_rank_xlsx(files: List[LoadedFile], analysis_month: str = None) -> Dict[str, Any]:
    """
    Process views rank xlsx: '조회수_순위_월간_*.xlsx'
    추가: 스테디셀러(효자 콘텐츠) 발굴 - 작성일이 분석 월 이전인 인기 게시물 표시
    월별 데이터 분리하여 전월/당월 비교 가능
    """
    views_data = []
    file_months = []

    for f in files:
        if not f.name.lower().endswith('.xlsx'):
            continue
        if '조회수_순위' not in f.name:
            continue

        # Extract month from filename
        file_month = extract_month_from_filename(f.name)
        if file_month:
            file_months.append(file_month)

        try:
            # Check df first, then raw_bytes
            if f.df is not None:
                df_raw = f.df.copy()
            elif f.raw_bytes:
                df_raw = pd.read_excel(BytesIO(f.raw_bytes), header=None)
            else:
                continue

            # Find header row containing '순위', '조회수'
            # Row 7 has: ['순위', '제목', '조회수', '작성일']
            header_idx = -1
            for idx in range(min(15, len(df_raw))):
                row_values = [str(v).strip() for v in df_raw.iloc[idx].values if pd.notna(v)]
                if '순위' in row_values and '조회수' in row_values:
                    header_idx = idx
                    break

            if header_idx < 0:
                continue

            df = df_raw.iloc[header_idx + 1:].copy()
            df.columns = df_raw.iloc[header_idx].values
            df = df.reset_index(drop=True)

            # Find columns
            rank_col = None
            views_col = None
            title_col = None
            write_date_col = None

            for col in df.columns:
                if pd.isna(col):
                    continue
                col_str = str(col).strip()
                if col_str == '순위':
                    rank_col = col
                elif col_str == '조회수':
                    views_col = col
                elif col_str == '제목':
                    title_col = col
                elif col_str == '작성일':
                    write_date_col = col

            if views_col and title_col:
                for _, row in df.iterrows():
                    views = pd.to_numeric(row.get(views_col, 0), errors='coerce') or 0
                    title = str(row.get(title_col, '')).strip()
                    rank = pd.to_numeric(row.get(rank_col, 0), errors='coerce') or 0 if rank_col else 0
                    write_date = str(row.get(write_date_col, '')).strip() if write_date_col else ''

                    if views > 0 and title and title.lower() != 'nan':
                        # 스테디셀러 여부 판단
                        is_steady = is_steady_seller(write_date, analysis_month) if analysis_month else False

                        views_data.append({
                            'rank': int(rank),
                            'title': title,
                            'views': int(views),
                            'write_date': write_date if write_date.lower() != 'nan' else '',
                            'is_steady_seller': is_steady,
                            'file_month': file_month
                        })

        except Exception as e:
            print(f"Error processing views rank file {f.name}: {e}")
            continue

    if not views_data:
        return {}

    views_df = pd.DataFrame(views_data)
    sorted_months = sorted(set(file_months)) if file_months else []

    # 월별로 TOP5 분리
    monthly_views_top5 = {}
    for month in sorted_months:
        month_data = views_df[views_df['file_month'] == month]
        if not month_data.empty:
            monthly_views_top5[month] = month_data.nlargest(5, 'views').to_dict('records')

    # 전체 집계 (하위 호환성)
    top10 = views_df.nlargest(10, 'views').to_dict('records')
    top5 = views_df.nlargest(5, 'views').to_dict('records')

    # 스테디셀러만 필터링
    steady_sellers = [v for v in top10 if v.get('is_steady_seller', False)]

    return {
        'views_top5': top5,
        'views_top10': top10,
        'steady_sellers': steady_sellers,  # 효자 콘텐츠(스테디셀러)
        'file_months': sorted_months,
        'monthly_views_top5': monthly_views_top5  # 월별 조회수 TOP5
    }


def process_views_monthly_xlsx(files: List[LoadedFile]) -> Dict[str, Any]:
    """Process views monthly xlsx: '조회수_월간_*.xlsx'"""
    monthly_views = []

    for f in files:
        if not f.name.lower().endswith('.xlsx'):
            continue
        # Match 조회수_월간_ but not 조회수_순위_월간_
        if '조회수_월간_' not in f.name or '순위' in f.name:
            continue

        try:
            # Check df first, then raw_bytes
            if f.df is not None:
                df_raw = f.df.copy()
            elif f.raw_bytes:
                df_raw = pd.read_excel(BytesIO(f.raw_bytes), header=None)
            else:
                continue

            # Find header row containing '기간' and '전체'
            # Row 6 has: ['기간', '기간', '전체', '피이웃', '서로이웃', '기타']
            header_idx = -1
            for idx in range(min(15, len(df_raw))):
                row_values = [str(v).strip() for v in df_raw.iloc[idx].values if pd.notna(v)]
                if '기간' in row_values and '전체' in row_values:
                    header_idx = idx
                    break

            if header_idx < 0:
                continue

            df = df_raw.iloc[header_idx + 1:].copy()
            df.columns = df_raw.iloc[header_idx].values
            df = df.reset_index(drop=True)

            # Find period and total columns
            # Data row: ['2025-12-01~2025-12-31', '739', '5', '64', '670']
            # The first non-nan value containing date range is the period
            # The '전체' column has the total views

            period_col = None
            total_col = None

            col_list = list(df.columns)
            for i, col in enumerate(col_list):
                if pd.isna(col):
                    continue
                col_str = str(col).strip()
                if col_str == '기간' and period_col is None:
                    period_col = col
                elif col_str == '전체':
                    total_col = col

            if total_col:
                for _, row in df.iterrows():
                    # Get the first column value as period (it contains the date range)
                    period = str(row.iloc[0]).strip() if len(row) > 0 else ''
                    year_month = parse_date_range_to_year_month(period)
                    total_views = pd.to_numeric(row.get(total_col, 0), errors='coerce') or 0

                    if year_month and total_views > 0:
                        monthly_views.append({
                            'year_month': year_month,
                            'total_views': int(total_views)
                        })

        except Exception as e:
            print(f"Error processing views monthly file {f.name}: {e}")
            continue

    if not monthly_views:
        return {}

    views_df = pd.DataFrame(monthly_views)
    views_df = views_df.groupby('year_month')['total_views'].sum().reset_index()
    views_df = views_df.sort_values('year_month')
    views_df['mom_growth'] = views_df['total_views'].pct_change() * 100

    return {
        'monthly_views': views_df.to_dict('records'),
        'total_by_month': dict(zip(views_df['year_month'], views_df['total_views']))
    }


def process_blog(files: List[LoadedFile]) -> Dict[str, Any]:
    """
    Main processor for blog/content team.

    Args:
        files: List of LoadedFile objects

    Returns:
        dict with department, month, prev_month, current_month_data, prev_month_data,
        growth_rate, kpi, tables, charts, clean_data, diagnosis, insights

    분석 로직:
    1. 이월 건수: 계약 건수 - 발행 완료 건수
    2. 포스팅 리스트: 제목과 URL (클릭 가능한 링크)
    3. 전월 대비 조회수 증감률 계산
    """
    work_result = process_work_csv(files)
    inflow_result = process_inflow_xlsx(files)
    views_monthly_result = process_views_monthly_xlsx(files)

    # Determine months - 계약 시작일(work) 기준 우선, 없으면 조회수(views) 기준
    work_months = set()
    if work_result.get('monthly_summary'):
        work_months.update([s['year_month'] for s in work_result['monthly_summary'] if s.get('year_month')])

    views_months = set()
    if views_monthly_result.get('monthly_views'):
        views_months.update([s['year_month'] for s in views_monthly_result['monthly_views']])

    # 계약 데이터 월이 있으면 그것을 기준으로 current/prev 결정
    if work_months:
        sorted_work = sorted(work_months)
        current_month = sorted_work[-1]
        prev_month = sorted_work[-2] if len(sorted_work) >= 2 else None
    else:
        all_months = views_months
        sorted_months = sorted(all_months) if all_months else []
        current_month = sorted_months[-1] if sorted_months else None
        prev_month = sorted_months[-2] if len(sorted_months) >= 2 else None

    # Process views rank with analysis_month for steady seller detection
    views_rank_result = process_views_rank_xlsx(files, analysis_month=current_month)

    # Current month data
    current_month_data = {}
    prev_month_data = {}

    if work_result.get('monthly_summary'):
        for summary in work_result['monthly_summary']:
            if summary.get('year_month') == current_month:
                current_month_data['work'] = summary
            elif summary.get('year_month') == prev_month:
                prev_month_data['work'] = summary

    if views_monthly_result.get('total_by_month'):
        current_month_data['total_views'] = views_monthly_result['total_by_month'].get(current_month, 0)
        prev_month_data['total_views'] = views_monthly_result['total_by_month'].get(prev_month, 0)

    # Growth rate
    growth_rate = {}
    curr_views = current_month_data.get('total_views', 0)
    prev_views = prev_month_data.get('total_views', 0)
    if prev_views > 0:
        growth_rate['views'] = ((curr_views - prev_views) / prev_views) * 100
    else:
        growth_rate['views'] = 0

    # KPI
    work_summary = current_month_data.get('work', {})
    curr_publish_count = work_summary.get('published_count', 0)
    contract_count = work_summary.get('contract_count', 0)

    # 이월 건수 취합: "지난달 이월 건수" 컬럼 데이터 사용 (User Request Reversion)
    carryover_count = work_summary.get('base_carryover', 0)

    # 전월 데이터
    prev_work_summary = prev_month_data.get('work', {})
    prev_publish_count = prev_work_summary.get('published_count', 0)
    prev_contract_count = prev_work_summary.get('contract_count', 0)
    prev_carryover_count = prev_work_summary.get('base_carryover', 0)

    kpi = {
        'publish_completion_rate': round(work_summary.get('completion_rate', 0), 2),
        'remaining_cnt': work_summary.get('remaining_count', 0),
        'total_views': current_month_data.get('total_views', 0),
        'views_mom_growth': round(growth_rate.get('views', 0), 2),
        'published_count': curr_publish_count,  # 발행량
        'contract_count': contract_count,  # 계약 건수
        'carryover_count': carryover_count,  # 이월 건수 (계약-발행)
        'pending_data_count': work_summary.get('pending_data_count', 0),  # 자료 미수신 건수
        # 전월 데이터
        'prev_published_count': prev_publish_count,
        'prev_contract_count': prev_contract_count,
        'prev_carryover_count': prev_carryover_count,
        'prev_total_views': prev_month_data.get('total_views', 0)
    }

    # 성과 원인 자동 진단
    diagnosis = generate_performance_diagnosis(
        curr_views=curr_views,
        prev_views=prev_views,
        curr_publish_count=curr_publish_count,
        prev_publish_count=prev_month_data.get('work', {}).get('published_count', 0)
    )

    # Separate work_summary by month for side-by-side comparison
    all_work_summary = work_result.get('work_summary', [])
    work_df = pd.DataFrame(all_work_summary) if all_work_summary else pd.DataFrame()

    curr_work_summary = []
    prev_work_summary = []

    if not work_df.empty and 'year_month' in work_df.columns:
        curr_work_df = work_df[work_df['year_month'] == current_month]
        prev_work_df = work_df[work_df['year_month'] == prev_month]
        curr_work_summary = curr_work_df.to_dict('records') if not curr_work_df.empty else []
        prev_work_summary = prev_work_df.to_dict('records') if not prev_work_df.empty else []

    # 월별 TOP5 데이터 추출 (posting_list에서 발행일 매핑에 사용)
    monthly_views_top5 = views_rank_result.get('monthly_views_top5', {})

    # 당월/전월 views_top5 먼저 가져오기 (발행일 매핑용)
    curr_views_top5 = monthly_views_top5.get(current_month, views_rank_result.get('views_top5', []))
    prev_views_top5 = monthly_views_top5.get(prev_month, [])

    # views_top5에서 제목 -> 발행일 매핑 생성
    curr_views_date_map = {post.get('title', ''): post.get('write_date', '') for post in curr_views_top5}
    prev_views_date_map = {post.get('title', ''): post.get('write_date', '') for post in prev_views_top5}

    # 포스팅 리스트 - 제목, URL, 발행일 정리 (클릭 가능한 링크용)
    posting_list = []
    for post in curr_work_summary:
        title = post.get('post_title', '')
        url = post.get('post_url', '')
        status = post.get('status', '')
        # 포스팅-업로드 날짜만 사용
        write_date = post.get('upload_date', '')
        if title and title.lower() != 'nan':
            posting_list.append({
                'title': title,
                'url': url if url and url.lower() != 'nan' else '',
                'status': status,
                'write_date': write_date
            })

    prev_posting_list = []
    for post in prev_work_summary:
        title = post.get('post_title', '')
        url = post.get('post_url', '')
        status = post.get('status', '')
        # 포스팅-업로드 날짜만 사용
        write_date = post.get('upload_date', '')
        if title and title.lower() != 'nan':
            prev_posting_list.append({
                'title': title,
                'url': url if url and url.lower() != 'nan' else '',
                'status': status,
                'write_date': write_date  # 발행일 추가
            })

    monthly_traffic_top5 = inflow_result.get('monthly_traffic_top5', {})
    monthly_source_top5 = inflow_result.get('monthly_source_top5', {})

    # 당월/전월 traffic_top5 (상세유입경로)
    curr_traffic_top5 = monthly_traffic_top5.get(current_month, inflow_result.get('traffic_top5', []))
    prev_traffic_top5 = monthly_traffic_top5.get(prev_month, [])

    # 당월/전월 source_top5 (유입경로 = 검색 키워드)
    curr_source_top5 = monthly_source_top5.get(current_month, inflow_result.get('source_top5', []))
    prev_source_top5 = monthly_source_top5.get(prev_month, [])

    # Tables with new features
    tables = {
        'traffic_top5': curr_traffic_top5,
        'prev_traffic_top5': prev_traffic_top5,  # 전월 상세유입경로 TOP5
        'source_top5': curr_source_top5,  # 당월 유입경로(검색키워드) TOP5
        'prev_source_top5': prev_source_top5,  # 전월 유입경로 TOP5
        'views_top5': curr_views_top5,
        'prev_views_top5': prev_views_top5,  # 전월 조회수 TOP5
        'views_top10': views_rank_result.get('views_top10', []),
        'work_summary': all_work_summary,
        'curr_work_summary': curr_work_summary,
        'prev_work_summary': prev_work_summary,
        # 포스팅 리스트 (제목 + URL)
        'posting_list': posting_list,
        'prev_posting_list': prev_posting_list,
        # 새로운 분석 데이터
        'search_keywords_top10': inflow_result.get('search_keywords_top10', []),  # 급상승 검색어
        'steady_sellers': views_rank_result.get('steady_sellers', []),  # 효자 콘텐츠
        # 월별 데이터 (상세)
        'monthly_views_top5': monthly_views_top5,
        'monthly_traffic_top5': monthly_traffic_top5,
        'monthly_source_top5': monthly_source_top5  # 월별 유입경로 TOP5
    }

    # Charts
    charts = {
        'views_trend': views_monthly_result.get('monthly_views', [])
    }

    # Clean data
    clean_data = {
        'work': work_result,
        'inflow': inflow_result,
        'views_rank': views_rank_result,
        'views_monthly': views_monthly_result
    }

    # 인사이트 생성
    insights = {
        'diagnosis': diagnosis,
        'has_steady_sellers': len(views_rank_result.get('steady_sellers', [])) > 0,
        'steady_seller_count': len(views_rank_result.get('steady_sellers', [])),
        'has_search_keywords': len(inflow_result.get('search_keywords_top10', [])) > 0,
        'search_keyword_count': len(inflow_result.get('search_keywords_top10', []))
    }

    return {
        'department': '콘텐츠팀',
        'month': current_month,
        'prev_month': prev_month,
        'current_month_data': current_month_data,
        'prev_month_data': prev_month_data,
        'growth_rate': growth_rate,
        'kpi': kpi,
        'tables': tables,
        'charts': charts,
        'clean_data': clean_data,
        'diagnosis': diagnosis,  # 성과 원인 진단
        'insights': insights  # 인사이트
    }
