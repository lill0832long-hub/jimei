"""图表分析 — 三Tab + KPI + 响应式ECharts（升级版）"""
from nicegui import ui
from app.components.ui_components import SectionHeader, EmptyState
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount
from app.utils.period import generate_periods, period_labels
from app.services import LedgerService, ReportService


# ── 注入图表页专用样式 ──
_CHART_CSS_INJECTED = False

def _inject_chart_css():
    global _CHART_CSS_INJECTED
    if _CHART_CSS_INJECTED:
        return
    _CHART_CSS_INJECTED = True
    ui.add_head_html('''
    <style>
    /* KPI 摘要行 */
    .chart-kpi-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
        margin-bottom: 16px;
    }
    .chart-kpi-card {
        border-radius: 12px !important;
        border-left: 4px solid var(--kpi-color, #6366f1);
        padding: 14px 18px !important;
        transition: transform 0.15s, box-shadow 0.15s;
        min-height: 80px;
    }
    .chart-kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    .chart-kpi-label { font-size: 12px; color: var(--c-text-muted); font-weight: 500; }
    .chart-kpi-value { font-size: 20px; font-weight: 700; color: var(--c-text-primary); line-height: 1.3; }
    .chart-kpi-sub { font-size: 11px; color: var(--c-text-muted); }

    /* Tab 样式 */
    .chart-tabs .q-tab { font-weight: 600; }
    .chart-tab-panels { background: transparent !important; }
    .chart-tab-panel { padding: 8px 0 !important; }

    /* 图表卡片 */
    .chart-card {
        border-radius: 12px !important;
        overflow: hidden;
        padding: 0 !important;
    }
    .chart-card__header {
        padding: 14px 20px;
        border-bottom: 1px solid var(--c-border-light);
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .chart-card__title { font-size: 15px; font-weight: 600; color: var(--c-text-primary); }
    .chart-card__subtitle { font-size: 12px; color: var(--c-text-muted); background: var(--c-bg-secondary); padding: 2px 8px; border-radius: 8px; }
    .chart-card__body { padding: 12px 16px; min-height: 300px; }

    /* 空状态 */
    .chart-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        gap: 12px;
        min-height: 260px;
    }
    .chart-empty-icon { color: var(--c-text-muted); opacity: 0.4; }
    .chart-empty-text { font-size: 14px; color: var(--c-text-muted); }
    .chart-empty-hint { font-size: 12px; color: var(--c-text-muted); opacity: 0.7; }

    /* 图表网格 */
    .chart-grid-2 {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
    }
    @media (max-width: 1024px) {
        .chart-grid-2 { grid-template-columns: 1fr; }
    }
    .chart-grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }
    @media (max-width: 1200px) {
        .chart-grid-3 { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 768px) {
        .chart-grid-3 { grid-template-columns: 1fr; }
    }

    /* 趋势指标小标签 */
    .trend-tag {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 11px;
        font-weight: 600;
        padding: 1px 6px;
        border-radius: 6px;
    }
    .trend-tag--up { color: #16a34a; background: #dcfce7; }
    .trend-tag--down { color: #dc2626; background: #fee2e2; }
    .trend-tag--flat { color: #6b7280; background: #f3f4f6; }
    </style>
    ''')


