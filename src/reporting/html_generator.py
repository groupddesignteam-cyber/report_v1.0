"""
HTML Report Generator using Jinja2 & Tailwind CSS
Enhanced design matching the Streamlit dashboard style
"""

from datetime import datetime
from typing import Dict, Any, List
from jinja2 import Template
from src.processors.summary import generate_summary

HTML_TEMPLATE = """
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
        .gradient-bg { background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%); }
        .card { background: white; border-radius: 1rem; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08), 0 4px 10px -2px rgba(0,0,0,0.04); overflow: hidden; transition: box-shadow 0.3s ease; }
        .card:hover { box-shadow: 0 20px 40px -8px rgba(0,0,0,0.12), 0 8px 16px -4px rgba(0,0,0,0.06); }
        .fade-in { animation: fadeIn 0.7s cubic-bezier(0.4, 0, 0.2, 1) forwards; opacity: 0; transform: translateY(12px); }
        @keyframes fadeIn { to { opacity: 1; transform: translateY(0); } }
        .delay-1 { animation-delay: 0.15s; }
        .delay-2 { animation-delay: 0.3s; }
        .delay-3 { animation-delay: 0.45s; }
        .delay-4 { animation-delay: 0.6s; }
        .strategy-card { border-left: 4px solid; transition: transform 0.2s, box-shadow 0.2s; }
        .strategy-card:hover { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(0,0,0,0.3); }
        .section-badge { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.625rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 0.25rem 0.625rem; border-radius: 9999px; }
        .metric-highlight { position: relative; }
        .metric-highlight::after { content: ''; position: absolute; bottom: -2px; left: 0; right: 0; height: 3px; border-radius: 2px; background: currentColor; opacity: 0.2; }
        .glass-card { background: rgba(255,255,255,0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.3); }
        @keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulse-dot { animation: pulse-dot 2s ease-in-out infinite; }
        details summary::-webkit-details-marker { display: none; }
        details[open] > summary .toggle-arrow { transform: rotate(90deg); }
        @media print {
            .fade-in { opacity: 1 !important; transform: none !important; animation: none !important; }
            .card { box-shadow: none !important; border: 1px solid #e2e8f0; }
            .card:hover { box-shadow: none !important; }
            body { background: white !important; }
        }
    </style>
</head>
<body class="p-4 md:p-8 text-slate-800 bg-slate-100">

    <div class="max-w-5xl mx-auto space-y-6">

        <!-- 1. Header -->
        <header class="gradient-bg text-white p-8 md:p-12 rounded-3xl shadow-2xl relative overflow-hidden fade-in">
            <div class="absolute top-0 right-0 w-80 h-80 bg-indigo-500/15 rounded-full blur-3xl -mr-20 -mt-20"></div>
            <div class="absolute bottom-0 left-0 w-48 h-48 bg-blue-400/10 rounded-full blur-2xl -ml-12 -mb-12"></div>
            <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-to-tr from-indigo-600/5 to-cyan-400/5 rounded-full blur-3xl"></div>
            <div class="relative z-10">
                <div class="inline-flex items-center gap-2 bg-white/10 px-4 py-1.5 rounded-full text-xs font-bold mb-4 border border-white/10 backdrop-blur-sm">
                    <span class="w-2 h-2 bg-green-400 rounded-full pulse-dot"></span>
                    MARKETING REPORT
                </div>
                <h1 class="text-3xl md:text-4xl font-black tracking-tight mb-2 bg-clip-text">{{ report_title }}</h1>
                <p class="text-slate-300 font-light text-sm md:text-base">{{ clinic_name }} | {{ report_date }}</p>
            </div>
        </header>

        <!-- 2. Department Sections -->
        {% for dept in departments %}
        {% if dept.has_data %}
        <div class="card p-6 md:p-8 fade-in delay-2">
            <!-- Section Header -->
            <div class="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
                <div class="flex items-center gap-3">
                    <div class="p-2.5 rounded-xl shadow-sm" style="background: {{ dept.color_bg }};">
                        <span class="text-lg">{{ dept.icon }}</span>
                    </div>
                    <div>
                        <h2 class="text-lg font-bold text-slate-800">{{ dept.name }}</h2>
                        <p class="text-[10px] text-slate-400 font-medium uppercase tracking-wider">{% if dept.id == 'setting' %}Channel Setting Analysis{% else %}Performance Analysis{% endif %}</p>
                    </div>
                </div>
                {% if dept.prev_month and dept.curr_month %}
                <span class="section-badge bg-slate-100 text-slate-500 border border-slate-200">{{ dept.prev_month }} → {{ dept.curr_month }}</span>
                {% endif %}
            </div>

            <!-- CPA Banner hidden -->

            <!-- Ads: Impressions & Clicks Metrics -->
            {% if dept.id == 'ads' and dept.prev_metrics and dept.curr_metrics %}
            <div class="grid md:grid-cols-2 gap-4 mb-6">
                <div class="bg-slate-50 p-5 rounded-xl border border-slate-200">
                    <h4 class="text-sm font-bold text-slate-500 mb-3 pb-2 border-b border-slate-200">{{ dept.prev_month }}</h4>
                    <div class="grid grid-cols-2 gap-3">
                        {% for metric in dept.prev_metrics %}
                        <div class="bg-white p-3 rounded-lg border border-slate-100">
                            <div class="flex items-center gap-1.5 mb-1">
                                <span class="text-sm">{{ metric.icon }}</span>
                                <span class="text-[10px] text-slate-500 font-bold uppercase">{{ metric.label }}</span>
                            </div>
                            <p class="text-lg font-bold text-slate-800">{{ metric.value }}<span class="text-xs text-slate-400 ml-0.5">{{ metric.unit|default('') }}</span></p>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                <div class="bg-blue-50/50 p-5 rounded-xl border-2 border-blue-200">
                    <h4 class="text-sm font-bold text-blue-600 mb-3 pb-2 border-b border-blue-200">{{ dept.curr_month }} <span class="text-[10px] text-blue-400">(당월)</span></h4>
                    <div class="grid grid-cols-2 gap-3">
                        {% for metric in dept.curr_metrics %}
                        <div class="bg-white p-3 rounded-lg border border-blue-100 shadow-sm">
                            <div class="flex items-center gap-1.5 mb-1">
                                <span class="text-sm">{{ metric.icon }}</span>
                                <span class="text-[10px] font-bold uppercase" style="color: {{ metric.label_color|default('#64748b') }};">{{ metric.label }}</span>
                            </div>
                            <p class="text-lg font-bold text-slate-800">{{ metric.value }}<span class="text-xs text-slate-400 ml-0.5">{{ metric.unit|default('') }}</span></p>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
            {% endif %}

            <!-- Month Comparison Metrics -->
            {% if dept.prev_month and dept.curr_month and dept.id not in ['ads', 'design'] %}
            <div class="grid md:grid-cols-2 gap-4 mb-6">
                <!-- Previous Month -->
                <div class="bg-slate-50 p-5 rounded-xl border border-slate-200">
                    <h4 class="text-sm font-bold text-slate-500 mb-3 pb-2 border-b border-slate-200">{{ dept.prev_month }}</h4>
                    <div class="grid grid-cols-{% if dept.id == 'blog' %}2{% else %}3{% endif %} gap-3">
                        {% for metric in dept.prev_metrics %}
                        <div class="bg-white p-3 rounded-lg border border-slate-100">
                            <div class="flex items-center gap-1.5 mb-1">
                                <span class="text-sm">{{ metric.icon }}</span>
                                <span class="text-[10px] text-slate-500 font-bold uppercase">{{ metric.label }}</span>
                            </div>
                            <p class="text-lg font-bold text-slate-800">{{ metric.value }}<span class="text-xs text-slate-400 ml-0.5">{{ metric.unit|default('') }}</span></p>
                            {% if metric.note %}
                            <p class="text-[10px] text-amber-600 mt-1">{{ metric.note }}</p>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                    {% if dept.id == 'blog' and dept.prev_metrics_row2 %}
                    <div class="grid grid-cols-2 gap-3 mt-3">
                        {% for metric in dept.prev_metrics_row2 %}
                        <div class="bg-white p-3 rounded-lg border border-slate-100">
                            <div class="flex items-center gap-1.5 mb-1">
                                <span class="text-sm">{{ metric.icon }}</span>
                                <span class="text-[10px] text-slate-500 font-bold uppercase">{{ metric.label }}</span>
                            </div>
                            <p class="text-lg font-bold text-slate-800">{{ metric.value }}<span class="text-xs text-slate-400 ml-0.5">{{ metric.unit|default('') }}</span></p>
                            {% if metric.note %}
                            <p class="text-[10px] text-amber-600 mt-1">{{ metric.note }}</p>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>

                <!-- Current Month (highlighted) -->
                <div class="bg-blue-50/50 p-5 rounded-xl border-2 border-blue-200">
                    <h4 class="text-sm font-bold text-blue-600 mb-3 pb-2 border-b border-blue-200">{{ dept.curr_month }} <span class="text-[10px] text-blue-400">(당월)</span></h4>
                    <div class="grid grid-cols-{% if dept.id == 'blog' %}2{% else %}3{% endif %} gap-3">
                        {% for metric in dept.curr_metrics %}
                        <div class="bg-white p-3 rounded-lg border border-blue-100 shadow-sm">
                            <div class="flex items-center gap-1.5 mb-1">
                                <span class="text-sm">{{ metric.icon }}</span>
                                <span class="text-[10px] font-bold uppercase" style="color: {{ metric.label_color|default('#64748b') }};">{{ metric.label }}</span>
                            </div>
                            <p class="text-lg font-bold text-slate-800">{{ metric.value }}<span class="text-xs text-slate-400 ml-0.5">{{ metric.unit|default('') }}</span></p>
                            {% if metric.note %}
                            <p class="text-[10px] text-amber-600 mt-1">{{ metric.note }}</p>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                    {% if dept.id == 'blog' and dept.curr_metrics_row2 %}
                    <div class="grid grid-cols-2 gap-3 mt-3">
                        {% for metric in dept.curr_metrics_row2 %}
                        <div class="bg-white p-3 rounded-lg border border-blue-100 shadow-sm">
                            <div class="flex items-center gap-1.5 mb-1">
                                <span class="text-sm">{{ metric.icon }}</span>
                                <span class="text-[10px] font-bold uppercase" style="color: {{ metric.label_color|default('#64748b') }};">{{ metric.label }}</span>
                            </div>
                            <p class="text-lg font-bold text-slate-800">{{ metric.value }}<span class="text-xs text-slate-400 ml-0.5">{{ metric.unit|default('') }}</span></p>
                            {% if metric.note %}
                            <p class="text-[10px] text-amber-600 mt-1">{{ metric.note }}</p>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>
            </div>
            {% endif %}

            <!-- TOP5 Sections -->
            {% if dept.top5_sections %}
            {% for section in dept.top5_sections %}
            {% if not loop.first %}
            <div class="border-t border-slate-100 my-5"></div>
            {% endif %}
            <div class="mb-6">
                <div class="flex items-center gap-2 mb-3">
                    <div class="flex items-center justify-center w-7 h-7 rounded-lg" style="background: {% if section.bar_color == 'red' %}#fef2f2{% elif section.bar_color == 'green' %}#f0fdf4{% elif section.bar_color == 'purple' %}#faf5ff{% elif section.bar_color == 'amber' %}#fffbeb{% else %}#eff6ff{% endif %};">
                        <span class="text-sm">{{ section.icon }}</span>
                    </div>
                    <h3 class="text-sm font-bold text-slate-700">{{ section.title }}</h3>
                </div>
                <div class="grid md:grid-cols-2 gap-4">
                    <!-- Previous Month TOP5 -->
                    <div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <p class="text-xs font-bold text-slate-400 uppercase mb-3">{{ dept.prev_month }}</p>
                        {% if section.prev_items %}
                        {% for item in section.prev_items %}
                        <div class="flex items-center gap-2 py-1.5 {% if not loop.last %}border-b border-slate-100{% endif %}">
                            {% if item.icon %}
                            <span class="text-xs">{{ item.icon }}</span>
                            {% else %}
                            <span class="text-[10px] font-bold text-slate-400 w-4">{{ loop.index }}</span>
                            {% endif %}
                            <span class="text-xs text-slate-700 flex-1 truncate">{{ item.label }}</span>
                            <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                <div class="h-full rounded-full" style="width: {{ item.pct }}%; background: {% if section.bar_color == 'red' %}#f87171{% elif section.bar_color == 'green' %}#6ee7b7{% elif section.bar_color == 'purple' %}#c4b5fd{% elif section.bar_color == 'amber' %}#fcd34d{% elif section.bar_color == 'blue' %}#93c5fd{% else %}#94a3b8{% endif %};"></div>
                            </div>
                            <span class="text-[10px] font-bold text-slate-600 w-14 text-right">{{ item.value_display }}</span>
                        </div>
                        {% endfor %}
                        {% else %}
                        <p class="text-xs text-slate-400 italic py-2">{{ section.no_prev_data_msg|default('데이터 없음') }}</p>
                        {% endif %}
                    </div>
                    <!-- Current Month TOP5 -->
                    <div class="p-4 rounded-xl border" style="background: {% if section.bar_color == 'red' %}#fef2f2{% elif section.bar_color == 'green' %}#f0fdf4{% elif section.bar_color == 'purple' %}#faf5ff{% elif section.bar_color == 'amber' %}#fffbeb{% else %}#eff6ff80{% endif %}; border-color: {% if section.bar_color == 'red' %}#fecaca{% elif section.bar_color == 'green' %}#bbf7d0{% elif section.bar_color == 'purple' %}#e9d5ff{% elif section.bar_color == 'amber' %}#fde68a{% else %}#bfdbfe{% endif %};">
                        <p class="text-xs font-bold uppercase mb-3" style="color: {% if section.bar_color == 'red' %}#ef4444{% elif section.bar_color == 'green' %}#22c55e{% elif section.bar_color == 'purple' %}#8b5cf6{% elif section.bar_color == 'amber' %}#d97706{% else %}#3b82f6{% endif %};">{{ dept.curr_month }}</p>
                        {% if section.curr_items %}
                        {% for item in section.curr_items %}
                        <div class="flex items-center gap-2 py-1.5 {% if not loop.last %}border-b{% endif %}" style="{% if not loop.last %}border-color: {% if section.bar_color == 'red' %}#fee2e2{% elif section.bar_color == 'green' %}#dcfce7{% elif section.bar_color == 'purple' %}#f3e8ff{% elif section.bar_color == 'amber' %}#fef3c7{% else %}#dbeafe{% endif %};{% endif %}">
                            {% if item.icon %}
                            <span class="text-xs">{{ item.icon }}</span>
                            {% else %}
                            <span class="text-[10px] font-bold w-4" style="color: {% if section.bar_color == 'red' %}#f87171{% elif section.bar_color == 'green' %}#4ade80{% elif section.bar_color == 'purple' %}#a78bfa{% elif section.bar_color == 'amber' %}#fbbf24{% else %}#60a5fa{% endif %};">{{ loop.index }}</span>
                            {% endif %}
                            <span class="text-xs text-slate-700 flex-1 truncate">{{ item.label }}</span>
                            <div class="w-16 h-1.5 rounded-full overflow-hidden" style="background: {% if section.bar_color == 'red' %}#fee2e2{% elif section.bar_color == 'green' %}#dcfce7{% elif section.bar_color == 'purple' %}#f3e8ff{% elif section.bar_color == 'amber' %}#fef3c7{% else %}#dbeafe{% endif %};">
                                <div class="h-full rounded-full" style="width: {{ item.pct }}%; background: {% if section.bar_color == 'red' %}#ef4444{% elif section.bar_color == 'green' %}#22c55e{% elif section.bar_color == 'purple' %}#8b5cf6{% elif section.bar_color == 'amber' %}#f59e0b{% else %}#3b82f6{% endif %};"></div>
                            </div>
                            <span class="text-[10px] font-bold w-14 text-right" style="color: {% if section.bar_color == 'red' %}#b91c1c{% elif section.bar_color == 'green' %}#15803d{% elif section.bar_color == 'purple' %}#6d28d9{% elif section.bar_color == 'amber' %}#92400e{% else %}#1d4ed8{% endif %};">{{ item.value_display }}</span>
                        </div>
                        {% endfor %}
                        {% else %}
                        <p class="text-xs text-slate-400 italic py-2">데이터 없음</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endfor %}
            {% endif %}

            <!-- Blog: Key Insights -->
            {% if dept.id == 'blog' and dept.key_insights %}
            <div class="bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 rounded-xl p-5 mb-6 relative">
                <span class="absolute -top-2 left-4 bg-amber-100 text-amber-700 text-[10px] font-bold px-2 py-0.5 rounded-full border border-amber-200">KEY INSIGHT</span>
                <div class="grid md:grid-cols-2 gap-4 mt-2">
                    {% if dept.key_insights.top_post %}
                    <div class="bg-white p-3 rounded-lg border border-amber-100">
                        <p class="text-[10px] font-bold text-amber-700 uppercase mb-1">Best Post</p>
                        <p class="text-xs font-bold text-slate-800 truncate">{{ dept.key_insights.top_post.title }}</p>
                        <p class="text-sm font-black text-amber-600 mt-1">{{ dept.key_insights.top_post.views }}회</p>
                    </div>
                    {% endif %}
                    {% if dept.key_insights.top_keyword %}
                    <div class="bg-white p-3 rounded-lg border border-amber-100">
                        <p class="text-[10px] font-bold text-amber-700 uppercase mb-1">Top Keyword</p>
                        <p class="text-xs font-bold text-slate-800">{{ dept.key_insights.top_keyword.keyword }}</p>
                        <p class="text-sm font-black text-amber-600 mt-1">{{ dept.key_insights.top_keyword.ratio }}%</p>
                    </div>
                    {% endif %}
                </div>
            </div>
            {% endif %}

            <!-- Blog: Posting List -->
            {% if dept.id == 'blog' and (dept.posting_list or dept.prev_posting_list) %}
            <div class="mb-6">
                <h3 class="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                    <i data-lucide="list" class="w-4 h-4 text-slate-400"></i> 발행 포스팅 목록
                </h3>
                <div class="grid md:grid-cols-2 gap-4">
                    <!-- Prev Month Posts -->
                    <div class="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden">
                        <div class="bg-slate-100 px-4 py-2">
                            <p class="text-[10px] font-bold text-slate-500 uppercase">{{ dept.prev_month }}</p>
                        </div>
                        {% if dept.prev_posting_list %}
                        <div class="divide-y divide-slate-100">
                            {% for post in dept.prev_posting_list %}
                            <div class="px-4 py-2 flex items-center justify-between gap-2">
                                <span class="text-xs text-slate-700 truncate flex-1">
                                    {% if post.url %}<a href="{{ post.url }}" target="_blank" class="hover:text-blue-600 hover:underline">{{ post.title }}</a>{% else %}{{ post.title }}{% endif %}
                                </span>
                                <span class="text-[10px] text-slate-400 shrink-0">{{ post.date }}</span>
                            </div>
                            {% endfor %}
                        </div>
                        {% else %}
                        <p class="px-4 py-3 text-xs text-slate-400 italic">데이터 없음</p>
                        {% endif %}
                    </div>
                    <!-- Current Month Posts -->
                    <div class="bg-blue-50/30 rounded-xl border border-blue-100 overflow-hidden">
                        <div class="bg-blue-50 px-4 py-2">
                            <p class="text-[10px] font-bold text-blue-500 uppercase">{{ dept.curr_month }}</p>
                        </div>
                        {% if dept.posting_list %}
                        <div class="divide-y divide-blue-50">
                            {% for post in dept.posting_list %}
                            <div class="px-4 py-2 flex items-center justify-between gap-2">
                                <span class="text-xs text-slate-700 truncate flex-1">
                                    {% if post.url %}<a href="{{ post.url }}" target="_blank" class="hover:text-blue-600 hover:underline">{{ post.title }}</a>{% else %}{{ post.title }}{% endif %}
                                </span>
                                <span class="text-[10px] text-slate-400 shrink-0">{{ post.date }}</span>
                            </div>
                            {% endfor %}
                        </div>
                        {% else %}
                        <p class="px-4 py-3 text-xs text-slate-400 italic">데이터 없음</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endif %}

            <!-- Ads: Keyword Ranking Grid -->
            {% if dept.id == 'ads' and dept.ads_ranking_data %}
            <div class="grid md:grid-cols-2 gap-4 mb-6">
                <!-- Prev Impressions -->
                <div class="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden">
                    <div class="bg-slate-100 px-4 py-2 flex justify-between items-center">
                        <p class="text-[10px] font-bold text-slate-500 uppercase">{{ dept.prev_month }} 노출수 TOP5</p>
                    </div>
                    {% if dept.ads_ranking_data.prev_impressions %}
                    <div class="p-3 space-y-2">
                        {% for item in dept.ads_ranking_data.prev_impressions %}
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] font-bold text-slate-400 w-4">{{ loop.index }}</span>
                            <span class="text-xs text-slate-700 flex-1 truncate">{{ item.keyword }}</span>
                            <div class="w-12 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                <div class="h-full bg-indigo-400 rounded-full" style="width: {{ item.pct }}%;"></div>
                            </div>
                            <span class="text-[10px] font-bold text-slate-500 w-14 text-right">{{ item.impressions }}</span>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <p class="p-4 text-xs text-slate-400 italic">데이터 없음</p>
                    {% endif %}
                </div>
                <!-- Prev Clicks -->
                <div class="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden">
                    <div class="bg-slate-100 px-4 py-2">
                        <p class="text-[10px] font-bold text-slate-500 uppercase">{{ dept.prev_month }} 클릭수 TOP5</p>
                    </div>
                    {% if dept.ads_ranking_data.prev_clicks %}
                    <div class="p-3 space-y-2">
                        {% for item in dept.ads_ranking_data.prev_clicks %}
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] font-bold text-slate-400 w-4">{{ loop.index }}</span>
                            <span class="text-xs text-slate-700 flex-1 truncate">{{ item.keyword }}</span>
                            <div class="w-12 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                <div class="h-full bg-green-400 rounded-full" style="width: {{ item.pct }}%;"></div>
                            </div>
                            <span class="text-[10px] font-bold text-slate-500 w-14 text-right">{{ item.clicks }}</span>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <p class="p-4 text-xs text-slate-400 italic">데이터 없음</p>
                    {% endif %}
                </div>
                <!-- Curr Impressions -->
                <div class="bg-blue-50/30 rounded-xl border border-blue-100 overflow-hidden">
                    <div class="bg-blue-50 px-4 py-2">
                        <p class="text-[10px] font-bold text-blue-500 uppercase">{{ dept.curr_month }} 노출수 TOP5</p>
                    </div>
                    {% if dept.ads_ranking_data.curr_impressions %}
                    <div class="p-3 space-y-2">
                        {% for item in dept.ads_ranking_data.curr_impressions %}
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] font-bold text-blue-400 w-4">{{ loop.index }}</span>
                            <span class="text-xs text-slate-700 flex-1 truncate">{{ item.keyword }}</span>
                            <div class="w-12 h-1.5 bg-blue-100 rounded-full overflow-hidden">
                                <div class="h-full bg-indigo-500 rounded-full" style="width: {{ item.pct }}%;"></div>
                            </div>
                            <span class="text-[10px] font-bold text-indigo-700 w-14 text-right">{{ item.impressions }}</span>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <p class="p-4 text-xs text-slate-400 italic">데이터 없음</p>
                    {% endif %}
                </div>
                <!-- Curr Clicks -->
                <div class="bg-blue-50/30 rounded-xl border border-blue-100 overflow-hidden">
                    <div class="bg-blue-50 px-4 py-2">
                        <p class="text-[10px] font-bold text-blue-500 uppercase">{{ dept.curr_month }} 클릭수 TOP5</p>
                    </div>
                    {% if dept.ads_ranking_data.curr_clicks %}
                    <div class="p-3 space-y-2">
                        {% for item in dept.ads_ranking_data.curr_clicks %}
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] font-bold text-blue-400 w-4">{{ loop.index }}</span>
                            <span class="text-xs text-slate-700 flex-1 truncate">{{ item.keyword }}</span>
                            <div class="w-12 h-1.5 bg-blue-100 rounded-full overflow-hidden">
                                <div class="h-full bg-green-500 rounded-full" style="width: {{ item.pct }}%;"></div>
                            </div>
                            <span class="text-[10px] font-bold text-green-700 w-14 text-right">{{ item.clicks }}</span>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <p class="p-4 text-xs text-slate-400 italic">데이터 없음</p>
                    {% endif %}
                </div>
            </div>
            {% endif %}

            <!-- YouTube: Production Metrics -->
            {% if dept.id == 'youtube' %}
            {% if dept.prev_production_metrics or dept.curr_production_metrics %}
            <div class="mb-6">
                <h3 class="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                    <i data-lucide="clapperboard" class="w-4 h-4 text-slate-400"></i> 제작 현황
                </h3>
                <div class="grid md:grid-cols-2 gap-4">
                    <div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <p class="text-xs font-bold text-slate-400 uppercase mb-3">{{ dept.prev_month }}</p>
                        <div class="grid grid-cols-2 gap-3">
                            {% for metric in dept.prev_production_metrics %}
                            <div class="bg-white p-3 rounded-lg border border-slate-100">
                                <div class="flex items-center gap-1.5 mb-1">
                                    <span class="text-sm">{{ metric.icon }}</span>
                                    <span class="text-[10px] text-slate-500 font-bold uppercase">{{ metric.label }}</span>
                                </div>
                                <p class="text-lg font-bold text-slate-800">{{ metric.value }}<span class="text-xs text-slate-400 ml-0.5">{{ metric.unit|default('') }}</span></p>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    <div class="bg-blue-50/30 p-4 rounded-xl border border-blue-100">
                        <p class="text-xs font-bold text-blue-500 uppercase mb-3">{{ dept.curr_month }}</p>
                        <div class="grid grid-cols-2 gap-3">
                            {% for metric in dept.curr_production_metrics %}
                            <div class="bg-white p-3 rounded-lg border border-blue-100 shadow-sm">
                                <div class="flex items-center gap-1.5 mb-1">
                                    <span class="text-sm">{{ metric.icon }}</span>
                                    <span class="text-[10px] font-bold uppercase" style="color: {{ metric.label_color|default('#64748b') }};">{{ metric.label }}</span>
                                </div>
                                <p class="text-lg font-bold text-slate-800">{{ metric.value }}<span class="text-xs text-slate-400 ml-0.5">{{ metric.unit|default('') }}</span></p>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>
            {% endif %}

            <!-- YouTube: Video Type Distribution -->
            {% if dept.video_type_distribution %}
            <div class="mb-6">
                <h3 class="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                    <i data-lucide="pie-chart" class="w-4 h-4 text-slate-400"></i> 영상 종류별 제작 분포
                </h3>
                <div class="grid md:grid-cols-2 gap-4">
                    <!-- Prev -->
                    <div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <p class="text-xs font-bold text-slate-400 uppercase mb-3">{{ dept.prev_month }}</p>
                        {% if dept.video_type_distribution.prev.total > 0 %}
                        <div class="flex h-6 rounded-full overflow-hidden mb-2">
                            {% if dept.video_type_distribution.prev.longform.pct > 0 %}
                            <div class="bg-indigo-500 flex items-center justify-center" style="width: {{ dept.video_type_distribution.prev.longform.pct }}%;">
                                <span class="text-[9px] text-white font-bold">롱폼</span>
                            </div>
                            {% endif %}
                            {% if dept.video_type_distribution.prev.shortform.pct > 0 %}
                            <div class="bg-pink-400 flex items-center justify-center" style="width: {{ dept.video_type_distribution.prev.shortform.pct }}%;">
                                <span class="text-[9px] text-white font-bold">숏폼</span>
                            </div>
                            {% endif %}
                        </div>
                        <div class="flex gap-4 text-[10px] text-slate-500">
                            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-indigo-500 rounded-full"></span> 롱폼 {{ dept.video_type_distribution.prev.longform.count }}건</span>
                            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-pink-400 rounded-full"></span> 숏폼 {{ dept.video_type_distribution.prev.shortform.count }}건</span>
                        </div>
                        {% else %}
                        <p class="text-xs text-slate-400 italic">데이터 없음</p>
                        {% endif %}
                    </div>
                    <!-- Curr -->
                    <div class="bg-blue-50/30 p-4 rounded-xl border border-blue-100">
                        <p class="text-xs font-bold text-blue-500 uppercase mb-3">{{ dept.curr_month }}</p>
                        {% if dept.video_type_distribution.curr.total > 0 %}
                        <div class="flex h-6 rounded-full overflow-hidden mb-2">
                            {% if dept.video_type_distribution.curr.longform.pct > 0 %}
                            <div class="bg-indigo-500 flex items-center justify-center" style="width: {{ dept.video_type_distribution.curr.longform.pct }}%;">
                                <span class="text-[9px] text-white font-bold">롱폼</span>
                            </div>
                            {% endif %}
                            {% if dept.video_type_distribution.curr.shortform.pct > 0 %}
                            <div class="bg-pink-400 flex items-center justify-center" style="width: {{ dept.video_type_distribution.curr.shortform.pct }}%;">
                                <span class="text-[9px] text-white font-bold">숏폼</span>
                            </div>
                            {% endif %}
                        </div>
                        <div class="flex gap-4 text-[10px] text-slate-500">
                            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-indigo-500 rounded-full"></span> 롱폼 {{ dept.video_type_distribution.curr.longform.count }}건</span>
                            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-pink-400 rounded-full"></span> 숏폼 {{ dept.video_type_distribution.curr.shortform.count }}건</span>
                        </div>
                        {% else %}
                        <p class="text-xs text-slate-400 italic">데이터 없음</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endif %}
            {% endif %}

            <!-- Design: Aggregated Tasks Summary -->
            {% if dept.id == 'design' and dept.design_tasks %}
            <div class="mb-6">
                <h3 class="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                    <i data-lucide="layers" class="w-4 h-4 text-slate-400"></i> 업무 유형별 요약
                </h3>
                <div class="bg-gradient-to-r from-pink-50 to-purple-50 border border-pink-200 rounded-xl overflow-hidden">
                    <div class="grid grid-cols-4 gap-0 bg-pink-100/50 px-4 py-2 text-[10px] font-bold text-slate-500 uppercase border-b border-pink-200">
                        <span>업무 유형</span>
                        <span class="text-center">평균 수정</span>
                        <span class="text-center">전월</span>
                        <span class="text-center">당월</span>
                    </div>
                    <div class="divide-y divide-pink-100">
                        {% for task in dept.design_tasks %}
                        <div class="grid grid-cols-4 gap-0 px-4 py-2.5 items-center">
                            <span class="text-xs font-medium text-slate-700 truncate">{{ task.name }}</span>
                            <span class="text-xs text-slate-500 text-center">{{ task.avg_rev }}회</span>
                            <span class="text-xs text-slate-500 text-center">{{ task.prev }}건</span>
                            <span class="text-xs font-bold text-blue-600 text-center">{{ task.curr }}건</span>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
            {% endif %}

            <!-- Design: Task Tables -->
            {% if dept.id == 'design' %}
            <div class="grid {% if dept.prev_month %}md:grid-cols-2{% endif %} gap-4">
                {% if dept.prev_month %}
                <!-- Prev Month Tasks -->
                <div class="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden">
                    <div class="bg-slate-100 px-4 py-2 flex justify-between items-center">
                        <p class="text-[10px] font-bold text-slate-500 uppercase">{{ dept.prev_month }}</p>
                        {% if dept.tables and dept.tables.prev_task_list %}
                        <p class="text-[10px] text-slate-400">{{ dept.tables.prev_task_list|length }}건 / {{ dept.tables.prev_task_list|sum(attribute='pages') }}p</p>
                        {% endif %}
                    </div>
                    {% if dept.tables and dept.tables.prev_task_list %}
                    <div class="divide-y divide-slate-100">
                        {% for task in dept.tables.prev_task_list %}
                        <div class="px-4 py-2 flex items-center justify-between">
                            <span class="text-xs text-slate-700 truncate flex-1">{{ task.name }}</span>
                            <div class="flex items-center gap-3 text-[10px] text-slate-400 shrink-0">
                                <span>{{ task.revision_count }}회</span>
                                <span class="font-bold text-slate-600">{{ task.pages }}p</span>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <p class="px-4 py-3 text-xs text-slate-400 italic">데이터 없음</p>
                    {% endif %}
                </div>
                {% endif %}
                <!-- Curr Month Tasks -->
                <div class="bg-blue-50/30 rounded-xl border border-blue-100 overflow-hidden">
                    <div class="bg-blue-50 px-4 py-2 flex justify-between items-center">
                        <p class="text-[10px] font-bold text-blue-500 uppercase">{{ dept.curr_month|default(dept.month) }}</p>
                        {% if dept.tables and dept.tables.curr_task_list %}
                        <p class="text-[10px] text-blue-400">{{ dept.tables.curr_task_list|length }}건 / {{ dept.tables.curr_task_list|sum(attribute='pages') }}p</p>
                        {% endif %}
                    </div>
                    {% if dept.tables and dept.tables.curr_task_list %}
                    <div class="divide-y divide-blue-50">
                        {% for task in dept.tables.curr_task_list %}
                        <div class="px-4 py-2 flex items-center justify-between">
                            <span class="text-xs text-slate-700 truncate flex-1">{{ task.name }}</span>
                            <div class="flex items-center gap-3 text-[10px] text-slate-400 shrink-0">
                                <span>{{ task.revision_count }}회</span>
                                <span class="font-bold text-blue-600">{{ task.pages }}p</span>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <p class="px-4 py-3 text-xs text-slate-400 italic">데이터 없음</p>
                    {% endif %}
                </div>
            </div>
            {% endif %}

            <!-- Setting: 병원별 플랫폼 카드 레이아웃 -->
            {% if dept.id == 'setting' and dept.clinic_progress %}
            {% for clinic in dept.clinic_progress %}
            <div class="mb-6">
                <!-- Clinic Header -->
                <div class="flex items-center justify-between mb-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
                    <div class="flex items-center gap-2">
                        <span class="w-2.5 h-2.5 rounded-full" style="background: {% if clinic.progress_rate >= 80 %}#22c55e{% elif clinic.progress_rate >= 50 %}#f59e0b{% else %}#ef4444{% endif %};"></span>
                        <span class="text-sm font-bold text-slate-800">{{ clinic.clinic }}</span>
                        <span class="text-[10px] px-2 py-0.5 rounded-full font-bold {% if clinic.progress_rate >= 80 %}bg-green-100 text-green-700{% elif clinic.progress_rate >= 50 %}bg-amber-100 text-amber-700{% else %}bg-red-100 text-red-700{% endif %}">
                            {% if clinic.progress_rate >= 100 %}완료{% else %}진행{% endif %}
                        </span>
                    </div>
                    <div class="flex items-center gap-2">
                        <div class="w-20 h-2 bg-slate-200 rounded-full overflow-hidden">
                            <div class="h-full rounded-full" style="width: {{ clinic.progress_rate }}%; background: {% if clinic.progress_rate >= 80 %}#22c55e{% elif clinic.progress_rate >= 50 %}#f59e0b{% else %}#ef4444{% endif %};"></div>
                        </div>
                        <span class="text-xs font-bold" style="color: {% if clinic.progress_rate >= 80 %}#16a34a{% elif clinic.progress_rate >= 50 %}#d97706{% else %}#dc2626{% endif %};">{{ clinic.progress_rate|round(1) }}%</span>
                    </div>
                </div>

                <!-- Platform Cards Grid -->
                {% if clinic.platform_groups %}
                <div class="grid md:grid-cols-3 gap-3">
                    {% for group in clinic.platform_groups %}
                    {% set is_wide = group.channels|length > 4 %}
                    <details class="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm group/platform {% if is_wide %}md:col-span-3{% endif %}" open>
                        <!-- Platform Header (clickable toggle) -->
                        <summary class="px-3 py-2 border-b border-slate-100 cursor-pointer list-none select-none hover:bg-slate-50 transition-colors" style="border-top: 3px solid {% if group.completion_rate >= 100 %}#06b6d4{% elif group.completion_rate >= 50 %}#f59e0b{% else %}#ef4444{% endif %};">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-1.5">
                                    <span class="text-[10px] text-slate-400 transition-transform group-open/platform:rotate-90" style="display:inline-block;">▶</span>
                                    <span class="text-xs font-bold text-slate-800">{{ group.platform }}</span>
                                </div>
                                <span class="text-[10px] font-bold" style="color: {% if group.completion_rate >= 100 %}#0891b2{% elif group.completion_rate >= 50 %}#d97706{% else %}#dc2626{% endif %};">{{ group.completed }}/{{ group.total }}</span>
                            </div>
                            <!-- Mini progress bar -->
                            <div class="w-full h-1 bg-slate-100 rounded-full mt-1.5 overflow-hidden">
                                <div class="h-full rounded-full" style="width: {{ group.completion_rate }}%; background: {% if group.completion_rate >= 100 %}#06b6d4{% elif group.completion_rate >= 50 %}#f59e0b{% else %}#ef4444{% endif %};"></div>
                            </div>
                        </summary>
                        <!-- Channel groups with sub-tasks -->
                        <div class="{% if is_wide %}grid md:grid-cols-2 gap-0{% endif %}">
                            {% for ch in group.channels %}
                            <div class="px-3 py-2 {% if is_wide %}border-b border-slate-100 {% if loop.index is odd and not loop.last %}md:border-r{% endif %}{% else %}{% if not loop.last %}border-b border-slate-100{% endif %}{% endif %}">
                                <!-- Channel name header -->
                                <div class="flex items-center justify-between mb-1">
                                    <span class="text-[10px] font-bold text-slate-600 uppercase tracking-wide">{{ ch.channel }}</span>
                                    <span class="text-[9px] font-bold px-1.5 py-0.5 rounded" style="background: {% if ch.status == 'completed' %}#ecfeff{% elif ch.status == 'in_progress' %}#fffbeb{% else %}#f8fafc{% endif %}; color: {% if ch.status == 'completed' %}#0e7490{% elif ch.status == 'in_progress' %}#b45309{% else %}#94a3b8{% endif %}; border: 1px solid {% if ch.status == 'completed' %}#a5f3fc{% elif ch.status == 'in_progress' %}#fde68a{% else %}#e2e8f0{% endif %};">
                                        {{ ch.completed_tasks }}/{{ ch.total_tasks }}
                                    </span>
                                </div>
                                <!-- Sub-task list -->
                                {% if ch.sub_tasks %}
                                <div class="space-y-1">
                                    {% for task in ch.sub_tasks %}
                                    <div class="flex items-start justify-between gap-1.5 pl-2" style="border-left: 2px solid {% if task.status == 'completed' %}#a5f3fc{% elif task.status == 'in_progress' %}#fde68a{% else %}#e2e8f0{% endif %};">
                                        <div class="flex-1 min-w-0">
                                            <p class="text-[10px] {% if task.status == 'completed' %}text-slate-500{% else %}text-slate-700{% endif %} leading-tight">{{ task.type if task.type else '-' }}</p>
                                            {% if task.completion_date %}
                                            <p class="text-[8px] text-slate-400">{{ task.start_date }}{% if task.start_date != task.completion_date %} → {{ task.completion_date }}{% endif %}</p>
                                            {% endif %}
                                        </div>
                                        <span class="text-[8px] font-bold flex-shrink-0 {% if task.status == 'completed' %}text-cyan-600{% elif task.status == 'in_progress' %}text-amber-600{% else %}text-slate-400{% endif %}">
                                            {% if task.status == 'completed' %}✓{% elif task.status == 'in_progress' %}{{ task.status_raw if task.status_raw else '진행' }}{% else %}대기{% endif %}
                                        </span>
                                    </div>
                                    {% endfor %}
                                </div>
                                {% endif %}
                                {% if ch.note %}
                                <p class="text-[8px] text-amber-500 mt-1 pl-2">※ {{ ch.note }}</p>
                                {% endif %}
                            </div>
                            {% endfor %}
                        </div>
                    </details>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% if not loop.last %}
            <div class="border-t border-slate-100 my-4"></div>
            {% endif %}
            {% endfor %}
            {% endif %}

        </div>
        {% endif %}
        {% endfor %}

        <!-- 4. Summary & Action Plan -->
        {% if summary %}
        <div class="card p-6 md:p-10 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white relative overflow-hidden fade-in delay-3">
            <div class="absolute top-0 right-0 w-96 h-96 bg-indigo-500/5 rounded-full blur-3xl -mr-24 -mt-24"></div>
            <div class="absolute bottom-0 left-0 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl -ml-16 -mb-16"></div>
            <div class="relative z-10">
                <div class="flex items-center justify-between mb-8 pb-4 border-b border-white/10">
                    <div class="flex items-center gap-3">
                        <div class="bg-gradient-to-br from-yellow-400/20 to-amber-500/20 p-2.5 rounded-xl border border-yellow-400/20"><i data-lucide="compass" class="w-6 h-6 text-yellow-400"></i></div>
                        <div>
                            <h2 class="text-xl font-bold text-white">{{ summary.title|default('종합 분석 및 전략') }}</h2>
                            <p class="text-[10px] text-slate-400 font-medium uppercase tracking-wider mt-0.5">Strategic Analysis & Action Plan</p>
                        </div>
                    </div>
                </div>

                <!-- Summary Content -->
                {% if summary.content %}
                <div class="bg-white/5 p-5 rounded-xl border border-white/10 mb-6 text-sm text-slate-300 leading-relaxed">
                    {{ summary.content|safe }}
                </div>
                {% endif %}

                <!-- Analysis Sections -->
                {% if summary.analysis_sections %}
                <div class="space-y-4 mb-6">
                    {% for section in summary.analysis_sections %}
                    <div class="bg-white/10 p-5 rounded-xl border border-white/5">
                        <h3 class="font-bold text-slate-200 mb-2">{{ section.title }}</h3>
                        <div class="text-sm text-slate-300 leading-relaxed">{{ section.content|safe }}</div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}

                <!-- Diagnosis -->
                {% if summary.diagnosis %}
                <div class="grid md:grid-cols-2 gap-4 mb-6">
                    {% for item in summary.diagnosis %}
                    <div class="bg-white/10 p-5 rounded-xl border border-white/5">
                        <p class="font-bold text-sm mb-2 {% if loop.index == 1 %}text-green-400{% else %}text-red-400{% endif %}">{{ item.title }}</p>
                        <div class="text-sm text-slate-300 leading-relaxed">{{ item.content|safe }}</div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}

                <!-- Action Plan -->
                {% if summary.action_plan %}
                <div>
                    <h3 class="text-sm font-bold text-slate-300 mb-4 flex items-center gap-2">
                        <span class="bg-indigo-600 text-[10px] px-2 py-0.5 rounded uppercase font-bold">Action Plan</span>
                        {{ summary.action_plan_month|default('') }} 실행 계획
                    </h3>
                    <div class="space-y-3">
                        {% set dept_colors = {'예약': '#3b82f6', '블로그': '#10b981', '유튜브': '#ef4444', '디자인': '#f59e0b', '네이버 광고': '#8b5cf6'} %}
                        {% for item in summary.action_plan %}
                        <div class="strategy-card bg-slate-800 p-4 rounded-xl" style="border-left-color: {{ dept_colors.get(item.department, '#a78bfa') }};">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded" style="background: {{ dept_colors.get(item.department, '#a78bfa') }}20; color: {{ dept_colors.get(item.department, '#a78bfa') }};">{{ item.department }}</span>
                            </div>
                            <p class="text-xs font-bold text-slate-300 mb-1">{{ item.agenda|safe }}</p>
                            {% if item.plan %}
                            <p class="text-sm text-slate-400">{{ item.plan|safe }}</p>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
        {% else %}
        <!-- Default Summary -->
        <div class="card p-6 md:p-8 bg-slate-900 text-white fade-in delay-3">
            <div class="flex items-center gap-3 mb-4">
                <div class="bg-white/10 p-2 rounded-lg"><i data-lucide="file-text" class="w-5 h-5 text-slate-300"></i></div>
                <h2 class="text-lg font-bold">종합 요약</h2>
            </div>
            <p class="text-sm text-slate-300">전반적인 데이터 분석 결과, 각 채널별로 유의미한 성과와 개선점이 확인되었습니다.</p>
            <p class="text-sm text-slate-400 mt-2">위 데이터를 바탕으로 다음 달 마케팅 전략을 수립하시기 바랍니다.</p>
        </div>
        {% endif %}

        <!-- 5. Footer -->
        <footer class="text-center py-8 fade-in delay-4">
            <div class="inline-flex items-center gap-2 bg-white/80 backdrop-blur-sm px-5 py-2.5 rounded-full shadow-sm border border-slate-200">
                <i data-lucide="sparkles" class="w-3.5 h-3.5 text-indigo-400"></i>
                <p class="text-xs text-slate-500 font-medium">Generated by Marketing Analytics System | Powered by <span class="font-bold text-slate-600">(주)그룹디</span></p>
            </div>
        </footer>

    </div>

    <script>
        lucide.createIcons();
    </script>
</body>
</html>

"""


