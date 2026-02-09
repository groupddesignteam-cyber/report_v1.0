"""
고객 피드백 분석 프로세서
- 설문/피드백 xlsx/csv 파일의 컬럼을 자동 감지
- 점수, 객관식, 주관식, 단일선택 등 타입별 분석
- 개선 제안 자동 생성
"""

import pandas as pd
import re
from io import BytesIO
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


# 한국어 불용어 (조사, 접속사 등)
KOREAN_STOPWORDS = {
    '은', '는', '이', '가', '을', '를', '에', '의', '도', '로', '와', '과',
    '한', '및', '등', '더', '그', '수', '것', '때', '중', '후', '위', '내',
    '좀', '잘', '안', '못', '너무', '아주', '매우', '정말', '진짜', '다',
    '있다', '없다', '하다', '되다', '있는', '없는', '하는', '되는',
    '있습니다', '없습니다', '합니다', '됩니다', '입니다', '했습니다',
    '없음', '있음', '해주', '해서', '하고', '했는데', '인데', '근데',
    '그리고', '하지만', '그래서', '때문에', '대한', '통해',
}


def load_feedback_file(file) -> Optional[pd.DataFrame]:
    """xlsx 또는 csv 피드백 파일을 읽어 DataFrame으로 반환."""
    try:
        raw = file.raw_bytes if hasattr(file, 'raw_bytes') else file.read()

        if file.name.endswith('.xlsx') or file.name.endswith('.xls'):
            df = pd.read_excel(BytesIO(raw))
        elif file.name.endswith('.csv'):
            # 다중 인코딩 시도
            for enc in ['utf-8-sig', 'utf-8', 'euc-kr', 'cp949']:
                try:
                    df = pd.read_csv(BytesIO(raw), encoding=enc)
                    break
                except (UnicodeDecodeError, Exception):
                    continue
            else:
                return None
        else:
            return None

        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception:
        return None


def classify_column(series: pd.Series, col_name: str) -> str:
    """컬럼 데이터를 분석하여 타입을 자동 감지."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return 'free_text'

    # 0. 숫자/점수 감지 (타임스탬프보다 먼저 - 1~5 범위 정수가 날짜로 오감지 방지)
    str_values = non_null.astype(str).str.strip()
    score_pattern = str_values.str.extract(r'^(\d+)\s*점?$', expand=False)
    numeric_vals = pd.to_numeric(score_pattern, errors='coerce')
    numeric_ratio = numeric_vals.notna().sum() / len(non_null) if len(non_null) > 0 else 0

    if numeric_ratio > 0.7:
        valid = numeric_vals.dropna()
        score_keywords = ['점', '만족', '평가', '평점', 'score', '의향']
        is_score_name = any(kw in col_name.lower() for kw in score_keywords)
        is_score_range = valid.min() >= 1 and valid.max() <= 5

        if is_score_range or is_score_name:
            return 'score'
        return 'numeric'

    # 1. 타임스탬프 감지
    ts_keywords = ['타임', '시간', '일시', 'date', 'time', '날짜', '일자', '스탬프']
    if any(kw in col_name.lower() for kw in ts_keywords):
        try:
            pd.to_datetime(non_null.head(5))
            return 'timestamp'
        except Exception:
            pass

    # datetime 타입 체크
    if pd.api.types.is_datetime64_any_dtype(series):
        return 'timestamp'

    try:
        parsed = pd.to_datetime(non_null, errors='coerce')
        if parsed.notna().mean() > 0.8:
            # 순수 정수(1-5 등)가 날짜로 파싱되는 것 방지
            str_vals = non_null.astype(str)
            looks_like_date = str_vals.str.contains(r'[-/년월일:]', regex=True).mean()
            if looks_like_date > 0.5:
                return 'timestamp'
    except Exception:
        pass

    # 2. 문자열 분석
    avg_length = str_values.str.len().mean()
    cardinality = non_null.nunique() / len(non_null) if len(non_null) > 0 else 0

    # 질문형 컬럼명이면 식별자가 아닌 자유텍스트로 우선 판단
    question_keywords = ['Q', '?', '주세요', '있다면', '말씀', '의견', '좋았', '고쳐']
    is_question_col = any(kw in col_name for kw in question_keywords)

    # 불릿/복수선택 감지
    bullet_ratio = str_values.str.contains(r'[•·■▪]', regex=True).mean()
    has_comma_multi = str_values.str.count(',').mean()
    if bullet_ratio > 0.3 or (has_comma_multi > 1.5 and avg_length > 30):
        return 'multi_select'

    # 질문형 컬럼이면 free_text 우선
    if is_question_col and avg_length > 5:
        return 'free_text'

    # 식별자 (짧은 텍스트, 높은 고유성)
    if cardinality > 0.7 and avg_length < 30:
        return 'identifier'

    # 단일 선택 (낮은 카디널리티)
    if non_null.nunique() <= 5 and avg_length < 50:
        return 'single_select'

    if cardinality < 0.4 and avg_length < 50:
        return 'single_select'

    return 'free_text'


def parse_multiselect(value) -> List[str]:
    """복수선택 값을 개별 옵션으로 파싱."""
    if pd.isna(value) or not str(value).strip():
        return []

    text = str(value).strip()

    # 불릿 포인트 기반 분리
    if '•' in text:
        parts = [p.strip().lstrip('•').strip() for p in text.split('•')]
    elif '·' in text:
        parts = [p.strip().lstrip('·').strip() for p in text.split('·')]
    elif ',' in text and len(text) > 20:
        # 쉼표 분리 (긴 텍스트인 경우만)
        parts = [p.strip() for p in text.split(',')]
    else:
        parts = [text.strip()]

    return [p.rstrip(',').strip() for p in parts if p.rstrip(',').strip()]


def extract_score_value(value) -> Optional[float]:
    """'3점', '3', 3 등에서 숫자를 추출."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    match = re.match(r'^(\d+(?:\.\d+)?)\s*점?$', text)
    if match:
        return float(match.group(1))
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def extract_keywords(texts: List[str], top_n: int = 15) -> List[Dict[str, Any]]:
    """한국어 텍스트에서 키워드 빈도를 추출 (간단한 토큰화)."""
    word_count = {}

    for text in texts:
        if not text or pd.isna(text):
            continue
        text = str(text).strip()
        if not text or text.lower() == 'nan':
            continue

        # 특수문자 제거 후 공백 토큰화
        cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text)
        tokens = cleaned.split()

        for token in tokens:
            token = token.strip()
            if len(token) < 2:
                continue
            if token.lower() in KOREAN_STOPWORDS:
                continue
            word_count[token] = word_count.get(token, 0) + 1

    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [{'word': w, 'count': c} for w, c in sorted_words[:top_n]]


