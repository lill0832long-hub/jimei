"""图表分析 — Tab分类 + KPI摘要布局"""
from nicegui import ui
from app.components.ui_components import SectionHeader, EmptyState
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount
from app.utils.period import generate_periods, period_labels
from app.services import LedgerService, ReportService


def render_charts():
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

    # ── 生成近12个月数据 ──
    periods = generate_periods(state.selected_year, state.selected_month, 12)
    labels = period_labels(periods)
    revenue_data, expense_data, profit_data = [], [], []
    asset_data, liability_data = [], []

    for py, pm in periods:
        try:
            inc = ReportService.get_income_statement(lid, py, pm)
            revenue_data.append(round(inc.get("total_revenue", 0), 2))
            expense_data.append(round(sum((r.get("ytd") or 0) for r in inc.get("rows", [])
                                          if r.get("type") in ("expense_item", "subtotal")), 2))
            profit_data.append(round(inc.get("net_profit", 0), 2))
        except Exception:
            revenue_data.append(0)
            expense_data.append(0)
            profit_data.append(0)
        try:
            bs = ReportService.get_balance_sheet(lid, py, pm)
            asset_data.append(round(bs.get("total_assets", 0), 2))
            liability_data.append(round(bs.get("total_liab", 0), 2))
        except Exception:
            asset_data.append(0)
            liability_data.append(0)

    # ── KPI 摘要卡片（始终可见） ──
    _render_kpi_summary(revenue_data, expense_data, profit_data, asset_data, liability_data)

    # ── Tab 分类切换 ──
    with ui.tabs().classes("w-full chart-tabs") as chart_tabs:
        ui.tab("trend", label="趋势分析", icon="trending_up").props("no-caps")
        ui.tab("structure", label="结构分析", icon="pie_chart").props("no-caps")
        ui.tab("cashflow", label="现金流", icon="waterfall_chart").props("no-caps")

    with ui.tab_panels(chart_tabs, value="trend").classes("w-full chart-tab-panels"):
        # 趋势分析
        with ui.tab_panel("trend").classes("chart-tab-panel"):
            with ui.grid().classes("w-full gap-4").style("grid-template-columns: 1fr 1fr;"):
                _render_revenue_trend(labels, revenue_data, expense_data, profit_data)
                _render_asset_trend(labels, asset_data, liability_data)

        # 结构分析
        with ui.tab_panel("structure").classes("chart-tab-panel"):
            with ui.grid().classes("w-full gap-4").style("grid-template-columns: 1fr 1fr;"):
                _render_pie_chart("收入结构", "pie_chart", lid,
                                  state.selected_year, state.selected_month,
                                  ("revenue_item", "revenue_header", "rev_total"), "#22c55e")
                _render_pie_chart("费用结构", "donut_large", lid,
                                  state.selected_year, state.selected_month,
                                  ("expense_header", "expense_item"), "#ef4444")

        # 现金流
        with ui.tab_panel("cashflow").classes("chart-tab-panel"):
            _render_cashflow_chart(lid)


def _render_kpi_summary(rev, exp, prof, asset, liab):
    """KPI 摘要卡片 — 一行展示关键指标"""
    total_rev = sum(rev)
    total_exp = sum(exp)
    net_prof = sum(prof)
    latest_asset = asset[-1] if asset else 0
    latest_liab = liab[-1] if liab else 0

    kpis = [
        ("总收入", total_rev, "trending_up", "green", "近12月"),
        ("总费用", total_exp, "trending_down", "red", "近12月"),
        ("净利润", net_prof, "account_balance", "blue", "近12月"),
        ("总资产", latest_asset, "analytics", "purple", f"{state.selected_month}月"),
    ]

    with ui.row().classes("w-full gap-3 mb-3"):
        for label, value, icon, color, sub in kpis:
            with ui.card().classes("kpi-card-mini").props(f"data-color={color}"):
                with ui.row().classes("items-center gap-2 px-3 py-2"):
                    ui.icon(icon, size="22px").classes(f"kpi-icon-{color}")
                    with ui.column().classes("gap-0"):
                        ui.label(label).classes("kpi-mini-label")
                        ui.label(format_amount(value, show_currency=True)).classes("kpi-mini-value")
                        ui.label(sub).classes("kpi-mini-sub")


def _render_revenue_trend(labels, revenue_data, expense_data, profit_data):
    """收入/费用/利润趋势图"""
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("trending_up").classes("chart-header-icon-primary")
            ui.label("收入/费用/利润趋势").classes("chart-card__title")
            ui.space()
            ui.label("近12个月").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["收入", "费用", "净利润"], "top": 0, "textStyle": {"fontSize": 11}},
                "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45, "fontSize": 10}},
                "yAxis": {"type": "value", "axisLabel": {"fontSize": 10}},
                "series": [
                    {"name": "收入", "type": "bar", "data": revenue_data,
                     "itemStyle": {"color": "#22c55e", "borderRadius": [4, 4, 0, 0]}},
                    {"name": "费用", "type": "bar", "data": expense_data,
                     "itemStyle": {"color": "#ef4444", "borderRadius": [4, 4, 0, 0]}},
                    {"name": "净利润", "type": "line", "data": profit_data,
                     "itemStyle": {"color": "#494fdf"}, "lineStyle": {"width": 3},
                     "symbol": "circle", "symbolSize": 6},
                ],
            }).classes("w-full h-72")


