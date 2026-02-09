"""
고객 피드백 분석 HTML 보고서 생성
- Jinja2 + Tailwind CSS (기존 html_generator.py 패턴 동일)
"""

from datetime import datetime
from typing import Dict, Any
from jinja2 import Template


FEEDBACK_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Noto Sans KR', sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .gradient-bg { background: linear-gradient(135deg, #451a03 0%, #78350f 50%, #92400e 100%); }
        .card { background: white; border-radius: 1rem; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08); overflow: hidden; }
        .fade-in { animation: fadeIn 0.7s cubic-bezier(0.4, 0, 0.2, 1) forwards; opacity: 0; transform: translateY(12px); }
        @keyframes fadeIn { to { opacity: 1; transform: translateY(0); } }
        .delay-1 { animation-delay: 0.15s; }
        .delay-2 { animation-delay: 0.3s; }
        .delay-3 { animation-delay: 0.45s; }
        .strategy-card { border-left: 4px solid; transition: transform 0.2s, box-shadow 0.2s; }
        .strategy-card:hover { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(0,0,0,0.15); }
        .bar-fill { transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1); }
        details summary::-webkit-details-marker { display: none; }
        details summary { cursor: pointer; }
        @media print {
            .no-print { display: none !important; }
            .page-break { page-break-before: always; }
        }
    </style>