def analyze_scores(df: pd.DataFrame, score_cols: List[Dict]) -> Dict[str, Any]:
    """점수 컬럼별 평균, 분포 분석."""
    result = {}

    for col_info in score_cols:
        col_name = col_info['name']
        values = df[col_name].apply(extract_score_value).dropna()

        if len(values) == 0:
            continue

        distribution = {}
        for v in range(1, 6):
            distribution[v] = int((values == v).sum())

        # 짧은 라벨 추출 (컬럼명에서 대괄호 안 내용)
        label_match = re.search(r'\[(.+?)\]', col_name)
        short_label = label_match.group(1) if label_match else col_name[:30]

        result[col_name] = {
            'short_label': short_label,
            'mean': round(float(values.mean()), 2),
            'min': int(values.min()),
            'max': int(values.max()),
            'count': len(values),
            'distribution': distribution
        }

    return result


def analyze_multiselect(df: pd.DataFrame, ms_cols: List[Dict]) -> Dict[str, Any]:
    """복수선택 컬럼의 옵션별 카운트/비율 분석."""
    result = {}

    for col_info in ms_cols:
        col_name = col_info['name']
        total = len(df)
        option_count = {}

        for val in df[col_name]:
            options = parse_multiselect(val)
            for opt in options:
                option_count[opt] = option_count.get(opt, 0) + 1

        sorted_options = sorted(option_count.items(), key=lambda x: x[1], reverse=True)
        options_list = []
        for label, count in sorted_options:
            options_list.append({
                'label': label,
                'count': count,
                'pct': round(count / total * 100, 1) if total > 0 else 0
            })

        result[col_name] = {
            'total_responses': total,
            'options': options_list
        }

    return result


def analyze_freetext(df: pd.DataFrame, ft_cols: List[Dict]) -> Dict[str, Any]:
    """주관식 컬럼의 키워드 빈도 + 대표 응답 추출."""
    result = {}

    for col_info in ft_cols:
        col_name = col_info['name']
        texts = df[col_name].dropna().astype(str).tolist()
        valid_texts = [t for t in texts if t.strip() and t.lower() != 'nan']

        keywords = extract_keywords(valid_texts)
        samples = valid_texts[:10]  # 최대 10개 대표 응답

        result[col_name] = {
            'response_count': len(valid_texts),
            'top_keywords': keywords,
            'samples': samples
        }

    return result