def _render_asset_trend(labels, asset_data, liability_data):
    """资产负债趋势图"""
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("account_balance").classes("chart-header-icon-success")
            ui.label("资产负债趋势").classes("chart-card__title")
            ui.space()
            ui.label("近12个月").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["资产", "负债"], "top": 0, "textStyle": {"fontSize": 11}},
                "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45, "fontSize": 10}},
                "yAxis": {"type": "value", "axisLabel": {"fontSize": 10}},
                "series": [
                    {"name": "资产", "type": "line", "data": asset_data,
                     "itemStyle": {"color": "#22c55e"}, "areaStyle": {"opacity": 0.08, "color": "#22c55e"},
                     "lineStyle": {"width": 2}},
                    {"name": "负债", "type": "line", "data": liability_data,
                     "itemStyle": {"color": "#ef4444"}, "areaStyle": {"opacity": 0.08, "color": "#ef4444"},
                     "lineStyle": {"width": 2}},
                ],
            }).classes("w-full h-72")


def _render_pie_chart(title, icon_name, lid, year, month, type_filter, color):
    """渲染饼图卡片"""
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon(icon_name).classes(f"chart-header-icon-{color}")
            ui.label(title).classes("chart-card__title")
            ui.space()
            ui.label(f"{year}-{month:02d}").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            try:
                inc = ReportService.get_income_statement(lid, year, month)
                pie_data = [{"value": round(r.get("ytd") or 0, 2), "name": r["name"]}
                            for r in inc.get("rows", []) if r.get("type") in type_filter and (r.get("ytd") or 0) > 0]
                if pie_data:
                    ui.echart({
                        "tooltip": {"trigger": "item", "formatter": "{b}: ¥{c} ({d}%)"},
                        "series": [{
                            "type": "pie", "radius": ["35%", "70%"],
                            "data": pie_data,
                            "label": {"formatter": "{b}\n{d}%", "fontSize": 11},
                            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0,
                                                        "shadowColor": "rgba(0,0,0,0.5)"}},
                        }],
                    }).classes("w-full h-64")
                else:
                    with ui.column().classes("chart-empty"):
                        ui.icon("pie_chart", size="40px").classes("chart-empty-icon")
                        ui.label(f"暂无{title.replace(chr(26500), '')}数据").classes("chart-empty-text")
            except Exception as e:
                with ui.column().classes("chart-empty"):
                    ui.icon("error_outline", size="40px").classes("chart-empty-icon")
                    ui.label("加载失败").classes("chart-empty-text")


def _render_cashflow_chart(lid):
    """现金流分析"""
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("waterfall_chart").classes("chart-header-icon-primary")
            ui.label("现金流分析").classes("chart-card__title")
            ui.space()
            ui.label(f"{state.selected_year}年").classes("chart-card__subtitle")
        with ui.element("div").classes("chart-card__body"):
            try:
                months_data = []
                for m in range(1, 13):
                    inc = ReportService.get_income_statement(lid, state.selected_year, m)
                    rev = inc.get("total_revenue", 0)
                    exp = sum((r.get("ytd") or 0) for r in inc.get("rows", [])
                              if r.get("type") in ("expense_item", "subtotal"))
                    months_data.append({"month": f"{m}月", "revenue": round(rev, 2), "expense": round(exp, 2)})

                ui.echart({
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["收入", "支出"], "top": 0, "textStyle": {"fontSize": 11}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                    "xAxis": {"type": "category",
                              "data": [md["month"] for md in months_data],
                              "axisLabel": {"rotate": 0, "fontSize": 10}},
                    "yAxis": {"type": "value", "axisLabel": {"fontSize": 10}},
                    "series": [
                        {"name": "收入", "type": "bar", "stack": "cf",
                         "data": [d["revenue"] for d in months_data],
                         "itemStyle": {"color": "#22c55e", "borderRadius": [4, 4, 0, 0]}},
                        {"name": "支出", "type": "bar", "stack": "cf",
                         "data": [-d["expense"] for d in months_data],
                         "itemStyle": {"color": "#ef4444", "borderRadius": [4, 4, 0, 0]}},
                    ]
                }).classes("w-full h-72")
            except Exception as e:
                with ui.column().classes("chart-empty"):
                    ui.icon("error_outline", size="40px").classes("chart-empty-icon")
                    ui.label(f"图表加载失败: {e}").classes("chart-empty-text")