def format_metric_value(value: Any, format_type: str = 'number') -> str:
    """Format metric value for display."""
    if value is None:
        return '-'
    if format_type == 'percent':
        return f"{value:.1f}" if isinstance(value, float) else str(value)
    if format_type == 'currency':
        return f"₩{int(value):,}"
    if isinstance(value, float):
        if abs(value) >= 1000000:
            return f"{value/1000000:,.1f}M"
        elif abs(value) >= 1000:
            return f"{value:,.0f}"
        else:
            return f"{value:,.1f}"
    return f"{value:,}" if isinstance(value, int) else str(value)


def prepare_reservation_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare reservation department data."""
    curr_month = result.get('month', '-')
    prev_month = result.get('prev_month', '-')
    curr_data = result.get('current_month_data', {})
    prev_data = result.get('prev_month_data', {})
    tables = result.get('tables', {})
    kpi = result.get('kpi', {})

    # 실 예약 수 (이용일시 기준)
    actual_reservations = kpi.get('actual_reservations', 0)
    prev_actual_reservations = kpi.get('prev_actual_reservations', 0)

    # Metrics - 아이콘 박스 스타일 적용
    prev_metrics = [
        {'icon': '📋', 'label': '총 신청', 'value': prev_data.get('total_reservations', 0), 'unit': ' 건', 'icon_box_class': 'blue', 'bg_class': 'bg-gray'},
        {'icon': '✅', 'label': '내원 확정', 'value': prev_actual_reservations, 'unit': ' 건', 'icon_box_class': 'green', 'bg_class': 'bg-green', 'color_class': 'green'},
        {'icon': '❌', 'label': '취소/노쇼', 'value': prev_data.get('canceled_count', 0), 'unit': ' 건', 'icon_box_class': 'red', 'bg_class': 'bg-red', 'color_class': 'red'},
    ]
    curr_metrics = [
        {'icon': '📋', 'label': '총 신청', 'value': curr_data.get('total_reservations', 0), 'unit': ' 건', 'icon_box_class': 'blue', 'bg_class': 'bg-blue', 'label_color': '#3b82f6'},
        {'icon': '✅', 'label': '내원 확정', 'value': actual_reservations, 'unit': ' 건', 'icon_box_class': 'green', 'bg_class': 'bg-green', 'color_class': 'green', 'label_color': '#22c55e'},
        {'icon': '❌', 'label': '취소/노쇼', 'value': curr_data.get('canceled_count', 0), 'unit': ' 건', 'icon_box_class': 'red', 'bg_class': 'bg-red', 'color_class': 'red', 'label_color': '#ef4444'},
    ]

    # Helper function to get icon and class for how_found
    def get_how_found_icon(label: str):
        label_lower = label.lower() if label else ''
        if '온라인' in label_lower or '인터넷' in label_lower or '검색' in label_lower or '네이버' in label_lower:
            return '🔍', 'online'
        elif '오프라인' in label_lower or '간판' in label_lower or '지나가다' in label_lower:
            return '🏢', 'offline'
        elif '지인' in label_lower or '소개' in label_lower or '추천' in label_lower:
            return '👥', 'referral'
        else:
            return '❓', 'other'

    # TOP5 sections
    top5_sections = []

    # Treatment TOP5 - 진료 항목별 색상 바
    prev_treatment = tables.get('prev_treatment_top5', [])
    curr_treatment = tables.get('treatment_top5', [])
    if prev_treatment or curr_treatment:
        prev_max = max((t.get('count', 0) for t in prev_treatment), default=1) or 1
        curr_max = max((t.get('count', 0) for t in curr_treatment), default=1) or 1

        top5_sections.append({
            'title': '주요 희망 진료 TOP5',
            'icon': '🦷',
            'bar_color': 'blue',
            'prev_items': [{'label': t.get('treatment', ''), 'value_display': f"{t.get('count', 0)}건", 'pct': (t.get('count', 0) / prev_max) * 100} for t in prev_treatment[:5]],
            'curr_items': [{'label': t.get('treatment', ''), 'value_display': f"{t.get('count', 0)}건", 'pct': (t.get('count', 0) / curr_max) * 100} for t in curr_treatment[:5]],
        })

    # How found TOP5 - 아이콘 추가
    prev_how_found = tables.get('prev_how_found_top5', [])
    curr_how_found = tables.get('how_found_top5', [])
    if prev_how_found or curr_how_found:
        prev_max = max((t.get('count', 0) for t in prev_how_found), default=1) or 1
        curr_max = max((t.get('count', 0) for t in curr_how_found), default=1) or 1
        prev_total = sum(t.get('count', 0) for t in prev_how_found) or 1
        curr_total = sum(t.get('count', 0) for t in curr_how_found) or 1

        def make_how_found_item(t, total, max_val):
            label = t.get('how_found', '')
            icon, icon_class = get_how_found_icon(label)
            return {
                'label': label,
                'value_display': f"{(t.get('count', 0) / total * 100):.1f}%",
                'sub_value': f"{t.get('count', 0)}건",
                'pct': (t.get('count', 0) / max_val) * 100,
                'icon': icon,
                'icon_class': icon_class
            }

        top5_sections.append({
            'title': '어떻게 치과를 알게 되었나요? TOP5',
            'icon': '🔍',
            'bar_color': 'green',
            'prev_items': [make_how_found_item(t, prev_total, prev_max) for t in prev_how_found[:5]],
            'curr_items': [make_how_found_item(t, curr_total, curr_max) for t in curr_how_found[:5]],
        })

    # Cancel reason TOP5 - 빨간색 바
    prev_cancel = tables.get('prev_cancel_reason_top5', [])
    curr_cancel = tables.get('cancel_reason_top5', [])
    if prev_cancel or curr_cancel:
        prev_max = max((t.get('count', 0) for t in prev_cancel), default=1) or 1
        curr_max = max((t.get('count', 0) for t in curr_cancel), default=1) or 1
        top5_sections.append({
            'title': '주요 예약 취소 사유 TOP5',
            'icon': '❌',
            'bar_color': 'red',
            'prev_items': [{'label': t.get('cancel_reason', ''), 'value_display': f"{t.get('count', 0)}건", 'pct': (t.get('count', 0) / prev_max) * 100} for t in prev_cancel[:5]],
            'curr_items': [{'label': t.get('cancel_reason', ''), 'value_display': f"{t.get('count', 0)}건", 'pct': (t.get('count', 0) / curr_max) * 100} for t in curr_cancel[:5]],
        })

    return {
        'prev_month': prev_month,
        'curr_month': curr_month,
        'prev_metrics': prev_metrics,
        'curr_metrics': curr_metrics,
        'top5_sections': top5_sections,
    }


def prepare_blog_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare blog department data."""
    curr_month = result.get('month', '-')
    prev_month = result.get('prev_month', '-')
    curr_data = result.get('current_month_data', {})
    prev_data = result.get('prev_month_data', {})
    curr_work = curr_data.get('work', {})
    prev_work = prev_data.get('work', {})
    tables = result.get('tables', {})
    diagnosis = result.get('diagnosis', {})
    insights_data = result.get('insights', {})
    kpi = result.get('kpi', {})

    # KPI에서 이월 건수 가져오기
    # CSV 파일의 "지난달 이월 건수" 컬럼 값을 그대로 사용
    prev_contract = kpi.get('prev_contract_count', 0) or prev_work.get('contract_count', 0) or 0
    prev_published = kpi.get('prev_published_count', 0) or prev_work.get('published_count', 0) or 0
    prev_carryover = kpi.get('prev_carryover_count', 0) or max(0, prev_contract - prev_published)

    curr_contract = kpi.get('contract_count', 0) or curr_work.get('contract_count', 0) or 0
    curr_published = kpi.get('published_count', 0) or curr_work.get('published_count', 0) or 0
    # 당월 이월 건수 = CSV 파일의 "지난달 이월 건수" 컬럼 값 사용 (계산하지 않음)
    curr_carryover = kpi.get('carryover_count', 0) or max(0, curr_contract - curr_published)

    # 자료 미수신 건수
    pending_data_count = kpi.get('pending_data_count', 0)

    # Metrics - Row 1 (핵심 요약) - 아이콘 박스 스타일
    prev_metrics = [
        {'icon': '👁️', 'label': '총 조회수', 'value': f"{prev_data.get('total_views', 0):,}", 'unit': '회', 'icon_box_class': 'blue', 'bg_class': 'bg-gray'},
        {'icon': '📄', 'label': '계약 건수', 'value': prev_contract, 'unit': '건', 'icon_box_class': 'purple', 'bg_class': 'bg-gray'},
    ]
    curr_metrics = [
        {'icon': '👁️', 'label': '총 조회수', 'value': f"{curr_data.get('total_views', 0):,}", 'unit': '회', 'icon_box_class': 'blue', 'bg_class': 'bg-blue', 'label_color': '#3b82f6'},
        {'icon': '📄', 'label': '계약 건수', 'value': curr_contract, 'unit': '건', 'icon_box_class': 'purple', 'bg_class': '', 'label_color': '#8b5cf6'},
    ]

    # Metrics - Row 2 (이월 건수 추가) - 아이콘 박스 스타일
    prev_metrics_row2 = [
        {'icon': '✅', 'label': '발행 완료', 'value': prev_published, 'unit': '건', 'color_class': 'green', 'icon_box_class': 'green', 'bg_class': 'bg-gray'},
        {'icon': '➡️', 'label': '이월', 'value': prev_carryover, 'unit': '건', 'color_class': 'orange' if prev_carryover > 0 else '', 'icon_box_class': 'orange', 'bg_class': 'bg-gray'},
    ]
    # 자료 미수신 건수가 있으면 note로 표시 (소명)
    curr_carryover_note = f"⏳ 병원 측 임상 자료 대기 중 ({pending_data_count}건)" if pending_data_count > 0 else None
    curr_metrics_row2 = [
        {'icon': '✅', 'label': '발행 완료', 'value': curr_published, 'unit': '건', 'color_class': 'green', 'icon_box_class': 'green', 'bg_class': 'bg-green', 'label_color': '#22c55e'},
        {'icon': '➡️', 'label': '이월', 'value': curr_carryover, 'unit': '건', 'color_class': 'orange' if curr_carryover > 0 else '', 'icon_box_class': 'orange', 'bg_class': '', 'note': curr_carryover_note},
    ]

    # TOP5 sections
    top5_sections = []

    # Views TOP5 (당월 기준 - 조회수 순위 데이터는 누적 기준)
    views_top5 = tables.get('views_top5', [])
    prev_views_top5 = tables.get('prev_views_top5', [])
    if views_top5 or prev_views_top5:
        curr_max = max((t.get('views', 0) for t in views_top5), default=1) or 1
        prev_max = max((t.get('views', 0) for t in prev_views_top5), default=1) or 1
        top5_sections.append({
            'title': '조회수 TOP 5 게시물',
            'icon': '👁️',
            'bar_color': 'blue',
            'prev_items': [{'label': t.get('title', '')[:40], 'value_display': f"{t.get('views', 0):,}회", 'pct': (t.get('views', 0) / prev_max) * 100} for t in prev_views_top5[:5]] if prev_views_top5 else [],
            'curr_items': [{'label': t.get('title', '')[:40], 'value_display': f"{t.get('views', 0):,}회", 'pct': (t.get('views', 0) / curr_max) * 100} for t in views_top5[:5]],
            'no_prev_data_msg': '전월 데이터 없음' if not prev_views_top5 else None,
        })

    # Source TOP5 (유입경로 = 검색 키워드)
    source_top5 = tables.get('source_top5', [])
    prev_source_top5 = tables.get('prev_source_top5', [])
    if source_top5 or prev_source_top5:
        # 기타 제외한 항목만 표시
        curr_items_filtered = [t for t in source_top5 if t.get('source', '') != '기타'][:5]
        prev_items_filtered = [t for t in prev_source_top5 if t.get('source', '') != '기타'][:5]
        curr_max = max((t.get('ratio', 0) for t in curr_items_filtered), default=1) or 1
        prev_max = max((t.get('ratio', 0) for t in prev_items_filtered), default=1) or 1
        top5_sections.append({
            'title': '유입 키워드 TOP5',
            'icon': '🏷️',
            'bar_color': 'purple',
            'prev_items': [{'label': t.get('source', ''), 'value_display': f"{t.get('ratio', 0):.1f}%", 'pct': (t.get('ratio', 0) / prev_max) * 100} for t in prev_items_filtered] if prev_items_filtered else [],
            'curr_items': [{'label': t.get('source', ''), 'value_display': f"{t.get('ratio', 0):.1f}%", 'pct': (t.get('ratio', 0) / curr_max) * 100} for t in curr_items_filtered],
            'no_prev_data_msg': '전월 데이터 없음' if not prev_items_filtered else None,
        })

    # Traffic TOP5 + 기타 (총 6개) - 상세유입경로
    traffic_top5 = tables.get('traffic_top5', [])
    prev_traffic_top5 = tables.get('prev_traffic_top5', [])
    if traffic_top5 or prev_traffic_top5:
        curr_max = max((t.get('ratio', 0) for t in traffic_top5), default=1) or 1
        prev_max = max((t.get('ratio', 0) for t in prev_traffic_top5), default=1) or 1
        top5_sections.append({
            'title': '상세유입경로 TOP5',
            'icon': '🔍',
            'bar_color': 'green',
            'prev_items': [{'label': t.get('source', ''), 'value_display': f"{t.get('ratio', 0):.1f}%", 'pct': (t.get('ratio', 0) / prev_max) * 100} for t in prev_traffic_top5[:6]] if prev_traffic_top5 else [],
            'curr_items': [{'label': t.get('source', ''), 'value_display': f"{t.get('ratio', 0):.1f}%", 'pct': (t.get('ratio', 0) / curr_max) * 100} for t in traffic_top5[:6]],
            'no_prev_data_msg': '전월 데이터 없음' if not prev_traffic_top5 else None,
        })

    # Key insights for yellow box
    key_insights = {}

    # Get top post from views_top5
    views_top5 = tables.get('views_top5', [])
    if views_top5:
        top_post = views_top5[0]
        key_insights['top_post'] = {
            'title': top_post.get('title', ''),
            'views': f"{top_post.get('views', 0):,}"
        }

    # Get top keyword from source_top5 (유입 키워드) - 기타 제외
    source_for_insight = [s for s in tables.get('source_top5', []) if s.get('source', '') != '기타']
    if source_for_insight:
        top_keyword = source_for_insight[0]
        key_insights['top_keyword'] = {
            'keyword': top_keyword.get('source', ''),
            'ratio': f"{top_keyword.get('ratio', 0):.1f}"
        }
    elif traffic_top5:
        # Fallback to traffic if no source data
        top_keyword = traffic_top5[0]
        key_insights['top_keyword'] = {
            'keyword': top_keyword.get('source', ''),
            'ratio': f"{top_keyword.get('ratio', 0):.1f}"
        }

    # 발행일 형식 변환 함수 (요일 제거, YYYY-MM-DD 형식으로)
    def format_publish_date(date_str: str) -> str:
        """발행일을 YYYY-MM-DD 형식으로 변환 (요일 제거)"""
        if not date_str or date_str.lower() == 'nan':
            return ''
        # 이미 YYYY-MM-DD 형식이면 그대로 반환
        import re
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        # YYYY.MM.DD(요일) 형식 처리
        match = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})', date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        # 다른 형식 시도
        try:
            from datetime import datetime
            for fmt in ['%Y.%m.%d', '%Y/%m/%d', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(date_str.split('(')[0].strip(), fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
        except:
            pass
        return date_str

    # Posting list (포스팅) - 당월 데이터 (제목이 있는 모든 포스팅)
    posting_list = []
    raw_posting_list = tables.get('posting_list', [])

    for post in raw_posting_list:
        title = post.get('title', '')
        url = post.get('url', '')
        if title and title.lower() != 'nan':
            write_date = post.get('write_date', '')
            posting_list.append({
                'title': title,
                'url': url if url and url.lower() != 'nan' else '',
                'date': format_publish_date(write_date) if write_date else ''
            })

    # 전월 포스팅 리스트
    prev_posting_list = []
    raw_prev_posting_list = tables.get('prev_posting_list', [])

    for post in raw_prev_posting_list:
        title = post.get('title', '')
        url = post.get('url', '')
        if title and title.lower() != 'nan':
            write_date = post.get('write_date', '')
            prev_posting_list.append({
                'title': title,
                'url': url if url and url.lower() != 'nan' else '',
                'date': format_publish_date(write_date) if write_date else ''
            })

    return {
        'prev_month': prev_month,
        'curr_month': curr_month,
        'prev_metrics': prev_metrics,
        'curr_metrics': curr_metrics,
        'prev_metrics_row2': prev_metrics_row2,
        'curr_metrics_row2': curr_metrics_row2,
        'top5_sections': top5_sections,
        'key_insights': key_insights if key_insights else None,
        'posting_list': posting_list if posting_list else None,
        'prev_posting_list': prev_posting_list if prev_posting_list else None,
    }


def prepare_ads_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare ads department data."""
    curr_month = result.get('month', '-')
    prev_month = result.get('prev_month', '-')
    curr_data = result.get('current_month_data', {})
    prev_data = result.get('prev_month_data', {})
    tables = result.get('tables', {})
    kpi = result.get('kpi', {})

    curr_campaign = curr_data.get('campaign', {})
    prev_campaign = prev_data.get('campaign', {})

    # CPA 데이터
    cpa = kpi.get('cpa', 0)
    prev_cpa = kpi.get('prev_cpa', 0)

    # Metrics - Ads Revisions (노출수, 클릭수 위주)
    # CPA, 광고비 제거 요청 반영
    
    # Impressions from KPI (aggregated from campaign data)
    curr_imp_val = kpi.get('total_impressions', 0) or curr_data.get('campaign', {}).get('total_impressions', 0)
    prev_imp_val = kpi.get('prev_total_impressions', 0) or prev_data.get('campaign', {}).get('total_impressions', 0)

    prev_metrics = [
        {'icon': '👁️', 'label': '노출수', 'value': f"{int(prev_imp_val):,}", 'unit': ' 회', 'icon_box_class': 'blue', 'bg_class': 'bg-gray'},
        {'icon': '👆', 'label': '클릭수', 'value': f"{prev_campaign.get('total_clicks', 0):,}", 'unit': ' 회', 'icon_box_class': 'green', 'bg_class': 'bg-gray'},
    ]
    curr_metrics = [
        {'icon': '👁️', 'label': '노출수', 'value': f"{int(curr_imp_val):,}", 'unit': ' 회', 'icon_box_class': 'blue', 'bg_class': 'bg-blue', 'label_color': '#3b82f6'},
        {'icon': '👆', 'label': '클릭수', 'value': f"{curr_campaign.get('total_clicks', 0):,}", 'unit': ' 회', 'icon_box_class': 'green', 'bg_class': 'bg-green', 'label_color': '#22c55e'},
    ]

    # TOP5 sections
    top5_sections = []

    # TOP5 sections - 중복 제거 (아래 4열 그리드로 대체)
    top5_sections = []

    # TOP5 sections (데이터 추출)
    prev_impressions = tables.get('prev_keyword_top5_impressions', [])
    curr_impressions = tables.get('keyword_top5_impressions', [])
    prev_clicks = tables.get('prev_keyword_top5_clicks', [])
    curr_clicks = tables.get('keyword_top5_clicks', [])

    # CPA 배너 데이터
    cpa_growth = kpi.get('cpa_growth', 0)
    actual_reservations = kpi.get('actual_reservations', 0)
    cpa_banner = None
    if cpa > 0:
        cpa_change_text = ""
        cpa_change_color = "#64748b"
        if prev_cpa > 0:
            if cpa_growth < 0:
                cpa_change_text = f"전월 대비 {abs(cpa_growth):.1f}% 절감"
                cpa_change_color = "#22c55e"
            elif cpa_growth > 0:
                cpa_change_text = f"전월 대비 {cpa_growth:.1f}% 증가"
                cpa_change_color = "#ef4444"
        cpa_banner = {
            'cpa': f"₩{int(cpa):,}",
            'actual_reservations': actual_reservations,
            'change_text': cpa_change_text,
            'change_color': cpa_change_color
        }

    # 4열 광고 랭킹 데이터 (전월 노출/클릭, 당월 노출/클릭)
    ads_ranking_data = {}

    # 전월 노출수 TOP5
    if prev_impressions:
        prev_imp_max = max((t.get('impressions', 0) for t in prev_impressions), default=1) or 1
        ads_ranking_data['prev_impressions'] = [
            {
                'keyword': t.get('keyword', ''),
                'impressions': f"{t.get('impressions', 0):,}",
                'clicks': f"{t.get('clicks', 0):,}",
                'pct': (t.get('impressions', 0) / prev_imp_max) * 100
            } for t in prev_impressions[:5]
        ]
    else:
        ads_ranking_data['prev_impressions'] = []

    # 전월 클릭수 TOP5
    if prev_clicks:
        prev_clk_max = max((t.get('clicks', 0) for t in prev_clicks), default=1) or 1
        ads_ranking_data['prev_clicks'] = [
            {
                'keyword': t.get('keyword', ''),
                'impressions': f"{t.get('impressions', 0):,}",
                'clicks': f"{t.get('clicks', 0):,}",
                'pct': (t.get('clicks', 0) / prev_clk_max) * 100
            } for t in prev_clicks[:5]
        ]
    else:
        ads_ranking_data['prev_clicks'] = []

    # 당월 노출수 TOP5
    if curr_impressions:
        curr_imp_max = max((t.get('impressions', 0) for t in curr_impressions), default=1) or 1
        ads_ranking_data['curr_impressions'] = [
            {
                'keyword': t.get('keyword', ''),
                'impressions': f"{t.get('impressions', 0):,}",
                'clicks': f"{t.get('clicks', 0):,}",
                'pct': (t.get('impressions', 0) / curr_imp_max) * 100
            } for t in curr_impressions[:5]
        ]
    else:
        ads_ranking_data['curr_impressions'] = []

    # 당월 클릭수 TOP5
    if curr_clicks:
        curr_clk_max = max((t.get('clicks', 0) for t in curr_clicks), default=1) or 1
        ads_ranking_data['curr_clicks'] = [
            {
                'keyword': t.get('keyword', ''),
                'impressions': f"{t.get('impressions', 0):,}",
                'clicks': f"{t.get('clicks', 0):,}",
                'pct': (t.get('clicks', 0) / curr_clk_max) * 100
            } for t in curr_clicks[:5]
        ]
    else:
        ads_ranking_data['curr_clicks'] = []

    return {
        'prev_month': prev_month,
        'curr_month': curr_month,
        'prev_metrics': prev_metrics,
        'curr_metrics': curr_metrics,
        'top5_sections': top5_sections,
        'cpa_banner': cpa_banner,
        'ads_ranking_data': ads_ranking_data,
    }


def prepare_design_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare design department data."""
    curr_month = result.get('month') or '-'
    prev_month = result.get('prev_month') or None
    tables = result.get('tables', {})

    # Use aggregated_tasks from design.py
    aggregated_tasks = tables.get('aggregated_tasks', [])
    
    design_tasks = []
    for task in aggregated_tasks:
        design_tasks.append({
            'name': task.get('task_name', ''),
            'avg_rev': task.get('avg_revision', 0),
            'prev': task.get('prev_count', 0),
            'curr': task.get('curr_count', 0)
        })

    return {
        'prev_month': prev_month,
        'curr_month': curr_month,
        # No metrics needed as requested by user
        'curr_metrics': [],
        'design_tasks': design_tasks,
        'tables': tables, # Added this line to fix UndefinedError
    }


def _group_channels_by_platform(channels: list) -> list:
    """Group channels by platform prefix (e.g., 네이버, 카카오, 구글)."""
    platform_map = {}
    platform_order = []

    for ch in channels:
        ch_name = ch.get('channel', '')
        sub_tasks = ch.get('sub_tasks', [])
        total_tasks = ch.get('total_tasks', 0)
        completed_tasks = ch.get('completed_tasks', 0)

        # Skip channels with no tasks
        if total_tasks == 0:
            continue

        # Determine platform group
        platform = ch_name  # default: channel name IS the platform
        for prefix in ['자료 수신', '네비게이션', '네이버', '카카오', '구글', 'Google']:
            if ch_name.startswith(prefix):
                platform = prefix
                break

        if platform not in platform_map:
            platform_map[platform] = {
                'platform': platform,
                'channels': [],
                'completed_tasks': 0,
                'total_tasks': 0,
            }
            platform_order.append(platform)

        platform_map[platform]['channels'].append(ch)
        platform_map[platform]['completed_tasks'] += completed_tasks
        platform_map[platform]['total_tasks'] += total_tasks

    # Calculate completion rate per platform (based on sub-tasks)
    result = []
    for p_name in platform_order:
        group = platform_map[p_name]
        total = group['total_tasks']
        completed = group['completed_tasks']
        group['completion_rate'] = round((completed / total * 100) if total > 0 else 0, 1)
        group['completed'] = completed
        group['total'] = total
        result.append(group)

    return result


def prepare_setting_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare setting department data."""
    kpi = result.get('kpi', {})
    tables = result.get('tables', {})

    avg_progress = kpi.get('avg_progress_rate', 0)
    completed_clinics = kpi.get('completed_clinics', 0)
    risk_clinics = kpi.get('risk_clinics', 0)
    total_clinics = kpi.get('total_clinics', 0)

    # Channel completion rates
    channel_completion = tables.get('channel_completion_rate', [])

    # Clinic progress with per-clinic platform grouping
    clinic_progress_raw = tables.get('clinic_progress', [])
    clinic_progress = []
    for clinic in clinic_progress_raw:
        grouped = _group_channels_by_platform(clinic.get('channels', []))
        clinic_progress.append({
            'clinic': clinic.get('clinic', ''),
            'total_channels': clinic.get('total_channels', 0),
            'completed_channels': clinic.get('completed_channels', 0),
            'progress_rate': clinic.get('progress_rate', 0),
            'platform_groups': grouped,
        })

    return {
        'avg_progress_rate': round(avg_progress, 1),
        'completed_clinics': completed_clinics,
        'risk_clinics': risk_clinics,
        'total_clinics': total_clinics,
        'channel_completion': channel_completion,
        'clinic_progress': clinic_progress,
        'prev_metrics': [],
        'curr_metrics': [],
    }


def prepare_youtube_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare youtube department data."""
    curr_month = result.get('month', '-')
    prev_month = result.get('prev_month', '-')
    curr_data = result.get('current_month_data', {})
    prev_data = result.get('prev_month_data', {})
    curr_content = curr_data.get('content', {})
    prev_content = prev_data.get('content', {})
    tables = result.get('tables', {})
    kpi = result.get('kpi', {})

    # 영상 종류별 통계 가져오기
    video_type_stats = tables.get('video_type_stats', {})
    prev_video_type_stats = tables.get('prev_video_type_stats', {})

    longform_stats = video_type_stats.get('롱폼', {})
    shortform_stats = video_type_stats.get('숏폼', {})
    prev_longform_stats = prev_video_type_stats.get('롱폼', {})
    prev_shortform_stats = prev_video_type_stats.get('숏폼', {})

    # Channel metrics - 채널 성과 (3개 지표)
    # 총 시청 시간은 소수점 없이 정수로 표시
    prev_watch_time = int(prev_content.get('total_watch_time', 0))
    curr_watch_time = int(curr_content.get('total_watch_time', 0))

    prev_channel_metrics = [
        {'icon': '🔴', 'label': '총 조회수', 'value': f"{prev_content.get('total_views', 0):,}", 'unit': '회', 'icon_box_class': 'red', 'bg_class': 'bg-gray'},
        {'icon': '⏱️', 'label': '총 시청 시간', 'value': f"{prev_watch_time:,}", 'unit': '시간', 'icon_box_class': 'orange', 'bg_class': 'bg-gray'},
        {'icon': '👥', 'label': '구독자 증감', 'value': f"+{prev_content.get('new_subscribers', 0)}", 'unit': '명', 'icon_box_class': 'green', 'bg_class': 'bg-gray'},
    ]
    curr_channel_metrics = [
        {'icon': '🔴', 'label': '총 조회수', 'value': f"{curr_content.get('total_views', 0):,}", 'unit': '회', 'icon_box_class': 'red', 'bg_class': 'bg-red', 'label_color': '#ef4444'},
        {'icon': '⏱️', 'label': '총 시청 시간', 'value': f"{curr_watch_time:,}", 'unit': '시간', 'icon_box_class': 'orange', 'bg_class': 'bg-orange', 'label_color': '#f97316'},
        {'icon': '👥', 'label': '구독자 증감', 'value': f"+{curr_content.get('new_subscribers', 0)}", 'unit': '명', 'icon_box_class': 'green', 'bg_class': 'bg-green', 'label_color': '#22c55e'},
    ]

    # Production metrics - 제작 성과 (계약/완료)
    prev_contract = kpi.get('prev_contract_count', 0)
    prev_completed = kpi.get('prev_completed_count', 0)
    curr_contract = kpi.get('contract_count', 0)
    curr_completed = kpi.get('completed_count', 0)

    prev_production_metrics = [
        {'icon': '📝', 'label': '계약 건수', 'value': prev_contract, 'unit': '건', 'icon_box_class': 'purple', 'bg_class': 'bg-gray'},
        {'icon': '✅', 'label': '제작 완료', 'value': prev_completed, 'unit': '건', 'icon_box_class': 'blue', 'bg_class': 'bg-gray'},
    ]
    curr_production_metrics = [
        {'icon': '📝', 'label': '계약 건수', 'value': curr_contract, 'unit': '건', 'icon_box_class': 'purple', 'bg_class': '', 'label_color': '#8b5cf6'},
        {'icon': '✅', 'label': '제작 완료', 'value': curr_completed, 'unit': '건', 'icon_box_class': 'blue', 'bg_class': 'bg-blue', 'label_color': '#3b82f6'},
    ]

    # TOP3 sections (조회수 TOP3 동영상 + 트래픽 소스 TOP3)
    top3_sections = []

    # Videos TOP3 (당월/전월 비교)
    top5_videos = tables.get('top5_videos', [])
    prev_top5_videos = tables.get('prev_top5_videos', [])
    if top5_videos or prev_top5_videos:
        curr_max = max((t.get('views', 0) for t in top5_videos), default=1) or 1
        prev_max = max((t.get('views', 0) for t in prev_top5_videos), default=1) or 1
        top3_sections.append({
            'title': '조회수 TOP 3 동영상',
            'icon': '🎬',
            'bar_color': 'red',
            'prev_items': [{'label': t.get('title', '')[:25], 'value_display': f"{t.get('views', 0):,} 회", 'pct': (t.get('views', 0) / prev_max) * 100} for t in prev_top5_videos[:3]] if prev_top5_videos else [],
            'curr_items': [{'label': t.get('title', '')[:25], 'value_display': f"{t.get('views', 0):,} 회", 'pct': (t.get('views', 0) / curr_max) * 100} for t in top5_videos[:3]],
            'no_prev_data_msg': '데이터 없음' if not prev_top5_videos else None,
        })

    # Traffic source TOP3 (당월/전월 비교)
    traffic = tables.get('traffic_by_source', [])
    prev_traffic = tables.get('prev_traffic_by_source', [])
    if traffic or prev_traffic:
        curr_max = max((t.get('views', 0) for t in traffic), default=1) or 1
        curr_total = sum(t.get('views', 0) for t in traffic) or 1
        prev_max = max((t.get('views', 0) for t in prev_traffic), default=1) or 1
        prev_total = sum(t.get('views', 0) for t in prev_traffic) or 1
        top3_sections.append({
            'title': '트래픽 소스 TOP 3',
            'icon': '📡',
            'bar_color': 'amber',
            'prev_items': [{'label': t.get('source', ''), 'value_display': f"{(t.get('views', 0) / prev_total * 100):.1f} %", 'pct': (t.get('views', 0) / prev_max) * 100} for t in prev_traffic[:3]] if prev_traffic else [],
            'curr_items': [{'label': t.get('source', ''), 'value_display': f"{(t.get('views', 0) / curr_total * 100):.1f} %", 'pct': (t.get('views', 0) / curr_max) * 100} for t in traffic[:3]],
            'no_prev_data_msg': '데이터 없음' if not prev_traffic else None,
        })

    # Video type distribution (영상 종류별 분포)
    # 전월
    prev_longform_completed = prev_longform_stats.get('completed', 0)
    prev_shortform_completed = prev_shortform_stats.get('completed', 0)
    prev_total_completed = prev_longform_completed + prev_shortform_completed

    # 당월
    curr_longform_completed = longform_stats.get('completed', 0)
    curr_shortform_completed = shortform_stats.get('completed', 0)
    curr_total_completed = curr_longform_completed + curr_shortform_completed

    video_type_distribution = {
        'prev': {
            'longform': {'count': prev_longform_completed, 'pct': round((prev_longform_completed / prev_total_completed * 100), 1) if prev_total_completed > 0 else 0},
            'shortform': {'count': prev_shortform_completed, 'pct': round((prev_shortform_completed / prev_total_completed * 100), 1) if prev_total_completed > 0 else 0},
            'total': prev_total_completed
        },
        'curr': {
            'longform': {'count': curr_longform_completed, 'pct': round((curr_longform_completed / curr_total_completed * 100), 1) if curr_total_completed > 0 else 0},
            'shortform': {'count': curr_shortform_completed, 'pct': round((curr_shortform_completed / curr_total_completed * 100), 1) if curr_total_completed > 0 else 0},
            'total': curr_total_completed
        }
    }

    return {
        'prev_month': prev_month,
        'curr_month': curr_month,
        'prev_metrics': prev_channel_metrics,  # 채널 성과
        'curr_metrics': curr_channel_metrics,
        'prev_production_metrics': prev_production_metrics,  # 제작 성과
        'curr_production_metrics': curr_production_metrics,
        'top5_sections': top3_sections,  # TOP3 sections (기존 구조 유지)
        'video_type_distribution': video_type_distribution,  # 영상 종류별 분포
    }


def prepare_department_data(name: str, dept_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare department data for HTML template."""
    dept_styles = {
        'reservation': {'icon': '📅', 'color_bg': '#dbeafe'},
        'blog': {'icon': '📝', 'color_bg': '#dcfce7'},
        'ads': {'icon': '📊', 'color_bg': '#fef3c7'},
        'design': {'icon': '🎨', 'color_bg': '#fce7f3'},
        'youtube': {'icon': '🎬', 'color_bg': '#fee2e2'},
        'setting': {'icon': '⚙️', 'color_bg': '#e0e7ff'},
    }

    style = dept_styles.get(dept_id, {'icon': '📋', 'color_bg': '#f1f5f9'})

    if not result or not result.get('kpi'):
        return {'name': name, 'id': dept_id, 'has_data': False, 'icon': style['icon'], 'color_bg': style['color_bg']}

    # Get department-specific data
    dept_data = {}
    if dept_id == 'reservation':
        dept_data = prepare_reservation_data(result)
    elif dept_id == 'blog':
        dept_data = prepare_blog_data(result)
    elif dept_id == 'ads':
        dept_data = prepare_ads_data(result)
    elif dept_id == 'design':
        dept_data = prepare_design_data(result)
    elif dept_id == 'youtube':
        dept_data = prepare_youtube_data(result)
    elif dept_id == 'setting':
        dept_data = prepare_setting_data(result)

    return {
        'name': name,
        'id': dept_id,
        'has_data': True,
        'icon': style['icon'],
        'color_bg': style['color_bg'],
        **dept_data
    }



def calculate_best_worst(results: Dict[str, Any]) -> tuple:
    """Find best and worst performing metrics by MoM growth rate."""
    candidates = []
    metric_configs = [
        ('reservation', 'total_reservations', '총 예약 신청', '예약'),
        ('blog', 'views', '블로그 조회수', '블로그'),
        ('ads', 'impressions', '광고 노출수', '광고'),
        ('youtube', 'views', '영상 조회수', '유튜브'),
    ]

    for dept_id, key, name, source in metric_configs:
        dept = results.get(dept_id, {})
        growth_rate = dept.get('growth_rate', {})
        if growth_rate and key in growth_rate:
            val = growth_rate[key]
            if val is not None and val != 0:
                candidates.append({
                    'name': name,
                    'source': source,
                    'growth': round(val, 1)
                })

    if not candidates:
        return None, None

    best = max(candidates, key=lambda x: x['growth'])
    worst = min(candidates, key=lambda x: x['growth'])

    # Only show if there's meaningful difference
    if best['growth'] <= 0:
        best = max(candidates, key=lambda x: x['growth'])
    if worst['growth'] >= 0:
        worst = min(candidates, key=lambda x: x['growth'])

    return best, worst


def generate_html_report(results: Dict[str, Dict[str, Any]],
                         clinic_name: str = None,
                         report_date: str = None,
                         manager_comment: str = None,
                         action_plan_override: Dict = None) -> str:
    """Generate HTML report from processed results."""
    if clinic_name is None:
        clinic_name = '서울리멤버치과'
    if report_date is None:
        report_date = datetime.now().strftime('%Y년 %m월 %d일')

    report_title = f"{clinic_name} {datetime.now().strftime('%Y-%m')} 월간 분석 보고서"

    dept_configs = [
        ('예약 퍼널', 'reservation'),
        ('블로그', 'blog'),
        ('유튜브', 'youtube'),
        ('네이버 광고', 'ads'),
        ('디자인', 'design'),
        ('플랫폼별 세팅 현황', 'setting')
    ]

    departments = []
    for name, dept_id in dept_configs:
        result = results.get(dept_id, {})

        # 디자인: 해당 치과 데이터가 없으면 섹션 제외
        if dept_id == 'design' and clinic_name:
            design_clinics = result.get('clean_data', {}).get('clinic_names', [])
            has_clinic_data = any(clinic_name in c for c in design_clinics) if design_clinics else False
            if not has_clinic_data:
                continue  # 디자인 섹션 제외

        dept_data = prepare_department_data(name, dept_id, result)
        departments.append(dept_data)

    # Calculate executive summary data
    best_metric, worst_metric = calculate_best_worst(results)

    # Generate summary (use override if provided)
    if action_plan_override and action_plan_override.get('action_plan'):
        summary = action_plan_override
    else:
        summary = generate_summary(results)

    template = Template(HTML_TEMPLATE)
    return template.render(
        report_title=report_title,
        report_date=report_date,
        clinic_name=clinic_name,
        departments=departments,
        summary=summary,
        best_metric=best_metric,
        worst_metric=worst_metric,
        manager_comment=manager_comment or ''
    )


def get_report_filename(clinic_name: str = None) -> str:
    """Generate report filename."""
    if clinic_name is None:
        clinic_name = '서울리멤버치과'
    safe_name = clinic_name.replace(' ', '_')
    return f"{safe_name}_Monthly_Report_{datetime.now().strftime('%Y%m')}.html"