def render_charts():
    """图表分析主入口"""
    _inject_chart_css()

    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📊").classes("report-empty__icon")
                ui.label("请先创建账套").classes("report-empty__text")
        return

    year, month = state.selected_year, state.selected_month

    # ── 获取当前期间数据 ──
    try:
        cur_inc = ReportService.get_income_statement(lid, year, month)
    except Exception:
        cur_inc = {"rows": [], "total_revenue": 0, "total_expense": 0, "net_profit": 0}
    try:
        cur_bs = ReportService.get_balance_sheet(lid, year, month)
    except Exception:
        cur_bs = {"total_assets": 0, "total_liab": 0}

    # ── 生成近12个月趋势数据 ──
    periods = generate_periods(year, month, 12)
    labels = period_labels(periods)
    revenue_data, expense_data, profit_data = [], [], []
    asset_data, liability_data, equity_data = [], [], []

    for py, pm in periods:
        try:
            inc = ReportService.get_income_statement(lid, py, pm)
            revenue_data.append(round(inc.get("total_revenue", 0), 2))
            expense_data.append(round(inc.get("total_expense", 0), 2))
            profit_data.append(round(inc.get("net_profit", 0), 2))
        except Exception:
            revenue_data.append(0)
            expense_data.append(0)
            profit_data.append(0)
        try:
            bs = ReportService.get_balance_sheet(lid, py, pm)
            asset_data.append(round(bs.get("total_assets", 0), 2))
            liability_data.append(round(bs.get("total_liab", 0), 2))
            equity_data.append(round(bs.get("total_equity", 0) if isinstance(bs, dict) and bs.get("total_equity") else (bs.get("total_assets", 0) - bs.get("total_liab", 0)), 2))
        except Exception:
            asset_data.append(0)
            liability_data.append(0)
            equity_data.append(0)

    # ── 有数据的月份数 ──
    nonzero_months = sum(1 for r, e in zip(revenue_data, expense_data) if r != 0 or e != 0)

    # ── KPI 摘要 ──
    _render_kpi_summary(cur_inc, cur_bs, revenue_data, expense_data, profit_data, asset_data)

    # ── Tab 切换 ──
    with ui.tabs().classes("w-full chart-tabs") as chart_tabs:
        ui.tab("trend", label="趋势分析", icon="trending_up").props("no-caps")
        ui.tab("structure", label="结构分析", icon="pie_chart").props("no-caps")
        ui.tab("cashflow", label="现金流", icon="waterfall_chart").props("no-caps")

    with ui.tab_panels(chart_tabs, value="trend").classes("w-full chart-tab-panels"):
        # ── 趋势分析 ──
        with ui.tab_panel("trend").classes("chart-tab-panel"):
            with ui.element("div").classes("chart-grid-2"):
                _render_revenue_trend(labels, revenue_data, expense_data, profit_data)
                _render_asset_trend(labels, asset_data, liability_data, equity_data)
            # 利润率趋势
            with ui.element("div").classes("mt-4"):
                _render_profit_margin_trend(labels, revenue_data, profit_data)

        # ── 结构分析 ──
        with ui.tab_panel("structure").classes("chart-tab-panel"):
            with ui.element("div").classes("chart-grid-2"):
                _render_pie_chart("收入构成", "account_balance", lid, year, month,
                                  ("revenue_item", "revenue_header", "rev_total"), "#22c55e")
                _render_pie_chart("费用构成", "payments", lid, year, month,
                                  ("expense_header", "expense_item"), "#ef4444")
            # 资产结构
            with ui.element("div").classes("mt-4"):
                _render_asset_structure(lid, year, month)

        # ── 现金流 ──
        with ui.tab_panel("cashflow").classes("chart-tab-panel"):
            _render_cashflow_chart(lid, labels, revenue_data, expense_data)


# ──────────────────────────────────────
# KPI 摘要卡片
# ──────────────────────────────────────

def _render_kpi_summary(cur_inc, cur_bs, rev_data, exp_data, prof_data, asset_data):
    """KPI 摘要 — 当月 + 趋势箭头"""
    cur_rev = cur_inc.get("total_revenue", 0) if isinstance(cur_inc, dict) else 0
    cur_exp = cur_inc.get("total_expense", 0) if isinstance(cur_inc, dict) else 0
    cur_profit = cur_inc.get("net_profit", 0) if isinstance(cur_inc, dict) else 0
    cur_asset = cur_bs.get("total_assets", 0) if isinstance(cur_bs, dict) else 0
    cur_liab = cur_bs.get("total_liab", 0) if isinstance(cur_bs, dict) else 0

    # 计算环比（上月 vs 本月）
    prev_rev = rev_data[-2] if len(rev_data) >= 2 else 0
    prev_exp = exp_data[-2] if len(exp_data) >= 2 else 0
    prev_prof = prof_data[-2] if len(prof_data) >= 2 else 0
    prev_asset = asset_data[-2] if len(asset_data) >= 2 else 0

    def _trend_tag(cur, prev):
        if prev == 0 and cur == 0:
            return ""
        if prev == 0:
            return '<span class="trend-tag trend-tag--up">↑ 新增</span>'
        pct = ((cur - prev) / abs(prev)) * 100
        if abs(pct) < 1:
            return '<span class="trend-tag trend-tag--flat">→ 持平</span>'
        elif pct > 0:
            return f'<span class="trend-tag trend-tag--up">↑ {pct:.1f}%</span>'
        else:
            return f'<span class="trend-tag trend-tag--down">↓ {abs(pct):.1f}%</span>'

    kpis = [
        ("当月收入", cur_rev, "trending_up", "#22c55e", _trend_tag(cur_rev, prev_rev)),
        ("当月费用", cur_exp, "trending_down", "#ef4444", _trend_tag(cur_exp, prev_exp)),
        ("当月净利润", cur_profit, "account_balance", "#6366f1", _trend_tag(cur_profit, prev_prof)),
        ("总资产", cur_asset, "analytics", "#8b5cf6", _trend_tag(cur_asset, prev_asset)),
        ("资产负债率", (cur_liab / cur_asset * 100) if cur_asset else 0, "balance", "#f59e0b", ""),
    ]

    with ui.element("div").classes("chart-kpi-row"):
        for label, value, icon, color, trend_html in kpis:
            with ui.card().classes("chart-kpi-card").style(f"--kpi-color: {color}"):
                with ui.row().classes("items-center justify-between"):
                    with ui.column().classes("gap-1"):
                        ui.label(label).classes("chart-kpi-label")
                        if label == "资产负债率":
                            ui.label(f"{value:.1f}%").classes("chart-kpi-value")
                        else:
                            ui.label(format_amount(value, show_currency=True)).classes("chart-kpi-value")
                    ui.icon(icon, size="28px").style(f"color: {color}; opacity: 0.6;")
                if trend_html:
                    ui.html(trend_html)