def analyze_singleselect(df: pd.DataFrame, ss_cols: List[Dict]) -> Dict[str, Any]:
    """단일선택 컬럼의 값별 분포."""
    result = {}

    for col_info in ss_cols:
        col_name = col_info['name']
        counts = df[col_name].dropna().astype(str).value_counts()
        total = counts.sum()

        value_list = []
        for val, cnt in counts.items():
            val_str = str(val).strip()
            if val_str and val_str.lower() != 'nan':
                value_list.append({
                    'label': val_str,
                    'count': int(cnt),
                    'pct': round(cnt / total * 100, 1) if total > 0 else 0
                })

        result[col_name] = {
            'total_responses': int(total),
            'values': value_list
        }

    return result


def generate_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """분석 결과를 바탕으로 자동 개선 제안 생성."""
    recs = []

    # 1. 낮은 만족도 영역
    score_data = analysis.get('score_analysis', {})
    low_scores = []
    high_scores = []
    for col_name, data in score_data.items():
        mean = data.get('mean', 0)
        label = data.get('short_label', col_name[:20])
        if mean < 3.0:
            low_scores.append((label, mean))
        elif mean >= 4.5:
            high_scores.append((label, mean))

    if low_scores:
        areas = ', '.join([f"'{l}' ({m:.1f}점)" for l, m in low_scores])
        recs.append(
            f"[긴급 개선] 만족도가 낮은 영역: {areas}. "
            f"해당 영역의 서비스 품질 점검 및 개선 프로세스를 즉시 수립하세요."
        )

    if high_scores:
        areas = ', '.join([f"'{l}' ({m:.1f}점)" for l, m in high_scores])
        recs.append(
            f"[강점 유지] 높은 만족도 영역: {areas}. "
            f"이 강점을 대외 마케팅 포인트 및 신규 거래처 영업 시 활용하세요."
        )

    # 2. 최다 불만 사유
    ms_data = analysis.get('multiselect_analysis', {})
    for col_name, data in ms_data.items():
        options = data.get('options', [])
        if options:
            top = options[0]
            if top['pct'] > 30:
                recs.append(
                    f"[핵심 원인] '{top['label']}'이(가) {top['pct']:.0f}%로 "
                    f"가장 많이 선택됨. 이에 대한 구체적 대응 전략을 마련하세요."
                )

    # 3. 재거래 의향 분석
    for col_name, data in score_data.items():
        if '재' in col_name or '의향' in col_name or '거래' in col_name:
            dist = data.get('distribution', {})
            total = sum(dist.values())
            high_interest = dist.get(4, 0) + dist.get(5, 0)
            if total > 0 and high_interest > 0:
                pct = high_interest / total * 100
                recs.append(
                    f"[재계약 기회] 재거래 의향 4-5점 응답자 {high_interest}명({pct:.0f}%). "
                    f"개선 사항 적용 후 해당 거래처 대상 재계약 프로모션을 추진하세요."
                )

    # 4. 단일선택 분석
    ss_data = analysis.get('singleselect_analysis', {})
    for col_name, data in ss_data.items():
        if '재개' in col_name or '계획' in col_name:
            values = data.get('values', [])
            for v in values:
                if '없음' in v['label'] and v['pct'] > 50:
                    recs.append(
                        f"[위험 신호] 재개 계획 없음 응답이 {v['pct']:.0f}%. "
                        f"이탈 고객 복귀를 위한 특별 프로모션이나 서비스 개선안을 제시하세요."
                    )

    # 5. 주관식 피드백 인사이트
    ft_data = analysis.get('freetext_analysis', {})
    for col_name, data in ft_data.items():
        keywords = data.get('top_keywords', [])
        if '고쳐' in col_name or '개선' in col_name or '불만' in col_name:
            if keywords:
                top_words = ', '.join([kw['word'] for kw in keywords[:5]])
                recs.append(
                    f"[고객 목소리] 주요 불만 키워드: {top_words}. "
                    f"해당 키워드 관련 프로세스를 점검하고 구체적 개선 방안을 수립하세요."
                )

    if not recs:
        recs.append(
            "전반적으로 양호한 피드백입니다. 세부 응답을 검토하여 잠재적 개선 포인트를 발굴하세요."
        )

    return recs


