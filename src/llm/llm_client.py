import json
import os
import re
import time

import streamlit as st


def is_llm_test_mode() -> bool:
    """LLM 테스트 모드 여부. True이면 API 호출 스킵."""
    return bool(st.session_state.get("llm_test_mode", False))

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _strip_code_fences(text: str) -> str:
    if not text:
        return ""

    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return t.strip()


def _extract_response_text(response) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return str(content).strip()

    for item in content:
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            if item.get("text") is not None:
                return str(item.get("text", "")).strip()
            if item.get("content") is not None:
                return str(item.get("content", "")).strip()
        else:
            text = getattr(item, "text", None)
            if text is not None:
                return str(text).strip()

    return str(content).strip()


CLAUDE_MODEL = "claude-sonnet-4-20250514"
OPENAI_MODEL = "gpt-4o-mini"

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]


def _is_anthropic_key(key: str) -> bool:
    if not isinstance(key, str):
        return False
    return key.startswith("sk-ant-") or key.startswith("sk-ant-api")


def _is_openai_key(key: str) -> bool:
    if not isinstance(key, str):
        return False
    return key.startswith("sk-proj-") or (key.startswith("sk-") and len(key) > 10)


def _get_value(secret_keys, env_keys):
    for name in secret_keys:
        try:
            value = st.secrets.get(name)
            if value:
                return str(value).strip()
        except Exception:
            pass

    for name in env_keys:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return None


def _configured_provider() -> str:
    for key in ("LLM_PROVIDER", "LLM_PROVIDER_NAME", "AI_PROVIDER"):
        try:
            value = st.secrets.get(key)
            if value:
                return str(value).strip().lower()
        except Exception:
            pass
        value = os.environ.get(key)
        if value:
            return value.strip().lower()
    return ""


