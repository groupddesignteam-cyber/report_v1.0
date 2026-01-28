"""
세팅팀 데이터 처리 모듈
- Setting KPI CSV: '세팅KPI.csv'
"""

import re
import pandas as pd
import numpy as np
from io import BytesIO
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LoadedFile:
    name: str
    df: Optional[pd.DataFrame] = None
    raw_bytes: Optional[bytes] = None


def is_completed_status(status_value, completion_date_value=None) -> bool:
    """
    Check if a channel is completed based on status or completion date.
    Status text takes priority over completion date.
    """
    # Check status text FIRST (takes priority)
    if status_value is not None and not pd.isna(status_value):
        status_str = str(status_value).strip().upper()
        if status_str:
            # Explicitly NOT completed keywords
            incomplete_keywords = ['진행', '대기', '미완', '보류', '예정', '준비']
            for keyword in incomplete_keywords:
                if keyword in status_str:
                    return False

            # Completed keywords
            completion_keywords = ['완료', '완료됨', 'O', 'Y', 'YES', 'DONE', 'COMPLETE']
            for keyword in completion_keywords:
                if keyword in status_str:
                    return True

    # Fallback: check completion date only if status is empty/missing
    if completion_date_value is not None and pd.notna(completion_date_value):
        date_str = str(completion_date_value).strip()
        if date_str and date_str.lower() not in ['nan', 'nat', '']:
            return True

    return False


def _clean_val(value) -> str:
    """Clean a value to string, return empty if NaN/empty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    s = str(value).strip()
    return '' if s.lower() in ['nan', 'nat', ''] else s


def _clean_date(value) -> str:
    """Clean a date value, removing time portion."""
    s = _clean_val(value)
    if s and ' ' in s:
        s = s.split(' ')[0]
    return s


def extract_channel_groups(columns: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Extract channel groups from column names.
    Channels have suffixes: -상태, -종류, -작업완료일, -작업시작일

    Returns dict: {channel_name: {suffix: column_name}}
    """
    channel_suffixes = ['-상태', '-종류', '-작업완료일', '-작업시작일', '-비고', '-자료 수신일']
    channels = {}

    for col in columns:
        col_str = str(col).strip()
        for suffix in channel_suffixes:
            if col_str.endswith(suffix):
                channel_name = col_str[:-len(suffix)]
                if channel_name not in channels:
                    channels[channel_name] = {}
                channels[channel_name][suffix] = col
                break

    return channels


