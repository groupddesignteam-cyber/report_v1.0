"""
고객 피드백 분석 HTML 보고서 생성
- Jinja2 + Tailwind CSS
- Premium consulting report design
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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Noto Sans KR', 'Inter', sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #f8fafc; }
        .num-font { font-family: 'Inter', 'Noto Sans KR', sans-serif; }

        /* Hero gradient */
        .hero-bg {
            background: linear-gradient(160deg, #0c0a09 0%, #1c1917 35%, #292524 60%, #44403c 100%);
            position: relative; overflow: hidden;
        }
        .hero-bg::before {
            content: ''; position: absolute; top: -50%; right: -30%; width: 80%; height: 200%;
            background: radial-gradient(ellipse, rgba(245,158,11,0.08) 0%, transparent 70%);
            pointer-events: none;
        }

        /* Glass card */
        .glass { background: rgba(255,255,255,0.06); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); }

        /* Card base */
        .card {
            background: white; border-radius: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.06);
            overflow: hidden; border: 1px solid #f1f5f9;
        }

        /* Animations */
        .fade-up { animation: fadeUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards; opacity: 0; }
        @keyframes fadeUp { to { opacity: 1; transform: translateY(0); } }
        .fade-up { transform: translateY(16px); }
        .d1 { animation-delay: 0.1s; } .d2 { animation-delay: 0.2s; } .d3 { animation-delay: 0.3s; }
        .d4 { animation-delay: 0.4s; } .d5 { animation-delay: 0.5s; } .d6 { animation-delay: 0.6s; }

        /* Bar animation */
        .bar-fill { transition: width 1s cubic-bezier(0.22, 1, 0.36, 1); }

        /* Score gauge */
        .gauge-ring { transition: stroke-dashoffset 1.2s cubic-bezier(0.22, 1, 0.36, 1); }

        /* Section badge */
        .section-num {
            display: inline-flex; align-items: center; justify-content: center;
            width: 28px; height: 28px; border-radius: 8px;
            font-size: 13px; font-weight: 800;
        }

        /* Strategy card */
        .strategy-card { border-left: 4px solid; transition: transform 0.2s, box-shadow 0.2s; }
        .strategy-card:hover { transform: translateX(4px); box-shadow: 0 4px 16px rgba(0,0,0,0.08); }

        /* Keyword pill */
        .kw-pill { transition: transform 0.15s; }
        .kw-pill:hover { transform: scale(1.08); }

        /* Respondent card */
        details summary::-webkit-details-marker { display: none; }
        details summary { cursor: pointer; list-style: none; }
        details[open] summary .chevron-icon { transform: rotate(180deg); }
        .chevron-icon { transition: transform 0.2s; }

        /* Priority badges */
        .badge-urgent { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
        .badge-important { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
        .badge-info { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
        .badge-positive { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }

        /* Score dot */
        .score-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

        /* Print */
        @media print {
            .no-print { display: none !important; }
            .hero-bg { background: #1c1917 !important; -webkit-print-color-adjust: exact; }
            .card { break-inside: avoid; }
            body { font-size: 11px; }
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
    </style>
</head>
<body class="text-slate-800">

    <!-- ===== HERO HEADER ===== -->
    <div class="hero-bg text-white">
        <div class="max-w-5xl mx-auto px-6 pt-16 pb-12">
            <!-- Top badge -->
            <div class="fade-up d1 text-center mb-8">
                <span class="inline-block px-4 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-[0.15em] glass text-amber-300">
                    Feedback Analysis Report
                </span>
            </div>

            <!-- Title -->
            <h1 class="fade-up d2 text-center text-3xl md:text-4xl font-black tracking-tight leading-tight mb-3">
                {{ report_title }}
            </h1>
            <p class="fade-up d2 text-center text-stone-400 text-sm mb-10">{{ report_date }}</p>

            <!-- Key Stats Cards -->
            <div class="fade-up d3 grid grid-cols-2 md:grid-cols-4 gap-3 max-w-3xl mx-auto">
                <!-- Response Count -->
                <div class="glass rounded-2xl p-4 text-center">
                    <p class="num-font text-3xl font-black text-white mb-1">{{ overview.response_count }}</p>
                    <p class="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">총 응답</p>
                </div>

                {% if overview.avg_satisfaction > 0 %}
                <!-- Avg Satisfaction -->
                <div class="glass rounded-2xl p-4 text-center">
                    <p class="num-font text-3xl font-black mb-1" style="color: {% if overview.avg_satisfaction < 3 %}#f87171{% elif overview.avg_satisfaction < 4 %}#fbbf24{% else %}#34d399{% endif %};">
                        {{ overview.avg_satisfaction }}
                    </p>
                    <p class="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">평균 만족도</p>
                </div>
                {% endif %}

                {% if overview.date_range %}
                <!-- Date Range -->
                <div class="glass rounded-2xl p-4 text-center">
                    <p class="text-sm font-bold text-amber-300 leading-snug">{{ overview.date_range }}</p>
                    <p class="text-[10px] text-stone-400 uppercase tracking-wider font-semibold mt-1">응답 기간</p>
                </div>
                {% endif %}

                <!-- Column Count -->
                <div class="glass rounded-2xl p-4 text-center">
                    <p class="num-font text-3xl font-black text-stone-300 mb-1">{{ overview.column_count }}</p>
                    <p class="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">분석 항목</p>
                </div>
            </div>
        </div>
    </div>

    <div class="max-w-5xl mx-auto px-6 py-10 space-y-10">

        <!-- ===== EXECUTIVE SUMMARY ===== -->
        {% if score_analysis or multiselect_analysis %}
        <div class="fade-up d1">
            <div class="flex items-center gap-3 mb-5">
                <div class="section-num bg-amber-100 text-amber-700">01</div>
                <h2 class="text-lg font-black text-slate-900 tracking-tight">Executive Summary</h2>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                {% if overview.best_area %}
                <div class="card p-5 border-t-4 border-emerald-400">
                    <div class="flex items-center gap-2 mb-2">
                        <i data-lucide="trending-up" class="w-4 h-4 text-emerald-500"></i>
                        <span class="text-[10px] font-bold text-emerald-600 uppercase tracking-wider">최고 만족 영역</span>
                    </div>
                    <p class="text-base font-bold text-slate-800 mb-1">{{ overview.best_area.label }}</p>
                    <p class="num-font text-2xl font-black text-emerald-500">{{ overview.best_area.score }}점</p>
                </div>
                {% endif %}

                {% if overview.worst_area %}
                <div class="card p-5 border-t-4 border-rose-400">
                    <div class="flex items-center gap-2 mb-2">
                        <i data-lucide="trending-down" class="w-4 h-4 text-rose-500"></i>
                        <span class="text-[10px] font-bold text-rose-600 uppercase tracking-wider">개선 필요 영역</span>
                    </div>
                    <p class="text-base font-bold text-slate-800 mb-1">{{ overview.worst_area.label }}</p>
                    <p class="num-font text-2xl font-black text-rose-500">{{ overview.worst_area.score }}점</p>
                </div>
                {% endif %}

                {% if overview.top_concern %}
                <div class="card p-5 border-t-4 border-amber-400">
                    <div class="flex items-center gap-2 mb-2">
                        <i data-lucide="alert-triangle" class="w-4 h-4 text-amber-500"></i>
                        <span class="text-[10px] font-bold text-amber-600 uppercase tracking-wider">최다 중단 사유</span>
                    </div>
                    <p class="text-base font-bold text-slate-800 mb-1">{{ overview.top_concern.label }}</p>
                    <p class="num-font text-2xl font-black text-amber-500">{{ overview.top_concern.pct }}%</p>
                </div>
                {% endif %}
            </div>
        </div>
        {% endif %}


        <!-- ===== MULTI-SELECT ANALYSIS ===== -->
        {% if multiselect_analysis %}
        <div class="fade-up d2">
            <div class="flex items-center gap-3 mb-5">
                <div class="section-num bg-amber-100 text-amber-700">02</div>
                <h2 class="text-lg font-black text-slate-900 tracking-tight">객관식 응답 분석</h2>
            </div>

            <div class="space-y-5">
            {% for col_name, data in multiselect_analysis.items() %}
                <div class="card">
                    <!-- Question header -->
                    <div class="px-6 pt-5 pb-3 border-b border-slate-100">
                        <div class="flex items-start gap-2">
                            <i data-lucide="bar-chart-3" class="w-4 h-4 text-amber-500 mt-0.5 shrink-0"></i>
                            <div>
                                <p class="text-sm font-bold text-slate-800 leading-snug">{{ col_name }}</p>
                                <p class="text-[11px] text-slate-400 mt-0.5">복수 응답 | {{ data.total_responses }}명 응답</p>
                            </div>
                        </div>
                    </div>
                    <!-- Options -->
                    <div class="px-6 py-4 space-y-3">
                        {% for opt in data.options %}
                        <div>
                            <div class="flex justify-between items-center mb-1.5">
                                <div class="flex items-center gap-2">
                                    {% if loop.index == 1 %}
                                    <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-amber-500 text-white text-[10px] font-black">1</span>
                                    {% else %}
                                    <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-500 text-[10px] font-bold">{{ loop.index }}</span>
                                    {% endif %}
                                    <span class="text-sm text-slate-700 {% if loop.index == 1 %}font-bold{% else %}font-medium{% endif %}">{{ opt.label }}</span>
                                </div>
                                <span class="num-font text-xs font-bold {% if loop.index == 1 %}text-amber-600{% else %}text-slate-400{% endif %}">{{ opt.count }}건 ({{ opt.pct }}%)</span>
                            </div>
                            <div class="bg-slate-100 rounded-full h-3 overflow-hidden">
                                {% set bar_colors = ['from-amber-400 to-amber-600', 'from-amber-300 to-amber-500', 'from-slate-300 to-slate-400', 'from-slate-200 to-slate-300'] %}
                                <div class="bar-fill h-full rounded-full bg-gradient-to-r {{ bar_colors[loop.index0] if loop.index0 < 4 else 'from-slate-200 to-slate-300' }}"
                                     style="width: {{ opt.pct }}%;">
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            {% endfor %}
            </div>
        </div>
        {% endif %}


        <!-- ===== SATISFACTION SCORES ===== -->
        {% if score_analysis %}
        <div class="fade-up d3">
            <div class="flex items-center gap-3 mb-5">
                <div class="section-num bg-emerald-100 text-emerald-700">03</div>
                <h2 class="text-lg font-black text-slate-900 tracking-tight">영역별 만족도</h2>
            </div>

            <div class="card">
                <!-- Overall gauge header -->
                {% if score_analysis|length > 1 %}
                {% set all_means = [] %}
                {% for _, d in score_analysis.items() %}{% if all_means.append(d.mean) %}{% endif %}{% endfor %}
                {% set overall_avg = (all_means|sum / all_means|length)|round(1) %}
                <div class="px-6 pt-6 pb-4 border-b border-slate-100 flex items-center justify-between">
                    <div>
                        <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">전체 평균</p>
                        <p class="text-sm text-slate-500 mt-0.5">{{ score_analysis|length }}개 영역 종합</p>
                    </div>
                    <div class="flex items-center gap-3">
                        <!-- Mini gauge -->
                        <svg width="56" height="56" viewBox="0 0 56 56" class="transform -rotate-90">
                            <circle cx="28" cy="28" r="22" fill="none" stroke="#f1f5f9" stroke-width="5"/>
                            <circle cx="28" cy="28" r="22" fill="none"
                                    stroke="{% if overall_avg < 3 %}#f87171{% elif overall_avg < 4 %}#fbbf24{% else %}#34d399{% endif %}"
                                    stroke-width="5" stroke-linecap="round"
                                    stroke-dasharray="{{ (overall_avg / 5 * 138.2)|round(1) }} 138.2"
                                    class="gauge-ring"/>
                        </svg>
                        <span class="num-font text-3xl font-black {% if overall_avg < 3 %}text-rose-500{% elif overall_avg < 4 %}text-amber-500{% else %}text-emerald-500{% endif %}">
                            {{ overall_avg }}
                        </span>
                    </div>
                </div>
                {% endif %}

                <!-- Individual scores -->
                <div class="px-6 py-5 space-y-5">
                    {% for col_name, data in score_analysis.items() %}
                    <div>
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-sm font-bold text-slate-700">{{ data.short_label }}</span>
                            <span class="num-font text-lg font-black {% if data.mean < 3 %}text-rose-500{% elif data.mean < 4 %}text-amber-500{% else %}text-emerald-500{% endif %}">
                                {{ data.mean }}
                                <span class="text-xs text-slate-400 font-medium">/5</span>
                            </span>
                        </div>

                        <!-- Score bar -->
                        <div class="bg-slate-100 rounded-full h-2.5 overflow-hidden mb-2.5">
                            {% set pct = (data.mean / 5 * 100)|round %}
                            <div class="h-full rounded-full bar-fill"
                                 style="width: {{ pct }}%; background: {% if data.mean < 3 %}linear-gradient(90deg, #fca5a5, #ef4444){% elif data.mean < 4 %}linear-gradient(90deg, #fde68a, #f59e0b){% else %}linear-gradient(90deg, #6ee7b7, #10b981){% endif %};">
                            </div>
                        </div>

                        <!-- Distribution mini bars -->
                        <div class="flex items-center gap-1">
                            {% for i in range(1, 6) %}
                            {% set cnt = data.distribution.get(i, 0) %}
                            {% set max_cnt = data.distribution.values()|list|max if data.distribution.values()|list else 1 %}
                            {% set bar_h = (cnt / max_cnt * 24)|round|int if max_cnt > 0 else 0 %}
                            <div class="flex-1 flex flex-col items-center gap-0.5">
                                <div class="w-full flex justify-center">
                                    <div style="height: {{ bar_h + 4 }}px; width: 100%; max-width: 32px;"
                                         class="rounded-sm {% if i <= 2 %}bg-rose-200{% elif i == 3 %}bg-amber-200{% else %}bg-emerald-200{% endif %}">
                                    </div>
                                </div>
                                <span class="text-[9px] text-slate-400 font-medium">{{ i }}점</span>
                                <span class="text-[10px] font-bold text-slate-500">{{ cnt }}</span>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    {% if not loop.last %}
                    <div class="border-t border-slate-100"></div>
                    {% endif %}
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}


        <!-- ===== SINGLE-SELECT ANALYSIS ===== -->
        {% if singleselect_analysis %}
        <div class="fade-up d4">
            <div class="flex items-center gap-3 mb-5">
                <div class="section-num bg-cyan-100 text-cyan-700">04</div>
                <h2 class="text-lg font-black text-slate-900 tracking-tight">응답 분포</h2>
            </div>

            {% for col_name, data in singleselect_analysis.items() %}
            <div class="card p-6">
                <p class="text-sm font-bold text-slate-700 mb-4">{{ col_name }}</p>
                <div class="grid grid-cols-2 md:grid-cols-{{ [data.values|length, 4]|min }} gap-3">
                    {% set ss_colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#6366f1'] %}
                    {% for val in data.values %}
                    <div class="rounded-xl p-4 text-center" style="background: {{ ss_colors[loop.index0 % 6] }}08; border: 1px solid {{ ss_colors[loop.index0 % 6] }}20;">
                        <p class="num-font text-2xl font-black" style="color: {{ ss_colors[loop.index0 % 6] }};">{{ val.count }}</p>
                        <p class="text-xs text-slate-600 font-medium mt-1">{{ val.label }}</p>
                        <p class="num-font text-[10px] text-slate-400 font-bold mt-0.5">{{ val.pct }}%</p>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}


        <!-- ===== VOICE OF CUSTOMER (Free Text) ===== -->
        {% if freetext_analysis %}
        <div class="fade-up d4">
            <div class="flex items-center gap-3 mb-5">
                <div class="section-num bg-slate-200 text-slate-600">05</div>
                <h2 class="text-lg font-black text-slate-900 tracking-tight">고객의 목소리</h2>
            </div>

            <div class="space-y-5">
            {% for col_name, data in freetext_analysis.items() %}
                <div class="card">
                    <div class="px-6 pt-5 pb-3 border-b border-slate-100">
                        <div class="flex items-start gap-2">
                            <i data-lucide="message-circle" class="w-4 h-4 text-slate-400 mt-0.5 shrink-0"></i>
                            <div>
                                <p class="text-sm font-bold text-slate-800">{{ col_name }}</p>
                                <p class="text-[11px] text-slate-400 mt-0.5">{{ data.response_count }}건 응답</p>
                            </div>
                        </div>
                    </div>

                    <div class="px-6 py-4">
                        {% if data.top_keywords %}
                        <!-- Keywords -->
                        <div class="mb-5">
                            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2.5">주요 키워드</p>
                            <div class="flex flex-wrap gap-1.5">
                                {% for kw in data.top_keywords[:10] %}
                                {% set sizes = ['text-sm', 'text-sm', 'text-sm', 'text-xs', 'text-xs', 'text-xs', 'text-[11px]', 'text-[11px]', 'text-[11px]', 'text-[11px]'] %}
                                {% set opacities = ['', '', '', 'opacity-90', 'opacity-90', 'opacity-80', 'opacity-70', 'opacity-70', 'opacity-60', 'opacity-60'] %}
                                {% set bgs = ['bg-amber-100 text-amber-800 border-amber-200', 'bg-amber-50 text-amber-700 border-amber-200', 'bg-amber-50 text-amber-700 border-amber-100', 'bg-slate-100 text-slate-600 border-slate-200', 'bg-slate-100 text-slate-600 border-slate-200', 'bg-slate-50 text-slate-500 border-slate-200', 'bg-slate-50 text-slate-500 border-slate-100', 'bg-slate-50 text-slate-500 border-slate-100', 'bg-slate-50 text-slate-400 border-slate-100', 'bg-slate-50 text-slate-400 border-slate-100'] %}
                                <span class="kw-pill inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border {{ sizes[loop.index0] if loop.index0 < 10 else 'text-[11px]' }} {{ opacities[loop.index0] if loop.index0 < 10 else 'opacity-60' }} {{ bgs[loop.index0] if loop.index0 < 10 else 'bg-slate-50 text-slate-400 border-slate-100' }} font-semibold cursor-default">
                                    {{ kw.word }}
                                    <span class="text-[9px] opacity-60">{{ kw.count }}</span>
                                </span>
                                {% endfor %}
                            </div>
                        </div>
                        {% endif %}

                        <!-- Sample responses as quote cards -->
                        <div class="space-y-2.5">
                            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">대표 응답</p>
                            {% for sample in data.samples[:5] %}
                            <div class="relative pl-4 py-2.5 pr-3 bg-slate-50 rounded-lg border-l-[3px] {% if loop.index <= 2 %}border-amber-400{% else %}border-slate-200{% endif %}">
                                <p class="text-xs text-slate-600 leading-relaxed">{{ sample }}</p>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            {% endfor %}
            </div>
        </div>
        {% endif %}


        <!-- ===== RECOMMENDATIONS & ACTION PLAN ===== -->
        {% if recommendations %}
        <div class="fade-up d5">
            <div class="flex items-center gap-3 mb-5">
                <div class="section-num bg-amber-500 text-white">!</div>
                <h2 class="text-lg font-black text-slate-900 tracking-tight">개선 제안 & 워크플랜</h2>
            </div>

            <div class="card overflow-visible" style="background: linear-gradient(160deg, #1c1917 0%, #292524 100%);">
                <div class="px-6 pt-6 pb-2">
                    <div class="flex items-center gap-3 mb-1">
                        <div class="p-2 bg-amber-400/10 rounded-xl border border-amber-400/20">
                            <i data-lucide="lightbulb" class="w-5 h-5 text-amber-400"></i>
                        </div>
                        <div>
                            <p class="text-white font-bold">데이터 기반 액션 플랜</p>
                            <p class="text-[10px] text-stone-500 uppercase tracking-wider">Data-Driven Action Plan</p>
                        </div>
                    </div>
                </div>

                <div class="px-6 pb-6 space-y-3">
                    {% for rec in recommendations %}
                    {% set priority_color = '#ef4444' if '긴급' in rec else '#f59e0b' if '핵심' in rec else '#3b82f6' if '재계약' in rec else '#10b981' if '강점' in rec else '#8b5cf6' %}
                    {% set priority_bg = 'bg-rose-500/10 text-rose-400' if '긴급' in rec else 'bg-amber-500/10 text-amber-400' if '핵심' in rec else 'bg-blue-500/10 text-blue-400' if '재계약' in rec else 'bg-emerald-500/10 text-emerald-400' if '강점' in rec else 'bg-purple-500/10 text-purple-400' %}
                    {% set tag_text = rec.split(']')[0].replace('[', '') if ']' in rec else '' %}
                    {% set rec_body = rec.split('] ', 1)[1] if '] ' in rec else rec %}

                    <div class="strategy-card rounded-xl p-4 bg-white/[0.04]" style="border-left-color: {{ priority_color }};">
                        <div class="flex items-start gap-3">
                            <span class="shrink-0 inline-block px-2 py-0.5 rounded-md text-[10px] font-black uppercase {{ priority_bg }}">
                                {{ tag_text if tag_text else 'INFO' }}
                            </span>
                            <p class="text-sm text-stone-300 leading-relaxed">{{ rec_body }}</p>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}


        <!-- ===== RESPONDENT DETAILS ===== -->
        {% if respondent_details %}
        <div class="fade-up d6">
            <div class="flex items-center gap-3 mb-5">
                <div class="section-num bg-purple-100 text-purple-700">
                    <i data-lucide="users" class="w-3.5 h-3.5"></i>
                </div>
                <div>
                    <h2 class="text-lg font-black text-slate-900 tracking-tight">응답자별 상세</h2>
                    <p class="text-xs text-slate-400">{{ respondent_details|length }}건의 개별 응답</p>
                </div>
            </div>

            <div class="space-y-3">
                {% for row in respondent_details %}
                <details class="card group">
                    <summary class="px-5 py-4 flex items-center justify-between hover:bg-slate-50/50 transition-colors">
                        <div class="flex items-center gap-3">
                            <!-- Avatar -->
                            <div class="w-9 h-9 rounded-full bg-gradient-to-br from-purple-100 to-purple-200 flex items-center justify-center text-purple-600 font-black text-sm shrink-0">
                                {{ loop.index }}
                            </div>
                            <div>
                                <p class="text-sm font-bold text-slate-700">
                                    {% if identifier_col and row.get(identifier_col) and row[identifier_col]|string|lower not in ['nan', 'nat', 'none', ''] %}
                                        {{ row[identifier_col] }}
                                    {% else %}
                                        응답자 {{ loop.index }}
                                    {% endif %}
                                </p>
                                <!-- Score summary dots -->
                                {% if score_analysis %}
                                <div class="flex items-center gap-1.5 mt-1">
                                    {% for score_col, score_data in score_analysis.items() %}
                                    {% set val = row.get(score_col, '') %}
                                    {% set score_val = val|string|replace('점','')|trim %}
                                    {% if score_val and score_val not in ['nan', 'NaT', 'None'] %}
                                    <div class="flex items-center gap-0.5" title="{{ score_data.short_label }}: {{ score_val }}점">
                                        <div class="score-dot" style="background: {% if score_val|float < 3 %}#f87171{% elif score_val|float < 4 %}#fbbf24{% else %}#34d399{% endif %};"></div>
                                        <span class="text-[9px] text-slate-400">{{ score_val }}</span>
                                    </div>
                                    {% endif %}
                                    {% endfor %}
                                </div>
                                {% endif %}
                            </div>
                        </div>
                        <i data-lucide="chevron-down" class="w-4 h-4 text-slate-300 chevron-icon"></i>
                    </summary>

                    <div class="px-5 pb-5 border-t border-slate-100">
                        <div class="pt-4 space-y-3">
                            {% for col in columns %}
                            {% set val = row.get(col.name, '') %}
                            {% if val is not none and val|string|trim and val|string|lower not in ['nan', 'nat', 'none'] %}
                            <div class="flex gap-3">
                                <!-- Type indicator -->
                                {% set type_colors = {
                                    'timestamp': 'bg-blue-100 text-blue-600',
                                    'identifier': 'bg-purple-100 text-purple-600',
                                    'score': 'bg-emerald-100 text-emerald-600',
                                    'multi_select': 'bg-amber-100 text-amber-600',
                                    'single_select': 'bg-cyan-100 text-cyan-600',
                                    'free_text': 'bg-slate-100 text-slate-500'
                                } %}
                                <div class="shrink-0 w-32">
                                    <span class="text-[10px] font-bold text-slate-500 leading-tight block">{{ col.short_name }}</span>
                                </div>
                                <div class="flex-1 min-w-0">
                                    {% if col.col_type == 'score' %}
                                    {% set sv = val|string|replace('점','')|trim %}
                                    <div class="flex items-center gap-2">
                                        <div class="flex gap-0.5">
                                            {% for star in range(1, 6) %}
                                            {% if star <= sv|float|round %}
                                            <i data-lucide="star" class="w-3.5 h-3.5 fill-amber-400 text-amber-400"></i>
                                            {% else %}
                                            <i data-lucide="star" class="w-3.5 h-3.5 text-slate-200"></i>
                                            {% endif %}
                                            {% endfor %}
                                        </div>
                                        <span class="num-font text-xs font-bold text-slate-500">{{ sv }}점</span>
                                    </div>
                                    {% else %}
                                    <p class="text-xs text-slate-600 leading-relaxed">{{ val }}</p>
                                    {% endif %}
                                </div>
                            </div>
                            {% endif %}
                            {% endfor %}
                        </div>
                    </div>
                </details>
                {% endfor %}
            </div>
        </div>
        {% endif %}


        <!-- ===== DATA STRUCTURE (collapsed) ===== -->
        <details class="fade-up d6 card">
            <summary class="px-6 py-4 flex items-center justify-between hover:bg-slate-50/50 transition-colors cursor-pointer">
                <div class="flex items-center gap-2">
                    <i data-lucide="scan-search" class="w-4 h-4 text-slate-400"></i>
                    <span class="text-sm font-bold text-slate-500">데이터 구조 감지 결과 ({{ columns|length }}개 컬럼)</span>
                </div>
                <i data-lucide="chevron-down" class="w-4 h-4 text-slate-300 chevron-icon"></i>
            </summary>
            <div class="px-6 pb-5 border-t border-slate-100 pt-4">
                <div class="flex flex-wrap gap-2">
                    {% for col in columns %}
                    {% set type_colors = {
                        'timestamp': 'bg-blue-50 text-blue-700 border-blue-200',
                        'identifier': 'bg-purple-50 text-purple-700 border-purple-200',
                        'score': 'bg-emerald-50 text-emerald-700 border-emerald-200',
                        'multi_select': 'bg-amber-50 text-amber-700 border-amber-200',
                        'single_select': 'bg-cyan-50 text-cyan-700 border-cyan-200',
                        'free_text': 'bg-slate-50 text-slate-600 border-slate-200'
                    } %}
                    {% set type_labels = {
                        'timestamp': '날짜',
                        'identifier': '식별자',
                        'score': '점수',
                        'multi_select': '복수선택',
                        'single_select': '단일선택',
                        'free_text': '주관식'
                    } %}
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-medium {{ type_colors.get(col.col_type, 'bg-slate-50 text-slate-600 border-slate-200') }}">
                        <span class="font-bold">{{ type_labels.get(col.col_type, col.col_type) }}</span>
                        <span class="opacity-60">{{ col.short_name }}</span>
                    </span>
                    {% endfor %}
                </div>
            </div>
        </details>

    </div>

    <!-- ===== FOOTER ===== -->
    <div class="max-w-5xl mx-auto px-6 pb-12 pt-4">
        <div class="border-t border-slate-200 pt-6 flex items-center justify-between">
            <div>
                <p class="text-xs text-slate-400">Generated by <span class="font-bold text-slate-500">Group-D</span> 전략보고서 시스템</p>
                <p class="text-[10px] text-slate-300 mt-0.5">{{ report_date }}</p>
            </div>
            <div class="text-right">
                <p class="text-[10px] text-slate-300 uppercase tracking-wider font-semibold">Confidential</p>
            </div>
        </div>
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

    # Pre-compute executive summary data
    score_data = analysis.get('score_analysis', {})
    if score_data:
        best = max(score_data.values(), key=lambda x: x['mean'])
        worst = min(score_data.values(), key=lambda x: x['mean'])
        overview['best_area'] = {'label': best['short_label'], 'score': best['mean']}
        overview['worst_area'] = {'label': worst['short_label'], 'score': worst['mean']}

    # Find top concern from first complaint-related multiselect
    ms_data = analysis.get('multiselect_analysis', {})
    complaint_kw = ['이유', '원인', '사유', '미흡', '아쉬', '불만', '중단', '문제']
    overview['top_concern'] = None
    for col_name, data in ms_data.items():
        if any(kw in col_name for kw in complaint_kw) and data.get('options'):
            overview['top_concern'] = data['options'][0]
            break
    if not overview['top_concern'] and ms_data:
        first_ms = list(ms_data.values())[0]
        if first_ms.get('options'):
            overview['top_concern'] = first_ms['options'][0]

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