def get_claude_client():
    """
    Return a tuple: (provider, client)
    provider = "anthropic" | "openai" | None
    """
    provider = _configured_provider()

    if provider in {"anthropic", "claude"}:
        key = _get_value(
            ("ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "CLAUDE_API_KEY"),
            ("ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "CLAUDE_API_KEY"),
        )
        if key and _is_anthropic_key(key) and Anthropic is not None:
            return "anthropic", Anthropic(api_key=key)
        # Fallback: if provider is set to anthropic but key is missing/invalid,
        # try OpenAI key as a compatibility fallback (keeps behavior resilient).
        key = _get_value(
            ("OPENAI_API_KEY", "OPENAI_KEY", "GPT_API_KEY"),
            ("OPENAI_API_KEY", "OPENAI_KEY", "GPT_API_KEY"),
        )
        if key and _is_openai_key(key) and OpenAI is not None:
            return "openai", OpenAI(api_key=key)
        return None, None

    if provider in {"openai", "gpt", "chatgpt"}:
        key = _get_value(
            ("OPENAI_API_KEY", "OPENAI_KEY", "GPT_API_KEY"),
            ("OPENAI_API_KEY", "OPENAI_KEY", "GPT_API_KEY"),
        )
        if key and _is_openai_key(key) and OpenAI is not None:
            return "openai", OpenAI(api_key=key)
        # Fallback: if provider is set to openai but key is missing/invalid,
        # try Anthropic key as a secondary option.
        key = _get_value(
            ("ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "CLAUDE_API_KEY"),
            ("ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "CLAUDE_API_KEY"),
        )
        if key and _is_anthropic_key(key) and Anthropic is not None:
            return "anthropic", Anthropic(api_key=key)
        return None, None

    # Auto-detect: Anthropic key first, then OpenAI.
    key = _get_value(
        ("ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "CLAUDE_API_KEY"),
        ("ANTHROPIC_API_KEY", "ANTHROPIC_KEY", "CLAUDE_API_KEY"),
    )
    if key:
        if _is_anthropic_key(key) and Anthropic is not None:
            return "anthropic", Anthropic(api_key=key)
        if _is_openai_key(key) and OpenAI is not None:
            return "openai", OpenAI(api_key=key)

    key = _get_value(
        ("OPENAI_API_KEY", "OPENAI_KEY", "GPT_API_KEY"),
        ("OPENAI_API_KEY", "OPENAI_KEY", "GPT_API_KEY"),
    )
    if key and _is_openai_key(key) and OpenAI is not None:
        return "openai", OpenAI(api_key=key)

    return None, None


def _call_llm(prompt: str, max_tokens: int, temperature: float, *, json_mode: bool = False):
    provider, client = get_claude_client()
    if not provider or not client:
        return None

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            if provider == "anthropic":
                response = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                return _extract_response_text(response)

            if provider == "openai":
                payload = {
                    "model": OPENAI_MODEL,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if json_mode:
                    try:
                        response = client.chat.completions.create(
                            response_format={"type": "json_object"},
                            **payload,
                        )
                    except Exception:
                        response = client.chat.completions.create(**payload)
                else:
                    response = client.chat.completions.create(**payload)

                choices = getattr(response, "choices", [])
                if not choices:
                    return None
                return str(getattr(choices[0].message, "content", "")).strip()

            return None

        except Exception as e:
            last_error = e
            error_str = str(e)
            status_code = getattr(e, 'status_code', None)
            is_retryable = (
                status_code in (429, 500, 529)
                or '529' in error_str
                or 'overloaded' in error_str.lower()
            )
            if is_retryable and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])
                continue
            raise


def has_llm_client_configured() -> bool:
    if is_llm_test_mode():
        return False
    provider, client = get_claude_client()
    return bool(provider and client)


def generate_department_draft_and_strategy(dept_name: str, kpis: dict, previous_kpis: dict) -> dict:
    if is_llm_test_mode():
        return {
            "draft": f"[테스트 모드] {dept_name} 성과 총평 placeholder",
            "action_plan": [{"title": f"{dept_name} 테스트 항목 {i+1}", "detail": "테스트 모드 — LLM 호출 스킵"} for i in range(5)],
        }

    prompt = f"""당신은 병원 전문 마케팅 기획자(PM)입니다.
'{dept_name}' 부서의 이번 달 KPI 성과와 이전 달 성과를 바탕으로 1) 보고서에 들어갈 성과 총평(draft)과 2) 다음 달에 우리 부서 팀원들이 치과(클라이언트)를 위해 '실무적으로 직접 해줄 수 있는 핵심 서비스/업무' 5가지를 도출해주세요.

[데이터]
이번 달: {kpis}
지난 달: {previous_kpis}

[요청 사항]
1. 총평(draft)은 2~3문장으로 정중하고 전문적인 비즈니스 문체로 작성하세요.
2. 액션 플랜(Action Plan)은 추상적인 전략이 아니라, 우리 팀이 직접 수행할 수 있는 "구체적인 서비스/산출물" 단위여야 합니다. 
예시:
  - 마케팅팀: "네이버 예약 폼 변경", "예약 1일전 유도 해피콜 진행"
  - 디자인팀: "네이버 플레이스 이미지 리뉴얼", "원내 대기실 봄시즌 배너 제작"
  - 영상팀: "유튜브 쇼츠 3편 편집", "대기실 송출용 홍보 영상 제작"
  - 콘텐츠팀: "시즌 맞춤형 정보성 블로그 발행", "AEO 칼럼 기획"
3. 액션 플랜은 반드시 'title'(업무명/서비스명, 예: 네이버 예약 폼 수정)과 'detail'(구체적 설명/기대효과, 예: 신환/구환 구분을 위한 예약 폼 옵션 추가 및 안내 문구 개선)로 나누어 5개 작성하세요.
4. 반드시 아래 JSON 형식으로만 응답하세요. 다른 부연설명은 덧붙이지 마세요.

{{
  "draft": "간단한 리뷰 총평...",
  "action_plan": [
    {{
      "title": "업무명/서비스명",
      "detail": "구체적 실행 방안 및 효과..."
    }}
  ]
}}
"""

    try:
        text = _call_llm(prompt, max_tokens=1000, temperature=0.7, json_mode=True)
        if not text:
            return {
                "draft": "API key가 설정되지 않았습니다. Streamlit의 Secrets(ANTHROPIC_API_KEY 또는 OPENAI_API_KEY)에 값을 넣고 재시도하세요.",
                "action_plan": [{"text": "Please check API key and retry."}],
            }

        text = _strip_code_fences(text)
        return json.loads(text)
    except Exception as e:
        return {
            "draft": f"AI generation failed: {str(e)}",
            "action_plan": [{"text": "AI summary generation error."}],
        }


def generate_team_product_recommendations(
    team_name: str,
    blog_contract_count: float,
    team_kpis: dict,
    all_report_context: dict,
    catalog_candidates: list,
    max_items: int = 5,
) -> list:
    """
    Recommend up to max_items service/product items per team using KPI + catalog context.
    Returns: [{"title": "...", "detail": "...", "source_item": "...", ...}, ...]
    """
    if is_llm_test_mode():
        return [{"title": f"{team_name} 추천 {i+1}", "detail": "테스트 모드", "source_item": "", "category": "", "owner_dept": team_name, "status": "가능", "executor": "", "replacement_per_posting": 0, "estimated_needed_count": 0} for i in range(min(max_items, 3))]

    if not catalog_candidates:
        return []

    prompt = f"""You are planning team-level product/service recommendations for a monthly report.

Team: {team_name}
Blog contract count (current month): {blog_contract_count}
Team KPI: {team_kpis}
All report KPI context: {all_report_context}

Catalog candidates (must reference this list):
{catalog_candidates[:60]}

Rules:
1) Recommend exactly {max_items} items.
2) Recommendations must be grounded in the catalog candidates.
2-1) Prefer status='가능' first. Use status='보류' only if necessary. Avoid '불가' unless no other options.
2-2) Keep each recommendation tightly aligned with the given Team.
3) Include the replacement metric:
   estimated_needed_count = blog_contract_count * replacement_per_posting
4) Write Korean business-friendly copy for title/detail.
5) Output strict JSON only.

Output format:
{{
  "items": [
    {{
      "title": "추천명",
      "detail": "추천 이유와 실행 포인트",
      "source_item": "카탈로그 목록명",
      "category": "분류",
      "owner_dept": "주관 부서",
      "status": "상태",
      "executor": "실행 주체",
      "replacement_per_posting": 0,
      "estimated_needed_count": 0
    }}
  ]
}}
"""
    try:
        text = _call_llm(prompt, max_tokens=1800, temperature=0.3, json_mode=True)
        if not text:
            return []

        payload = json.loads(_strip_code_fences(text))
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            return []

        out = []
        for item in raw_items[:max_items]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            detail = str(item.get("detail", "")).strip()
            if not title:
                continue

            try:
                rpp = float(item.get("replacement_per_posting", 0))
            except Exception:
                rpp = 0.0
            try:
                needed = float(item.get("estimated_needed_count", blog_contract_count * rpp))
            except Exception:
                needed = blog_contract_count * rpp

            out.append(
                {
                    "title": title,
                    "detail": detail,
                    "source_item": str(item.get("source_item", "")).strip(),
                    "category": str(item.get("category", "")).strip(),
                    "owner_dept": str(item.get("owner_dept", "")).strip(),
                    "status": str(item.get("status", "")).strip(),
                    "executor": str(item.get("executor", "")).strip(),
                    "replacement_per_posting": rpp,
                    "estimated_needed_count": needed,
                }
            )

        return out
    except Exception:
        return []


def _fmt_num(val, fmt=",.0f"):
    try:
        return format(float(val), fmt)
    except (ValueError, TypeError):
        return str(val)


def _fmt_pct(val):
    try:
        v = float(val)
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.1f}%"
    except (ValueError, TypeError):
        return str(val)


def _join_items(items, key, count_key='count', unit='건', limit=3):
    """리스트 항목을 'name(count단위)' 형태로 join."""
    parts = []
    for item in items[:limit]:
        name = item.get(key, '?')
        cnt = item.get(count_key, 0)
        parts.append(f"{name}({_fmt_num(cnt)}{unit})")
    return ', '.join(parts)


def _join_titles(items, title_key='title', value_key='views', unit='회', limit=3):
    """제목+값 리스트를 join."""
    parts = []
    for item in items[:limit]:
        title = str(item.get(title_key, '?'))[:25]
        val = item.get(value_key, 0)
        parts.append(f'"{title}"({_fmt_num(val)}{unit})')
    return '; '.join(parts)


def _build_executive_context(dept_results: dict) -> str:
    """부서별 데이터를 구조화된 텍스트로 변환."""
    sections = []

    # 예약
    res = dept_results.get("reservation", {})
    if res and res.get("kpi"):
        kpi = res["kpi"]
        tables = res.get("tables", {})
        lines = [
            "## 예약 현황",
            f"- 총 예약: {_fmt_num(kpi.get('total_reservations', 0))}건 (전월 {_fmt_num(kpi.get('prev_total_reservations', 0))}건, {_fmt_pct(kpi.get('mom_growth', 0))})",
            f"- 이용완료: {_fmt_num(kpi.get('actual_reservations', 0))}건 (전월 {_fmt_num(kpi.get('prev_actual_reservations', 0))}건)",
            f"- 취소율: {kpi.get('cancel_rate', 0):.1f}% (전월 {kpi.get('prev_cancel_rate', 0):.1f}%)",
        ]
        cancel_reasons = tables.get("cancel_reason_top5", [])
        if cancel_reasons:
            lines.append("- 주요 취소 사유: " + _join_items(cancel_reasons, 'cancel_reason'))
        how_found = tables.get("how_found_top5", [])
        if how_found:
            lines.append("- 유입 경로: " + _join_items(how_found, 'how_found'))
        treatments = tables.get("treatment_top5", [])
        if treatments:
            lines.append("- 인기 진료: " + _join_items(treatments, 'treatment'))
        sections.append("\n".join(lines))

    # 광고
    ads = dept_results.get("ads", {})
    if ads and ads.get("kpi"):
        kpi = ads["kpi"]
        tables = ads.get("tables", {})
        lines = [
            "## 네이버 광고",
            f"- 소진액: {_fmt_num(kpi.get('total_spend', 0))}원 (전월 {_fmt_num(kpi.get('prev_total_spend', 0))}원, {_fmt_pct(kpi.get('spend_mom_growth', 0))})",
            f"- 노출: {_fmt_num(kpi.get('total_impressions', 0))} / 클릭: {_fmt_num(kpi.get('total_clicks', 0))} / CTR: {kpi.get('avg_ctr', 0):.2f}%",
            f"- CPA: {_fmt_num(kpi.get('cpa', 0))}원 (전월 {_fmt_num(kpi.get('prev_cpa', 0))}원, {_fmt_pct(kpi.get('cpa_growth', 0))})",
        ]
        top_kw = tables.get("keyword_top5_clicks", [])
        if top_kw:
            lines.append("- 클릭 TOP 키워드: " + _join_items(top_kw, 'keyword', 'clicks', '클릭'))
        sections.append("\n".join(lines))

    # 블로그
    blog = dept_results.get("blog", {})
    if blog and blog.get("kpi"):
        kpi = blog["kpi"]
        tables = blog.get("tables", {})
        lines = [
            "## 블로그 (콘텐츠팀)",
            f"- 계약: {_fmt_num(kpi.get('contract_count', 0))}건 / 발행: {_fmt_num(kpi.get('published_count', 0))}건 / 이월: {_fmt_num(kpi.get('carryover_count', 0))}건",
            f"- 달성률: {kpi.get('publish_completion_rate', 0):.1f}%",
            f"- 조회수: {_fmt_num(kpi.get('total_views', 0))} (전월 {_fmt_num(kpi.get('prev_total_views', 0))}, {_fmt_pct(kpi.get('views_mom_growth', 0))})",
        ]
        views_top = tables.get("views_top5", [])
        if views_top:
            lines.append("- 조회수 TOP3: " + _join_titles(views_top))
        source_top = tables.get("source_top5", [])
        if source_top:
            kws = ', '.join(str(s.get('source', s.get('keyword', '?'))) for s in source_top[:5])
            lines.append("- 주요 유입 검색어: " + kws)
        steady = tables.get("steady_sellers", [])
        if steady:
            lines.append(f"- 효자 콘텐츠(과거 인기글): {len(steady)}건")
        sections.append("\n".join(lines))

    # 유튜브
    yt = dept_results.get("youtube", {})
    if yt and yt.get("kpi"):
        kpi = yt["kpi"]
        tables = yt.get("tables", {})
        lines = [
            "## 유튜브 (영상팀)",
            f"- 계약: {_fmt_num(kpi.get('contract_count', 0))}건 / 완료: {_fmt_num(kpi.get('completed_count', 0))}건",
            f"- 조회수: {_fmt_num(kpi.get('total_views', 0))} (전월 {_fmt_num(kpi.get('prev_total_views', 0))}, {_fmt_pct(kpi.get('views_mom_growth', 0))})",
            f"- 노출 CTR: {kpi.get('avg_ctr', 0):.2f}% / 신규 구독: {_fmt_num(kpi.get('new_subscribers', 0))}명",
        ]
        top_vid = tables.get("top5_videos", [])
        if top_vid:
            lines.append("- 조회수 TOP3: " + _join_titles(top_vid))
        traffic = tables.get("traffic_by_source", [])
        if traffic:
            lines.append("- 트래픽 소스: " + _join_items(traffic, 'source', 'views', '회'))
        vt_stats = tables.get("video_type_stats", {})
        if vt_stats:
            for vt_name, vt_data in vt_stats.items():
                lines.append(f"  - {vt_name}: 계약 {_fmt_num(vt_data.get('contract', 0))}건 / 완료 {_fmt_num(vt_data.get('completed', 0))}건")
        sections.append("\n".join(lines))

    # 디자인
    design = dept_results.get("design", {})
    if design and design.get("kpi"):
        kpi = design["kpi"]
        lines = [
            "## 디자인팀",
            f"- 완료: {_fmt_num(kpi.get('completed_tasks', 0))}건 (전월대비 {_fmt_pct(kpi.get('mom_growth', 0))})",
            f"- 평균 수정: {kpi.get('avg_revision', 0):.1f}회 / 3회 이상 수정률: {kpi.get('heavy_revision_rate', 0):.1f}%",
        ]
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def generate_executive_summary(dept_results: dict, clinic_name: str = "") -> str:
    """전체 부서 데이터를 종합 분석하여 AI 전략 인사이트를 생성."""
    if is_llm_test_mode():
        return "[테스트 모드] AI 요약이 비활성화되었습니다.\n이 모드에서는 LLM API 호출을 건너뛰어 빠르게 UI를 테스트할 수 있습니다.\n사이드바에서 테스트 모드를 해제하면 실제 AI 요약이 생성됩니다."

    context = _build_executive_context(dept_results)
    if not context.strip():
        return "분석할 데이터가 없습니다. 파일을 업로드한 후 다시 시도해 주세요."

    report_month = ""
    for dept_key in ["reservation", "blog", "youtube", "ads", "design"]:
        dept = dept_results.get(dept_key, {})
        if dept.get("month"):
            report_month = dept["month"]
            break

    clinic_display = clinic_name or "해당 치과"

    prompt = f"""당신은 10년 이상의 경력을 보유한 병원 전문 마케팅 총괄 디렉터(CMO)입니다.
아래는 '{clinic_display}'의 {report_month} 월간 마케팅 성과 데이터입니다.

━━━━━━━━━━━━━━━━━━━━━━━━
{context}
━━━━━━━━━━━━━━━━━━━━━━━━

위 데이터를 종합적으로 분석하여 경영진/팀장을 위한 '마케팅 전략 인사이트'를 작성해 주세요.

[작성 규칙]
1. 각 팀(예약/광고/블로그/유튜브/디자인)의 핵심 지표(증감률, 조회수, 달성률, CTR, CPA 등)를 구체적으로 언급하며 분석할 것
2. 단순 수치 나열이 아닌, 수치가 의미하는 바와 원인을 해석할 것
3. 팀 간 교차 분석(예: 광고 키워드 → 블로그 유입, 유튜브 콘텐츠 → 예약 전환)을 포함할 것
4. 잘된 성과는 적극적으로 강조하고 인정할 것
5. 미달 성과는 사실을 밝히되, 원인/배경(리소스 부족, 시기적 요인, 전략 전환기 등)으로 합리적 명분을 제시할 것
6. 마지막에 미달 성과를 개선할 구체적 실행 방향을 "다음 달에는 ~하겠습니다" 톤으로 제안할 것
7. 한국어 비즈니스 문체, 전문 컨설턴트가 클라이언트에게 보고하는 톤으로 작성할 것

[문단 구성 — 반드시 아래 4개 문단으로 나눠서 작성]
① 종합 진단 (전체 성과 핵심 요약 — 긍정 시그널 강조)
② 채널별 성과 분석 (주요 지표 구체적 언급 + 잘한 점 강조, 미달 점은 원인과 함께)
③ 교차 분석 (팀 간 시너지, 유입→전환 흐름 해석)
④ 개선 방향 제안 ("다음 달에는 ~를 통해 ~하겠습니다" 형태의 실행 계획)

각 문단 사이에 반드시 빈 줄(줄바꿈 2회)을 넣어 시각적으로 명확히 구분할 것.

[핵심 제약]
- 700자 이상 800자 이내로 작성할 것 (공백 포함, 반드시 준수)
- 제목/소제목/이모지/번호 매기기 없이 본문만 작성할 것
"""

    try:
        text = _call_llm(prompt, max_tokens=1000, temperature=0.4, json_mode=False)
        if not text:
            return "API key가 설정되지 않았습니다. Streamlit의 Secrets(ANTHROPIC_API_KEY 또는 OPENAI_API_KEY)에 값을 넣고 재시도하세요."
        return text
    except Exception as e:
        return f"AI 요약 생성 실패: {str(e)}"