</head>
<body class="bg-slate-50 text-slate-800">

    <!-- ===== HEADER ===== -->
    <div class="gradient-bg text-white">
        <div class="max-w-5xl mx-auto px-6 py-12 text-center fade-in">
            <div class="inline-block px-3 py-1 bg-amber-400/20 border border-amber-400/30 rounded-full text-amber-300 text-[10px] font-bold uppercase tracking-widest mb-4">
                Feedback Analysis Report
            </div>
            <h1 class="text-3xl font-black tracking-tight mb-2">{{ report_title }}</h1>
            <p class="text-amber-200/70 text-sm">{{ report_date }}</p>
            <div class="flex justify-center gap-6 mt-6">
                <div class="text-center">
                    <p class="text-2xl font-black text-amber-300">{{ overview.response_count }}</p>
                    <p class="text-[10px] text-amber-200/60 uppercase">응답 수</p>
                </div>
                {% if overview.avg_satisfaction > 0 %}
                <div class="text-center">
                    <p class="text-2xl font-black text-amber-300">{{ overview.avg_satisfaction }}점</p>
                    <p class="text-[10px] text-amber-200/60 uppercase">평균 만족도</p>
                </div>
                {% endif %}
                {% if overview.date_range %}
                <div class="text-center">
                    <p class="text-sm font-bold text-amber-300 mt-1">{{ overview.date_range }}</p>
                    <p class="text-[10px] text-amber-200/60 uppercase">응답 기간</p>
                </div>
                {% endif %}
            </div>
        </div>
    </div>

    <div class="max-w-5xl mx-auto px-6 py-8 space-y-8">

        <!-- ===== 컬럼 감지 요약 ===== -->
        <div class="card p-6 fade-in delay-1">
            <h2 class="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                <i data-lucide="scan-search" class="w-4 h-4"></i> 데이터 구조 감지 결과
            </h2>
            <div class="flex flex-wrap gap-2">
                {% for col in columns %}
                {% set type_colors = {
                    'timestamp': 'bg-blue-50 text-blue-700 border-blue-200',
                    'identifier': 'bg-purple-50 text-purple-700 border-purple-200',
                    'score': 'bg-green-50 text-green-700 border-green-200',
                    'multi_select': 'bg-amber-50 text-amber-700 border-amber-200',
                    'single_select': 'bg-cyan-50 text-cyan-700 border-cyan-200',
                    'free_text': 'bg-slate-50 text-slate-600 border-slate-200'
                } %}
                {% set type_labels = {
                    'timestamp': '날짜',
                    'identifier': '식별자',
                    'score': '점수',
                    'multi_select': '객관식(복수)',
                    'single_select': '객관식(단일)',
                    'free_text': '주관식'
                } %}
                <span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg border text-[11px] font-medium {{ type_colors.get(col.col_type, 'bg-slate-50 text-slate-600 border-slate-200') }}">
                    <span class="font-bold">{{ type_labels.get(col.col_type, col.col_type) }}</span>
                    <span class="opacity-60">{{ col.name[:25] }}{% if col.name|length > 25 %}...{% endif %}</span>
                </span>
                {% endfor %}
            </div>
        </div>

        <!-- ===== 객관식(복수) 분석 ===== -->
        {% if multiselect_analysis %}
        {% for col_name, data in multiselect_analysis.items() %}
        <div class="card p-6 fade-in delay-2">
            <h2 class="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">
                <i data-lucide="bar-chart-3" class="w-4 h-4 text-amber-500"></i> 객관식 분석
            </h2>
            <p class="text-xs text-slate-400 mb-4">{{ col_name }}</p>
            <div class="space-y-3">
                {% for opt in data.options %}
                <div>
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-sm text-slate-700 font-medium">{{ opt.label }}</span>
                        <span class="text-xs font-bold text-slate-500">{{ opt.count }}건 ({{ opt.pct }}%)</span>
                    </div>
                    <div class="bg-slate-100 rounded-full h-5 overflow-hidden">
                        <div class="bar-fill h-full rounded-full flex items-center pl-2"
                             style="width: {{ opt.pct }}%; background: linear-gradient(90deg, #f59e0b, #d97706);">
                            {% if opt.pct > 15 %}
                            <span class="text-[10px] font-bold text-white">{{ opt.pct }}%</span>
                            {% endif %}
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
        {% endif %}

        <!-- ===== 만족도 점수 분석 ===== -->
        {% if score_analysis %}
        <div class="card p-6 fade-in delay-2">
            <h2 class="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                <i data-lucide="star" class="w-4 h-4 text-green-500"></i> 영역별 만족도
            </h2>
            <div class="space-y-4">
                {% for col_name, data in score_analysis.items() %}
                <div class="bg-slate-50 rounded-xl p-4">
                    <div class="flex justify-between items-center mb-2">
                        <span class="text-sm font-bold text-slate-700">{{ data.short_label }}</span>
                        <span class="text-lg font-black {% if data.mean < 3 %}text-red-500{% elif data.mean < 4 %}text-amber-500{% else %}text-green-500{% endif %}">
                            {{ data.mean }}점
                        </span>
                    </div>
                    <!-- Score bar -->
                    <div class="bg-slate-200 rounded-full h-3 overflow-hidden mb-2">
                        {% set pct = (data.mean / 5 * 100)|round %}
                        <div class="h-full rounded-full bar-fill"
                             style="width: {{ pct }}%; background: {% if data.mean < 3 %}#ef4444{% elif data.mean < 4 %}#f59e0b{% else %}#10b981{% endif %};">
                        </div>
                    </div>
                    <!-- Distribution dots -->
                    <div class="flex gap-3 text-[10px] text-slate-400">
                        {% for i in range(1, 6) %}
                        <span>{{ i }}점: <strong class="text-slate-600">{{ data.distribution.get(i, 0) }}명</strong></span>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>

            <!-- 평균 종합 -->
            {% if score_analysis|length > 1 %}
            <div class="mt-4 pt-4 border-t border-slate-200 text-center">
                <span class="text-xs text-slate-400">전체 평균</span>
                {% set total_mean = [] %}
                {% for _, d in score_analysis.items() %}{% if total_mean.append(d.mean) %}{% endif %}{% endfor %}
                {% set avg = (total_mean|sum / total_mean|length)|round(1) %}
                <span class="text-xl font-black ml-2 {% if avg < 3 %}text-red-500{% elif avg < 4 %}text-amber-500{% else %}text-green-500{% endif %}">
                    {{ avg }}점
                </span>
            </div>
            {% endif %}
        </div>
        {% endif %}

        <!-- ===== 단일선택 분석 ===== -->
        {% if singleselect_analysis %}
        {% for col_name, data in singleselect_analysis.items() %}
        <div class="card p-6 fade-in delay-2">
            <h2 class="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">
                <i data-lucide="pie-chart" class="w-4 h-4 text-cyan-500"></i> 응답 분포
            </h2>
            <p class="text-xs text-slate-400 mb-4">{{ col_name }}</p>
            <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
                {% set colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#6366f1'] %}
                {% for val in data.values %}
                <div class="bg-slate-50 rounded-xl p-3 text-center border border-slate-100">
                    <p class="text-xl font-black" style="color: {{ colors[loop.index0 % 6] }};">{{ val.count }}건</p>
                    <p class="text-[11px] text-slate-500 font-medium mt-1">{{ val.label }}</p>
                    <p class="text-[10px] text-slate-400">({{ val.pct }}%)</p>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
        {% endif %}

        <!-- ===== 주관식 피드백 ===== -->
        {% if freetext_analysis %}
        {% for col_name, data in freetext_analysis.items() %}
        <div class="card p-6 fade-in delay-3">
            <h2 class="text-sm font-bold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">
                <i data-lucide="message-square-text" class="w-4 h-4 text-slate-400"></i> 주관식 응답
            </h2>
            <p class="text-xs text-slate-400 mb-4">{{ col_name }} ({{ data.response_count }}건)</p>

            {% if data.top_keywords %}
            <div class="mb-4">
                <p class="text-[10px] font-bold text-slate-400 uppercase mb-2">주요 키워드</p>
                <div class="flex flex-wrap gap-1.5">
                    {% for kw in data.top_keywords[:12] %}
                    {% set size = 'text-sm font-bold' if loop.index <= 3 else 'text-xs' %}
                    {% set opacity = 'opacity-100' if loop.index <= 3 else 'opacity-80' if loop.index <= 6 else 'opacity-60' %}
                    <span class="inline-block px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md {{ size }} {{ opacity }}">
                        {{ kw.word }} <span class="text-slate-400 text-[10px]">{{ kw.count }}</span>
                    </span>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <div class="space-y-2">
                <p class="text-[10px] font-bold text-slate-400 uppercase">대표 응답</p>
                {% for sample in data.samples[:5] %}
                <div class="bg-slate-50 rounded-lg p-3 border-l-3 border-slate-200">
                    <p class="text-xs text-slate-600 leading-relaxed">{{ sample }}</p>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
        {% endif %}

        <!-- ===== 개선 제안 & 워크플랜 ===== -->
        {% if recommendations %}
        <div class="gradient-bg rounded-2xl p-6 text-white fade-in delay-3">
            <div class="flex items-center gap-3 mb-6">
                <div class="bg-amber-400/20 p-2.5 rounded-xl border border-amber-400/20">
                    <i data-lucide="lightbulb" class="w-6 h-6 text-amber-400"></i>
                </div>
                <div>
                    <h2 class="text-xl font-bold">개선 제안 & 워크플랜</h2>
                    <p class="text-[10px] text-amber-200/60 uppercase tracking-wider mt-0.5">Recommendations & Action Plan</p>
                </div>
            </div>
            <div class="space-y-3">
                {% set rec_colors = ['#f59e0b', '#ef4444', '#10b981', '#3b82f6', '#8b5cf6'] %}
                {% for rec in recommendations %}
                <div class="strategy-card bg-slate-800/50 p-4 rounded-xl" style="border-left-color: {{ rec_colors[loop.index0 % 5] }};">
                    <p class="text-sm text-slate-300 leading-relaxed">{{ rec }}</p>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- ===== 응답자별 상세 ===== -->
        {% if respondent_details %}
        <div class="card p-6 fade-in delay-3">
            <h2 class="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                <i data-lucide="users" class="w-4 h-4 text-purple-500"></i> 응답자별 상세 ({{ respondent_details|length }}건)
            </h2>
            <div class="space-y-2">
                {% for row in respondent_details %}
                <details class="bg-slate-50 rounded-xl overflow-hidden border border-slate-100">
                    <summary class="px-4 py-3 flex items-center justify-between hover:bg-slate-100 transition-colors">
                        <span class="text-sm font-bold text-slate-700">
                            {% if identifier_col and row.get(identifier_col) %}
                                {{ row[identifier_col] }}
                            {% else %}
                                응답자 {{ loop.index }}
                            {% endif %}
                        </span>
                        <i data-lucide="chevron-down" class="w-4 h-4 text-slate-400"></i>
                    </summary>
                    <div class="px-4 pb-4 space-y-2">
                        {% for col in columns %}
                        {% set val = row.get(col.name, '') %}
                        {% if val is not none and val|string|trim and val|string|lower != 'nan' and val|string|lower != 'nat' %}
                        <div class="flex gap-2">
                            <span class="text-[10px] font-bold text-slate-400 uppercase shrink-0 w-24 pt-0.5">{{ col.name[:20] }}</span>
                            <span class="text-xs text-slate-600">{{ val }}</span>
                        </div>
                        {% endif %}
                        {% endfor %}
                    </div>
                </details>
                {% endfor %}
            </div>
        </div>
        {% endif %}

    </div>

    <!-- Footer -->
    <div class="text-center py-8 text-xs text-slate-400">
        <p>Generated by Group-D 전략보고서 시스템 | {{ report_date }}</p>
    </div>

    <script>
        lucide.createIcons();
    </script>
</body>
</html>
"""


def generate_feedback_html_report(
    analysis: Dict[str, Any],
    report_title: str = "고객 피드백 분석 보고서",
    report_date: str = None,
) -> str:
    """피드백 분석 결과로 HTML 보고서를 생성."""
    if report_date is None:
        report_date = datetime.now().strftime('%Y년 %m월 %d일')

    overview = analysis.get('overview', {})
    identifier_col = overview.get('identifier_col', '')

    template = Template(FEEDBACK_HTML_TEMPLATE)
    return template.render(
        report_title=report_title,
        report_date=report_date,
        overview=overview,
        columns=analysis.get('columns', []),
        score_analysis=analysis.get('score_analysis', {}),
        multiselect_analysis=analysis.get('multiselect_analysis', {}),
        freetext_analysis=analysis.get('freetext_analysis', {}),
        singleselect_analysis=analysis.get('singleselect_analysis', {}),
        respondent_details=analysis.get('respondent_details', []),
        recommendations=analysis.get('recommendations', []),
        identifier_col=identifier_col,
    )


def get_feedback_report_filename() -> str:
    """피드백 보고서 파일명 생성."""
    return f"Feedback_Analysis_{datetime.now().strftime('%Y%m%d')}.html"