def detect_months(df: pd.DataFrame) -> List[str]:
    """DataFrame에서 타임스탬프 컬럼을 찾아 YYYY-MM 월 목록 반환."""
    months = set()
    for col in df.columns:
        col_type = classify_column(df[col], col)
        if col_type == 'timestamp':
            try:
                dt_series = pd.to_datetime(df[col], errors='coerce').dropna()
                for dt in dt_series:
                    months.add(dt.strftime('%Y-%m'))
            except Exception:
                pass
            break  # 첫 번째 타임스탬프 컬럼만 사용
    return sorted(months)


def filter_df_by_months(df: pd.DataFrame, selected_months: List[str]) -> pd.DataFrame:
    """타임스탬프 컬럼을 기준으로 선택된 월만 필터링."""
    if not selected_months:
        return df

    for col in df.columns:
        col_type = classify_column(df[col], col)
        if col_type == 'timestamp':
            try:
                dt_series = pd.to_datetime(df[col], errors='coerce')
                month_series = dt_series.dt.strftime('%Y-%m')
                mask = month_series.isin(selected_months)
                return df[mask].reset_index(drop=True)
            except Exception:
                pass
            break

    return df


def process_feedback(files: list, df_override: pd.DataFrame = None) -> Dict[str, Any]:
    """
    메인 피드백 처리 함수.
    파일 읽기 → 컬럼 분류 → 타입별 분석 → 개선 제안 생성.
    df_override가 있으면 파일 읽기를 건너뛰고 해당 DataFrame 사용.
    """
    if df_override is not None:
        df = df_override
    else:
        # 첫 번째 유효한 파일 읽기
        df = None
        for f in files:
            df = load_feedback_file(f)
            if df is not None and len(df) > 0:
                break

    if df is None or len(df) == 0:
        return {'error': '유효한 피드백 데이터를 찾을 수 없습니다.'}

    # 컬럼 분류
    columns = []
    for col in df.columns:
        col_type = classify_column(df[col], col)
        stats = {}

        if col_type == 'timestamp':
            try:
                dt_series = pd.to_datetime(df[col], errors='coerce').dropna()
                if len(dt_series) > 0:
                    stats['min_date'] = str(dt_series.min().strftime('%Y-%m-%d'))
                    stats['max_date'] = str(dt_series.max().strftime('%Y-%m-%d'))
            except Exception:
                pass

        elif col_type == 'score':
            vals = df[col].apply(extract_score_value).dropna()
            if len(vals) > 0:
                stats['mean'] = round(float(vals.mean()), 2)
                stats['count'] = len(vals)

        columns.append({
            'name': col,
            'col_type': col_type,
            'stats': stats
        })

    # 타입별 그룹핑
    score_cols = [c for c in columns if c['col_type'] == 'score']
    ms_cols = [c for c in columns if c['col_type'] == 'multi_select']
    ft_cols = [c for c in columns if c['col_type'] == 'free_text']
    ss_cols = [c for c in columns if c['col_type'] == 'single_select']
    ts_cols = [c for c in columns if c['col_type'] == 'timestamp']
    id_cols = [c for c in columns if c['col_type'] == 'identifier']

    # 개요
    overview = {
        'response_count': len(df),
        'column_count': len(df.columns),
    }

    if ts_cols:
        ts_col = ts_cols[0]
        overview['date_range'] = f"{ts_col['stats'].get('min_date', '?')} ~ {ts_col['stats'].get('max_date', '?')}"
    else:
        overview['date_range'] = ''

    if id_cols:
        overview['identifier_col'] = id_cols[0]['name']
    else:
        overview['identifier_col'] = ''

    # 전체 평균 만족도
    if score_cols:
        all_means = [c['stats'].get('mean', 0) for c in score_cols if c['stats'].get('mean')]
        overview['avg_satisfaction'] = round(sum(all_means) / len(all_means), 2) if all_means else 0
    else:
        overview['avg_satisfaction'] = 0

    # 타입별 분석
    score_analysis = analyze_scores(df, score_cols)
    multiselect_analysis = analyze_multiselect(df, ms_cols)
    freetext_analysis = analyze_freetext(df, ft_cols)
    singleselect_analysis = analyze_singleselect(df, ss_cols)

    # 응답자별 상세
    respondent_details = df.to_dict('records')

    # 분석 결과 취합
    analysis = {
        'overview': overview,
        'columns': columns,
        'score_analysis': score_analysis,
        'multiselect_analysis': multiselect_analysis,
        'freetext_analysis': freetext_analysis,
        'singleselect_analysis': singleselect_analysis,
        'respondent_details': respondent_details,
    }

    # 개선 제안 생성
    analysis['recommendations'] = generate_recommendations(analysis)

    return analysis
