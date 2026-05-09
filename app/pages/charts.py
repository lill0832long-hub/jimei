"""图表分析"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast
from database_v3 import (
    get_ledgers, get_income_statement, get_balance_sheet,
)

def render_charts():
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return
    lid = state.selected_ledger_id

    # 生成近12个月数据
    periods = []
    y, m = state.selected_year, state.selected_month
    for i in range(11, -1, -1):
        pm = m - i
        py = y
        while pm <= 0:
            pm += 12
            py -= 1
        periods.append((py, pm))

    labels = [f"{p[0]}-{p[1]:02d}" for p in periods]
    revenue_data = []
    expense_data = []
    profit_data = []
    asset_data = []
    liability_data = []

    for py, pm in periods:
        inc = get_income_statement(lid, py, pm)
        revenue_data.append(round(inc["total_revenue"], 2))
        expense_data.append(round(sum(r["ytd"] for r in inc["rows"] if r["type"] in ("expense_header","expense_item","subtotal")), 2))
        profit_data.append(round(inc["net_profit"], 2))
        bs = get_balance_sheet(lid, py, pm)
        asset_data.append(round(bs["total_assets"], 2))
        liability_data.append(round(bs["total_liab"], 2))

    # 收入/费用/利润趋势图
    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2 px-3"):
            ui.label("📈 收入/费用/利润趋势（近12个月）").classes("text-base font-bold")
        with ui.card_section():
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["收入", "费用", "净利润"], "top": 0},
                "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45}},
                "yAxis": {"type": "value"},
                "series": [
                    {"name": "收入", "type": "bar", "data": revenue_data, "itemStyle": {"color": "#4caf50"}},
                    {"name": "费用", "type": "bar", "data": expense_data, "itemStyle": {"color": "#f44336"}},
                    {"name": "净利润", "type": "line", "data": profit_data, "itemStyle": {"color": "#2196f3"},
                     "lineStyle": {"width": 3}, "symbol": "circle", "symbolSize": 6},
                ],
            }).classes("w-full h-80")

    # 资产负债趋势图
    with ui.card().classes("w-full mt-3"):
        with ui.card_section().classes("py-2 px-3"):
            ui.label("📗 资产负债趋势（近12个月）").classes("text-base font-bold")
        with ui.card_section():
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["资产", "负债"], "top": 0},
                "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 45}},
                "yAxis": {"type": "value"},
                "series": [
                    {"name": "资产", "type": "line", "data": asset_data, "itemStyle": {"color": "#4caf50"},
                     "areaStyle": {"opacity": 0.1}, "lineStyle": {"width": 2}},
                    {"name": "负债", "type": "line", "data": liability_data, "itemStyle": {"color": "#f44336"},
                     "areaStyle": {"opacity": 0.1}, "lineStyle": {"width": 2}},
                ],
            }).classes("w-full h-80")

    # 收入结构饼图（当月）
    with ui.row().classes("w-full mt-3 gap-3"):
        with ui.card().classes("w-1/2"):
            with ui.card_section().classes("py-2 px-3"):
                ui.label(f"🥧 收入结构 — {state.selected_year}-{state.selected_month:02d}").classes("text-base font-bold")
            with ui.card_section():
                inc = get_income_statement(lid, state.selected_year, state.selected_month)
                pie_data = [{"value": round(r.get("ytd") or 0, 2), "name": r["name"]}
                            for r in inc["rows"] if r["type"] in ("revenue_item","revenue_header","rev_total") and (r.get("ytd") or 0) > 0]
                if pie_data:
                    ui.echart({
                        "tooltip": {"trigger": "item", "formatter": "{b}: ¥{c} ({d}%)"},
                        "series": [{
                            "type": "pie", "radius": ["30%", "70%"],
                            "data": pie_data,
                            "label": {"formatter": "{b}\n{d}%"},
                            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.5)"}},
                        }],
                    }).classes("w-full h-64")
                else:
                    ui.label("暂无收入数据").classes("text-sm").style("color:var(--c-text-muted)").classes("p-4")

        with ui.card().classes("w-1/2"):
            with ui.card_section().classes("py-2 px-3"):
                ui.label(f"🍩 费用结构 — {state.selected_year}-{state.selected_month:02d}").classes("text-base font-bold")
            with ui.card_section():
                pie_data = [{"value": round(r.get("ytd") or 0, 2), "name": r["name"]}
                            for r in inc["rows"] if r["type"] in ("expense_header","expense_item") and (r.get("ytd") or 0) > 0]
                if pie_data:
                    ui.echart({
                        "tooltip": {"trigger": "item", "formatter": "{b}: ¥{c} ({d}%)"},
                        "series": [{
                            "type": "pie", "radius": ["30%", "70%"],
                            "data": pie_data,
                            "label": {"formatter": "{b}\n{d}%"},
                            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.5)"}},
                        }],
                    }).classes("w-full h-64")
                else:
                    ui.label("暂无费用数据").classes("text-sm").style("color:var(--c-text-muted)").classes("p-4")


    # ── 现金流瀑布图 ──
    with ui.card().classes("w-full mt-3"):
        with ui.card_section().classes("py-2 px-3"):
            ui.label(f"🌊 现金流瀑布图 — {state.selected_year}年").classes("text-base font-bold")
        with ui.card_section():
            try:
                # 按月汇总全年收支
                months_data = []
                for m in range(1, 13):
                    inc = get_income_statement(lid, state.selected_year, m)
                    rev = inc["total_revenue"]
                    exp = sum(r["ytd"] for r in inc["rows"] if r["type"] in ("expense_header","expense_item","subtotal"))
                    months_data.append({"month": f"{m}月", "revenue": round(rev, 2), "expense": round(exp, 2), "net": round(rev - exp, 2)})
                # 瀑布图：逐月累计
                waterfall_vals = []
                cumulative = 0
                for md in months_data:
                    if md["month"] == "1月":
                        waterfall_vals.append({"value": md["revenue"], "itemStyle": {"color": "#4caf50"}})
                        cumulative = md["revenue"]
                    else:
                        waterfall_vals.append({"value": md["revenue"], "itemStyle": {"color": "#81c784"}})
                        cumulative += md["revenue"]
                    waterfall_vals.append({"value": -md["expense"], "itemStyle": {"color": "#e57373"}})
                    cumulative -= md["expense"]
                ui.echart({
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": [md["month"] + "\n收入" for md in months_data] + [md["month"] + "\n支出" for md in months_data]},
                    "yAxis": {"type": "value"},
                    "series": [
                        {"type": "bar", "stack": "cf", "data": [d["revenue"] for d in months_data] + [0]*12, "itemStyle": {"color": "#4caf50"}},
                        {"type": "bar", "stack": "cf", "data": [0]*12 + [-d["expense"] for d in months_data], "itemStyle": {"color": "#f44336"}},
                    ]
                }).classes("w-full h-80")
            except Exception as e:
                ui.label(f"图表加载失败: {e}").classes("text-sm p-4").style("color:var(--c-danger)")
