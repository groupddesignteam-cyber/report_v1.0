import json
import os
import re

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


CLAUDE_MODEL = "claude-3-haiku-20240307"
OPENAI_MODEL = "gpt-4o-mini"


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


def generate_executive_summary(dept_results: dict) -> str:
    if is_llm_test_mode():
        return "[테스트 모드] AI 요약이 비활성화되었습니다.\n이 모드에서는 LLM API 호출을 건너뛰어 빠르게 UI를 테스트할 수 있습니다.\n사이드바에서 테스트 모드를 해제하면 실제 AI 요약이 생성됩니다."

    context = ""
    for dept, data in dept_results.items():
        if not data:
            continue
        current = data.get("current_month_data", {})
        kpi = data.get("kpi", {})
        context += f"-[{dept}]: {current}, KPI: {kpi}\n"

    prompt = f"""당신은 병원 전문 마케팅 총괄 디렉터입니다.
다음은 각 마케팅/디자인/영상 팀의 이번 달 성과 및 핵심 KPI 데이터입니다.

Data:
{context}

[요청 사항]
1. 위 데이터를 바탕으로 전체 성과에 대한 핵심 3줄 요약을 작성해 주세요.
2. 단순한 기계적 수치 나열(예: 포스팅 10건, 지출 1만원)은 절대 금지합니다.
3. 이 데이터를 근거로, 각 팀의 팀장들이 다음 달에 고객(병원)에게 어떤 '실행 상품 제안(Action Plan)'을 기획하고 집중해야 하는지 전략적이고 구체적인 인사이트를 포함해 주세요.
4. 반드시 3줄의 한국어 문장으로 명확하고 친근한 비즈니스 톤으로 작성해 주세요 (번호 매기기 없이 줄바꿈으로만 3줄 구분).
"""

    try:
        text = _call_llm(prompt, max_tokens=500, temperature=0.5, json_mode=False)
        if not text:
            return "API key가 설정되지 않았습니다. Streamlit의 Secrets(ANTHROPIC_API_KEY 또는 OPENAI_API_KEY)에 값을 넣고 재시도하세요."
        return text
    except Exception as e:
        return f"Summary generation failed: {str(e)}"