# ──────────────────────────────────────
# 趋势分析
# ──────────────────────────────────────

def _render_revenue_trend(labels, revenue_data, expense_data, profit_data):
    """收入/费用/利润趋势折线图"""
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("trending_up").style("color: #6366f1;")
            ui.label("收入 · 费用 · 利润趋势").classes("chart-card__title")
            ui.space()
            ui.label("近12月").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            has_data = any(v != 0 for v in revenue_data + expense_data + profit_data)
            if not has_data:
                _render_empty_chart("暂无收入费用数据", "请先录入记账凭证")
                return
            ui.echart({
                "tooltip": {
                    "trigger": "axis",
                    "backgroundColor": "rgba(255,255,255,0.95)",
                    "borderColor": "#e5e7eb",
                    "textStyle": {"fontSize": 12, "color": "#374151"},
                    "axisPointer": {"type": "cross", "crossStyle": {"color": "#9ca3af"}},
                },
                "legend": {
                    "data": ["收入", "费用", "净利润"],
                    "top": 0, "textStyle": {"fontSize": 11},
                    "itemGap": 16,
                },
                "grid": {"left": "3%", "right": "4%", "bottom": "12%", "top": "14%", "containLabel": True},
                "dataZoom": [
                    {"type": "inside", "start": 0, "end": 100},
                    {"type": "slider", "start": 0, "end": 100, "height": 18, "bottom": 4,
                     "borderColor": "#e5e7eb", "fillerColor": "rgba(99,102,241,0.1)",
                     "handleStyle": {"color": "#6366f1"}},
                ],
                "xAxis": {
                    "type": "category", "data": labels,
                    "axisLabel": {"rotate": 45, "fontSize": 10, "color": "#6b7280"},
                    "axisLine": {"lineStyle": {"color": "#e5e7eb"}},
                },
                "yAxis": {
                    "type": "value",
                    "axisLabel": {"fontSize": 10, "color": "#6b7280",
                                  "formatter": "function(v){return v>=10000?(v/10000)+'万':v}"},
                    "splitLine": {"lineStyle": {"color": "#f3f4f6", "type": "dashed"}},
                },
                "series": [
                    {
                        "name": "收入", "type": "bar", "data": revenue_data,
                        "itemStyle": {"color": "#22c55e", "borderRadius": [4, 4, 0, 0]},
                        "barMaxWidth": 24,
                    },
                    {
                        "name": "费用", "type": "bar", "data": expense_data,
                        "itemStyle": {"color": "#ef4444", "borderRadius": [4, 4, 0, 0]},
                        "barMaxWidth": 24,
                    },
                    {
                        "name": "净利润", "type": "line", "data": profit_data,
                        "smooth": True, "symbol": "circle", "symbolSize": 6,
                        "lineStyle": {"width": 2.5, "color": "#6366f1"},
                        "itemStyle": {"color": "#6366f1"},
                        "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                                "colorStops": [{"offset": 0, "color": "rgba(99,102,241,0.15)"},
                                                               {"offset": 1, "color": "rgba(99,102,241,0)"}]}},
                    },
                ],
            }).classes("w-full h-80")