def process_setting(files: List[LoadedFile]) -> Dict[str, Any]:
    """
    Main processor for setting team.

    Handles '세팅KPI.csv'

    Args:
        files: List of LoadedFile objects

    Returns:
        dict with department, month, prev_month, current_month_data, prev_month_data,
        growth_rate, kpi, tables, charts, clean_data
    """
    clinic_data = []

    for f in files:
        if not re.match(r'(세팅KPI|신규계약프로세스).*\.csv', f.name, re.IGNORECASE):
            continue

        try:
            if f.df is not None:
                df = f.df.copy()
            elif f.raw_bytes:
                df = pd.read_csv(BytesIO(f.raw_bytes), encoding='utf-8-sig')
            else:
                continue

            # Find clinic key column and other info columns
            clinic_col = None
            marketing_start_col = None
            contract_item_col = None
            platform_name_col = None
            data_received_col = None

            for col in df.columns:
                col_str = str(col).strip()
                if '거래처명' in col_str:
                    clinic_col = col
                elif '제목' in col_str and clinic_col is None:
                    clinic_col = col
                elif '마케팅 시작일' in col_str:
                    marketing_start_col = col
                elif '계약상품' in col_str:
                    contract_item_col = col
                elif '플랫폼명' in col_str:
                    platform_name_col = col
                elif '자료 수신' in col_str and '현황' not in col_str: # Avoid '자료 수신 현황' group
                    data_received_col = col

            if clinic_col is None:
                continue

            # Extract channel groups
            channel_groups = extract_channel_groups(df.columns.tolist())

            if not channel_groups:
                continue

            # CSV는 동일 ID의 여러 행으로 구성됨 (각 행이 플랫폼 세부작업)
            # 첫 행: 메타정보(거래처명, 계약상품 등) + 각 플랫폼 첫 번째 세부작업
            # 이후 행: 각 플랫폼 추가 세부작업

            # ID 컬럼 찾기
            id_col = None
            for col in df.columns:
                if str(col).strip() == '*ID':
                    id_col = col
                    break

            # ID 기준으로 그룹핑 (없으면 전체를 하나의 그룹으로)
            if id_col:
                groups = df.groupby(id_col)
            else:
                # 첫 행의 clinic_col 기준
                df['_group'] = df[clinic_col].fillna(method='ffill')
                groups = df.groupby('_group')

            for group_key, group_df in groups:
                first_row = group_df.iloc[0]
                clinic_name = str(first_row.get(clinic_col, '')).strip()
                if not clinic_name or clinic_name == 'nan':
                    continue
                # 제목에서 [기개원] 등 접두사 제거
                clinic_name = re.sub(r'\[.*?\]\s*', '', clinic_name).strip()

                marketing_start_date = str(first_row.get(marketing_start_col, '')).strip() if marketing_start_col else ''
                contract_item = str(first_row.get(contract_item_col, '')).strip() if contract_item_col else ''
                platform_name = str(first_row.get(platform_name_col, '')).strip() if platform_name_col else ''
                data_received = str(first_row.get(data_received_col, '')).strip() if data_received_col else ''

                # 각 플랫폼별로 모든 행에서 세부작업 수집
                channel_status = {}

                for channel_name, suffixes in channel_groups.items():
                    status_col_name = suffixes.get('-상태')
                    completion_date_col_name = suffixes.get('-작업완료일') or suffixes.get('-자료 수신일')
                    start_date_col_name = suffixes.get('-작업시작일')
                    type_col_name = suffixes.get('-종류')
                    note_col_name = suffixes.get('-비고')

                    # 모든 행에서 세부작업 수집
                    sub_tasks = []
                    for _, row in group_df.iterrows():
                        status_value = row.get(status_col_name) if status_col_name else None
                        completion_date = row.get(completion_date_col_name) if completion_date_col_name else None
                        start_date = row.get(start_date_col_name) if start_date_col_name else None
                        type_value = row.get(type_col_name) if type_col_name else None
                        note_value = row.get(note_col_name) if note_col_name else None

                        # 유효한 값 확인
                        has_content = False
                        for val in [status_value, completion_date, start_date, type_value]:
                            if val is not None and pd.notna(val) and str(val).strip() not in ['', 'nan', 'NaN']:
                                has_content = True
                                break

                        if not has_content:
                            continue

                        # 값 정리
                        type_str = _clean_val(type_value)
                        status_raw = _clean_val(status_value)
                        completion_date_str = _clean_date(completion_date)
                        start_date_str = _clean_date(start_date)
                        note_str = _clean_val(note_value)

                        is_completed = is_completed_status(status_value, completion_date)
                        if is_completed:
                            task_status = 'completed'
                        elif status_raw:
                            task_status = 'in_progress'
                        else:
                            task_status = 'not_started'

                        sub_tasks.append({
                            'type': type_str,
                            'status': task_status,
                            'status_raw': status_raw,
                            'completion_date': completion_date_str,
                            'start_date': start_date_str,
                            'note': note_str,
                        })

                    # 플랫폼 전체 상태 계산
                    if sub_tasks:
                        completed_count = sum(1 for t in sub_tasks if t['status'] == 'completed')
                        in_progress_count = sum(1 for t in sub_tasks if t['status'] == 'in_progress')
                        total_tasks = len(sub_tasks)
                        if completed_count == total_tasks:
                            platform_status = 'completed'
                        elif in_progress_count > 0 or completed_count > 0:
                            platform_status = 'in_progress'
                        else:
                            platform_status = 'not_started'
                    else:
                        platform_status = 'not_started'
                        total_tasks = 0
                        completed_count = 0

                    channel_status[channel_name] = {
                        'status': platform_status,
                        'type': sub_tasks[0]['type'] if sub_tasks else '',
                        'status_raw': sub_tasks[0]['status_raw'] if sub_tasks else '',
                        'completion_date': sub_tasks[-1]['completion_date'] if sub_tasks else '',
                        'sub_tasks': sub_tasks,
                        'total_tasks': total_tasks,
                        'completed_tasks': completed_count,
                    }

                # 전체 진행률: 세부작업 기준
                all_tasks = sum(ch['total_tasks'] for ch in channel_status.values())
                all_completed = sum(ch['completed_tasks'] for ch in channel_status.values())
                progress_rate = (all_completed / all_tasks * 100) if all_tasks > 0 else 0

                # 플랫폼 수 기준 (세부작업이 있는 플랫폼만)
                active_channels = sum(1 for ch in channel_status.values() if ch['total_tasks'] > 0)
                completed_channels = sum(1 for ch in channel_status.values() if ch['status'] == 'completed')

                clinic_data.append({
                    'clinic': clinic_name,
                    'marketing_start_date': marketing_start_date,
                    'contract_item': contract_item,
                    'platform_name': platform_name,
                    'data_received': data_received,
                    'total_channels': active_channels,
                    'completed_channels': completed_channels,
                    'progress_rate': round(progress_rate, 2),
                    'channel_status': channel_status
                })

        except Exception as e:
            print(f"Error processing setting file {f.name}: {e}")
            continue

    if not clinic_data:
        return {
            'department': '세팅팀',
            'month': None,
            'prev_month': None,
            'current_month_data': {},
            'prev_month_data': {},
            'growth_rate': {},
            'kpi': {},
            'tables': {},
            'charts': {},
            'clean_data': {}
        }

    clinic_df = pd.DataFrame(clinic_data)

    # Calculate KPIs
    avg_progress_rate = clinic_df['progress_rate'].mean()
    completed_clinics = len(clinic_df[clinic_df['progress_rate'] >= 70])  # >= 70%
    risk_clinics = len(clinic_df[clinic_df['progress_rate'] < 40])  # < 40%
    total_clinics = len(clinic_df)

    # Clinic progress table (sorted desc by progress_rate) with channel details
    clinic_progress = []
    for _, row in clinic_df.sort_values('progress_rate', ascending=False).iterrows():
        channels_detail = []
        for ch_name, ch_info in row['channel_status'].items():
            if isinstance(ch_info, dict):
                channels_detail.append({
                    'channel': ch_name,
                    'status': ch_info['status'],
                    'type': ch_info.get('type', ''),
                    'status_raw': ch_info.get('status_raw', ''),
                    'completion_date': ch_info.get('completion_date', ''),
                    'sub_tasks': ch_info.get('sub_tasks', []),
                    'total_tasks': ch_info.get('total_tasks', 0),
                    'completed_tasks': ch_info.get('completed_tasks', 0),
                })
            else:
                channels_detail.append({
                    'channel': ch_name,
                    'status': ch_info,
                    'type': '',
                    'status_raw': '',
                    'completion_date': '',
                    'sub_tasks': [],
                    'total_tasks': 0,
                    'completed_tasks': 0,
                })
        clinic_progress.append({
            'clinic': row['clinic'],
            'total_channels': row['total_channels'],
            'completed_channels': row['completed_channels'],
            'progress_rate': row['progress_rate'],
            'channels': channels_detail
        })

    # Channel completion rate (3-state: completed, in_progress, not_started) + 종류 집계
    all_channel_statuses = {}
    channel_types = {}  # {channel: {type: count}}
    for _, row in clinic_df.iterrows():
        for channel, ch_info in row['channel_status'].items():
            if channel not in all_channel_statuses:
                all_channel_statuses[channel] = {'completed': 0, 'in_progress': 0, 'not_started': 0, 'total': 0}
            if channel not in channel_types:
                channel_types[channel] = {}

            status = ch_info['status'] if isinstance(ch_info, dict) else ch_info
            ch_type = ch_info.get('type', '') if isinstance(ch_info, dict) else ''

            all_channel_statuses[channel]['total'] += 1
            if status == 'completed':
                all_channel_statuses[channel]['completed'] += 1
            elif status == 'in_progress':
                all_channel_statuses[channel]['in_progress'] += 1
            else:
                all_channel_statuses[channel]['not_started'] += 1

            # 종류 집계
            if ch_type:
                channel_types[channel][ch_type] = channel_types[channel].get(ch_type, 0) + 1

    channel_completion_rate = []
    for channel, counts in all_channel_statuses.items():
        rate = (counts['completed'] / counts['total'] * 100) if counts['total'] > 0 else 0
        # 종류별 빈도 정렬
        types = channel_types.get(channel, {})
        types_sorted = sorted(types.items(), key=lambda x: x[1], reverse=True)
        channel_completion_rate.append({
            'channel': channel,
            'completed': counts['completed'],
            'in_progress': counts['in_progress'],
            'not_started': counts['not_started'],
            'total': counts['total'],
            'completion_rate': round(rate, 2),
            'types': [{'name': t[0], 'count': t[1]} for t in types_sorted]
        })

    channel_completion_rate = sorted(channel_completion_rate, key=lambda x: x['completion_rate'], reverse=True)

    # KPI
    kpi = {
        'avg_progress_rate': round(avg_progress_rate, 2),
        'completed_clinics': completed_clinics,
        'risk_clinics': risk_clinics,
        'total_clinics': total_clinics
    }

    # Tables
    tables = {
        'clinic_progress': clinic_progress,
        'channel_completion_rate': channel_completion_rate
    }

    # Charts
    charts = {
        'progress_distribution': {
            'high': len(clinic_df[clinic_df['progress_rate'] >= 70]),
            'medium': len(clinic_df[(clinic_df['progress_rate'] >= 40) & (clinic_df['progress_rate'] < 70)]),
            'low': len(clinic_df[clinic_df['progress_rate'] < 40])
        }
    }

    # Clean data
    clean_data = {
        'clinic_data': clinic_df.to_dict('records')
    }

    return {
        'department': '세팅팀',
        'month': None,  # Setting KPI is not month-based
        'prev_month': None,
        'current_month_data': {
            'avg_progress_rate': avg_progress_rate,
            'completed_clinics': completed_clinics,
            'risk_clinics': risk_clinics
        },
        'prev_month_data': {},
        'growth_rate': {},
        'kpi': kpi,
        'tables': tables,
        'charts': charts,
        'clean_data': clean_data
    }
