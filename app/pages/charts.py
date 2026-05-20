"""图表分析"""
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
    revenue_data, expense_data, profit_data, asset_data, liability_data = [], [], [], [], []

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

    # ── 收入/费用/利润趋势图 ──
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("trending_up").style("color:var(--c-primary)")
            ui.label("收入/费用/利润趋势").classes("chart-card__title")
            ui.label("近12个月").classes("text-xs").style("color:var(--c-text-muted)")
        with ui.element("div").classes("chart-card__body"):
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["收入", "费用", "净利润"], "top": 0},
                "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45}},
                "yAxis": {"type": "value"},
                "series": [
                    {"name": "收入", "type": "bar", "data": revenue_data,
                     "itemStyle": {"color": "#22c55e", "borderRadius": [4, 4, 0, 0]}},
                    {"name": "费用", "type": "bar", "data": expense_data,
                     "itemStyle": {"color": "#ef4444", "borderRadius": [4, 4, 0, 0]}},
                    {"name": "净利润", "type": "line", "data": profit_data,
                     "itemStyle": {"color": "#494fdf"}, "lineStyle": {"width": 3},
                     "symbol": "circle", "symbolSize": 6},
                ],
            }).classes("w-full h-80")

    # ── 资产负债趋势图 ──
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("account_balance").style("color:var(--c-success)")
            ui.label("资产负债趋势").classes("chart-card__title")
            ui.label("近12个月").classes("text-xs").style("color:var(--c-text-muted)")
        with ui.element("div").classes("chart-card__body"):
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["资产", "负债"], "top": 0},
                "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45}},
                "yAxis": {"type": "value"},
                "series": [
                    {"name": "资产", "type": "line", "data": asset_data,
                     "itemStyle": {"color": "#22c55e"}, "areaStyle": {"opacity": 0.08, "color": "#22c55e"},
                     "lineStyle": {"width": 2}},
                    {"name": "负债", "type": "line", "data": liability_data,
                     "itemStyle": {"color": "#ef4444"}, "areaStyle": {"opacity": 0.08, "color": "#ef4444"},
                     "lineStyle": {"width": 2}},
                ],
            }).classes("w-full h-80")

    # ── 收入/费用结构饼图 ──
    with ui.row().classes("w-full gap-3"):
        _render_pie_chart("收入结构", "pie_chart", "revenue", lid,
                          state.selected_year, state.selected_month,
                          ("revenue_item", "revenue_header", "rev_total"),
                          "#22c55e")
        _render_pie_chart("费用结构", "donut_large", "expense", lid,
                          state.selected_year, state.selected_month,
                          ("expense_header", "expense_item"),
                          "#ef4444")

    # ── 现金流瀑布图 ──
    with ui.card().classes("chart-card"):
        with ui.row().classes("chart-card__header"):
            ui.icon("waterfall_chart").style("color:var(--c-primary)")
            ui.label("现金流分析").classes("chart-card__title")
            ui.label(f"{state.selected_year}年").classes("text-xs").style("color:var(--c-text-muted)")
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
                    "legend": {"data": ["收入", "支出"], "top": 0},
                    "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                    "xAxis": {"type": "category",
                              "data": [md["month"] for md in months_data],
                              "axisLabel": {"rotate": 0}},
                    "yAxis": {"type": "value"},
                    "series": [
                        {"name": "收入", "type": "bar", "stack": "cf",
                         "data": [d["revenue"] for d in months_data],
                         "itemStyle": {"color": "#22c55e", "borderRadius": [4, 4, 0, 0]}},
                        {"name": "支出", "type": "bar", "stack": "cf",
                         "data": [-d["expense"] for d in months_data],
                         "itemStyle": {"color": "#ef4444", "borderRadius": [4, 4, 0, 0]}},
                    ]
                }).classes("w-full h-80")
            except Exception as e:
                with ui.column().classes("report-empty"):
                    ui.label("⚠️").classes("report-empty__icon")
                    ui.label(f"图表加载失败: {e}").classes("report-empty__text").style("color:var(--c-danger)")


def _render_pie_chart(title, icon_name, chart_type, lid, year, month, type_filter, color):
    """渲染饼图卡片"""
    with ui.card().classes("w-1/2"):
        with ui.row().classes("chart-card__header"):
            ui.icon(icon_name).style(f"color:{color}")
            ui.label(title).classes("chart-card__title")
            ui.label(f"{year}-{month:02d}").classes("text-xs").style("color:var(--c-text-muted)")
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
                    with ui.column().classes("report-empty py-8"):
                        ui.label("📋").classes("report-empty__icon")
                        ui.label(f"暂无{title.replace('结构', '')}数据").classes("report-empty__text")
            except Exception as e:
                with ui.column().classes("report-empty py-8"):
                    ui.label("⚠️").classes("report-empty__icon")
                    ui.label("加载失败").classes("report-empty__text").style("color:var(--c-danger)")