def _render_asset_trend(labels, asset_data, liability_data, equity_data):
    """资产负债趋势图"""
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("account_balance").style("color: #8b5cf6;")
            ui.label("资产 · 负债 · 权益趋势").classes("chart-card__title")
            ui.space()
            ui.label("近12月").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            has_data = any(v != 0 for v in asset_data + liability_data)
            if not has_data:
                _render_empty_chart("暂无资产负债数据", "请先录入记账凭证")
                return
            ui.echart({
                "tooltip": {
                    "trigger": "axis",
                    "backgroundColor": "rgba(255,255,255,0.95)",
                    "borderColor": "#e5e7eb",
                    "textStyle": {"fontSize": 12, "color": "#374151"},
                },
                "legend": {
                    "data": ["资产", "负债", "权益"],
                    "top": 0, "textStyle": {"fontSize": 11},
                },
                "grid": {"left": "3%", "right": "4%", "bottom": "12%", "top": "14%", "containLabel": True},
                "dataZoom": [
                    {"type": "inside", "start": 0, "end": 100},
                    {"type": "slider", "start": 0, "end": 100, "height": 18, "bottom": 4,
                     "borderColor": "#e5e7eb", "fillerColor": "rgba(139,92,246,0.1)",
                     "handleStyle": {"color": "#8b5cf6"}},
                ],
                "xAxis": {
                    "type": "category", "data": labels,
                    "axisLabel": {"rotate": 45, "fontSize": 10, "color": "#6b7280"},
                    "axisLine": {"lineStyle": {"color": "#e5e7eb"}},
                },
                "yAxis": {
                    "type": "value",
                    "axisLabel": {"fontSize": 10, "color": "#6b7280",
                                  "formatter": "function(v){return v>=10000?(v/10000)+'万':v}"},
                    "splitLine": {"lineStyle": {"color": "#f3f4f6", "type": "dashed"}},
                },
                "series": [
                    {"name": "资产", "type": "line", "data": asset_data, "smooth": True,
                     "symbol": "circle", "symbolSize": 6,
                     "lineStyle": {"width": 2.5, "color": "#8b5cf6"},
                     "itemStyle": {"color": "#8b5cf6"},
                     "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                             "colorStops": [{"offset": 0, "color": "rgba(139,92,246,0.12)"},
                                                            {"offset": 1, "color": "rgba(139,92,246,0)"}]}}},
                    {"name": "负债", "type": "line", "data": liability_data, "smooth": True,
                     "symbol": "circle", "symbolSize": 6,
                     "lineStyle": {"width": 2, "color": "#f59e0b", "type": "dashed"},
                     "itemStyle": {"color": "#f59e0b"}},
                    {"name": "权益", "type": "line", "data": equity_data, "smooth": True,
                     "symbol": "circle", "symbolSize": 6,
                     "lineStyle": {"width": 2, "color": "#22c55e"},
                     "itemStyle": {"color": "#22c55e"},
                     "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                             "colorStops": [{"offset": 0, "color": "rgba(34,197,94,0.08)"},
                                                            {"offset": 1, "color": "rgba(34,197,94,0)"}]}}},
                ],
            }).classes("w-full h-80")


def _render_profit_margin_trend(labels, revenue_data, profit_data):
    """利润率趋势"""
    margins = []
    for r, p in zip(revenue_data, profit_data):
        if r and r > 0:
            margins.append(round(p / r * 100, 1))
        else:
            margins.append(0)

    has_data = any(m != 0 for m in margins)
    if not has_data:
        return

    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("percent").style("color: #0ea5e9;")
            ui.label("利润率趋势").classes("chart-card__title")
            ui.space()
            ui.label("净利润率 %").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            ui.echart({
                "tooltip": {
                    "trigger": "axis",
                    "formatter": "function(p){var d=p[0];return d.name+'<br/>利润率: '+d.value+'%'}",
                },
                "grid": {"left": "3%", "right": "4%", "bottom": "12%", "top": "8%", "containLabel": True},
                "xAxis": {
                    "type": "category", "data": labels,
                    "axisLabel": {"rotate": 45, "fontSize": 10, "color": "#6b7280"},
                },
                "yAxis": {
                    "type": "value",
                    "axisLabel": {"fontSize": 10, "color": "#6b7280", "formatter": "{value}%"},
                    "splitLine": {"lineStyle": {"color": "#f3f4f6", "type": "dashed"}},
                },
                "series": [{
                    "type": "line", "data": margins, "smooth": True,
                    "symbol": "circle", "symbolSize": 8,
                    "lineStyle": {"width": 3, "color": "#0ea5e9"},
                    "itemStyle": {"color": "#0ea5e9", "borderWidth": 2, "borderColor": "#fff"},
                    "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                            "colorStops": [{"offset": 0, "color": "rgba(14,165,233,0.2)"},
                                                           {"offset": 1, "color": "rgba(14,165,233,0)"}]}},
                    "markLine": {
                        "silent": True,
                        "data": [{"yAxis": 0, "lineStyle": {"color": "#ef4444", "type": "dashed", "width": 1},
                                  "label": {"formatter": "盈亏线", "fontSize": 10, "color": "#ef4444"}}],
                    },
                }],
            }).classes("w-full h-56")


# ──────────────────────────────────────
# 结构分析
# ──────────────────────────────────────

def _render_pie_chart(title, icon_name, lid, year, month, type_filter, color):
    """饼图：收入/费用结构"""
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon(icon_name).style(f"color: {color};")
            ui.label(title).classes("chart-card__title")
            ui.space()
            ui.label(f"{year}-{month:02d}").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            try:
                inc = ReportService.get_income_statement(lid, year, month)
                pie_data = [{"value": round(abs(float(r.get("ytd") or 0)), 2), "name": r["name"]}
                            for r in inc.get("rows", [])
                            if r.get("type") in type_filter and abs(float(r.get("ytd") or 0)) > 0.01]
                if pie_data:
                    ui.echart({
                        "tooltip": {"trigger": "item", "formatter": "{b}: ¥{c} ({d}%)",
                                    "backgroundColor": "rgba(255,255,255,0.95)"},
                        "legend": {"orient": "vertical", "right": "5%", "top": "center",
                                   "textStyle": {"fontSize": 11}},
                        "series": [{
                            "type": "pie", "radius": ["30%", "65%"], "center": ["40%", "50%"],
                            "data": pie_data,
                            "label": {"formatter": "{b}\n{d}%", "fontSize": 11},
                            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0,
                                                       "shadowColor": "rgba(0,0,0,0.3)"}},
                            "itemStyle": {"borderRadius": 6, "borderColor": "#fff", "borderWidth": 2},
                        }],
                    }).classes("w-full h-72")
                else:
                    _render_empty_chart(f"暂无{title}数据", "请先录入记账凭证")
            except Exception as e:
                _render_empty_chart("加载失败", str(e))


def _render_asset_structure(lid, year, month):
    """资产结构柱状图（按科目类别）"""
    try:
        balances = ReportService.get_account_balances(lid, year, month)
        if not balances:
            return

        # 按类别汇总
        cat_map = {}
        for b in balances:
            cat = b.get("category", "其他")
            closing = abs(float(b.get("closing_balance", 0) or 0))
            if closing > 0.01:
                cat_map[cat] = cat_map.get(cat, 0) + closing

        if not cat_map:
            return

        sorted_cats = sorted(cat_map.items(), key=lambda x: -x[1])
        cat_names = [c[0] for c in sorted_cats]
        cat_values = [round(c[1], 2) for c in sorted_cats]
        cat_colors = {"资产": "#8b5cf6", "负债": "#f59e0b", "权益": "#22c55e",
                      "收入": "#0ea5e9", "费用": "#ef4444"}

        with ui.card().classes("chart-card"):
            with ui.row().classes("chart-card__header"):
                ui.icon("donut_large").style("color: #f59e0b;")
                ui.label("科目余额分布").classes("chart-card__title")
                ui.space()
                ui.label(f"{year}-{month:02d}").classes("chart-card__subtitle")
            with ui.element("div").classes("chart-card__body"):
                ui.echart({
                    "tooltip": {"trigger": "axis",
                                "formatter": "function(p){var d=p[0];return d.name+'<br/>¥'+d.value.toLocaleString()}"},
                    "grid": {"left": "3%", "right": "4%", "bottom": "3%", "top": "8%", "containLabel": True},
                    "xAxis": {
                        "type": "category", "data": cat_names,
                        "axisLabel": {"fontSize": 12, "fontWeight": 600, "color": "#374151"},
                        "axisLine": {"lineStyle": {"color": "#e5e7eb"}},
                    },
                    "yAxis": {
                        "type": "value",
                        "axisLabel": {"fontSize": 10, "color": "#6b7280"},
                        "splitLine": {"lineStyle": {"color": "#f3f4f6", "type": "dashed"}},
                    },
                    "series": [{
                        "type": "bar", "data": [
                            {"value": v, "itemStyle": {"color": cat_colors.get(n, "#6366f1"),
                                                       "borderRadius": [6, 6, 0, 0]}}
                            for n, v in zip(cat_names, cat_values)
                        ],
                        "barMaxWidth": 60,
                        "label": {"show": True, "position": "top", "fontSize": 11, "fontWeight": 600,
                                  "formatter": "function(p){return '¥'+p.value.toLocaleString()}"},
                    }],
                }).classes("w-full h-56")
    except Exception:
        pass


# ──────────────────────────────────────
# 现金流分析
# ──────────────────────────────────────

def _render_cashflow_chart(lid, labels=None, revenue_data=None, expense_data=None):
    """现金流柱状图 — 使用传入的12月数据或重新获取"""
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("waterfall_chart").style("color: #0ea5e9;")
            ui.label("现金流分析").classes("chart-card__title")
            ui.space()
            ui.label(f"{state.selected_year}年").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            try:
                # 使用传入数据或重新获取
                if labels and revenue_data and expense_data:
                    cf_labels = labels
                    cf_rev = revenue_data
                    cf_exp = expense_data
                else:
                    cf_labels, cf_rev, cf_exp = [], [], []
                    for m in range(1, 13):
                        cf_labels.append(f"{m}月")
                        try:
                            inc = ReportService.get_income_statement(lid, state.selected_year, m)
                            cf_rev.append(round(inc.get("total_revenue", 0), 2))
                            cf_exp.append(round(inc.get("total_expense", 0), 2))
                        except Exception:
                            cf_rev.append(0)
                            cf_exp.append(0)

                has_data = any(r != 0 or e != 0 for r, e in zip(cf_rev, cf_exp))
                if not has_data:
                    _render_empty_chart("暂无现金流数据", "请先录入记账凭证")
                    return

                # 净现金流
                net_cf = [round(r - e, 2) for r, e in zip(cf_rev, cf_exp)]

                ui.echart({
                    "tooltip": {
                        "trigger": "axis",
                        "backgroundColor": "rgba(255,255,255,0.95)",
                        "borderColor": "#e5e7eb",
                        "textStyle": {"fontSize": 12, "color": "#374151"},
                    },
                    "legend": {"data": ["收入", "支出", "净现金流"], "top": 0, "textStyle": {"fontSize": 11}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "3%", "top": "14%", "containLabel": True},
                    "xAxis": {
                        "type": "category", "data": cf_labels,
                        "axisLabel": {"fontSize": 10, "color": "#6b7280"},
                        "axisLine": {"lineStyle": {"color": "#e5e7eb"}},
                    },
                    "yAxis": {
                        "type": "value",
                        "axisLabel": {"fontSize": 10, "color": "#6b7280"},
                        "splitLine": {"lineStyle": {"color": "#f3f4f6", "type": "dashed"}},
                    },
                    "series": [
                        {"name": "收入", "type": "bar", "stack": "cf", "data": cf_rev,
                         "itemStyle": {"color": "#22c55e", "borderRadius": [4, 4, 0, 0]},
                         "barMaxWidth": 28},
                        {"name": "支出", "type": "bar", "stack": "cf", "data": [-e for e in cf_exp],
                         "itemStyle": {"color": "#ef4444", "borderRadius": [4, 4, 0, 0]},
                         "barMaxWidth": 28},
                        {"name": "净现金流", "type": "line", "data": net_cf,
                         "smooth": True, "symbol": "circle", "symbolSize": 6,
                         "lineStyle": {"width": 2.5, "color": "#6366f1"},
                         "itemStyle": {"color": "#6366f1"}},
                    ],
                }).classes("w-full h-80")
            except Exception as e:
                _render_empty_chart("加载失败", str(e))


# ──────────────────────────────────────
# 工具函数
# ──────────────────────────────────────

def _render_empty_chart(text, hint=""):
    """统一空状态"""
    with ui.column().classes("chart-empty"):
        ui.icon("bar_chart", size="48px").classes("chart-empty-icon")
        ui.label(text).classes("chart-empty-text")
        if hint:
            ui.label(hint).classes("chart-empty-hint")
