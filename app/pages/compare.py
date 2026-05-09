"""对比分析"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount
from database_v3 import (
    get_ledgers, get_period_compare_income, get_period_compare_balance,
)

def render_compare():
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return
    lid = state.selected_ledger_id

    # 期间选择器
    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2 px-3"):
            with ui.row().classes("items-center justify-between"):
                ui.label("📊 多期间对比分析").classes("text-base font-bold")
                with ui.row().classes("items-center gap-2"):
                    ui.label("基准年：").classes("text-sm")
                    ui.select(list(range(2024,2031)), value=state.selected_year,
                        on_change=lambda e: [setattr(state,'selected_year',e.value), refresh_main()]
                    ).props("dense outlined").classes("w-20")
                    ui.label("对比月数：").classes("text-sm")
                    ui.select([3,6,12], value=6,
                        on_change=lambda e: [setattr(state,'compare_months',e.value), refresh_main()]
                    ).props("dense outlined").classes("w-16")

    # 生成对比期间列表
    periods = []
    y, m = state.selected_year, state.selected_month
    for i in range(state.compare_months - 1, -1, -1):
        pm = m - i
        py = y
        while pm <= 0:
            pm += 12
            py -= 1
        periods.append((py, pm))

    # 利润对比
    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2 px-3"):
            ui.label("📈 利润对比").classes("text-base font-bold")

        inc_data = get_period_compare_income(lid, periods)
        if inc_data["items"] or any(v != 0 for v in inc_data["summary"]["total_revenue"]):
            # 汇总表头
            cols = [{"name":"item","label":"项目","field":"item","align":"left","headerClasses":"table-header-cell"}]
            for i, p in enumerate(inc_data["periods"]):
                cols.append({"name":f"p{i}","label":p,"field":f"p{i}","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell"})
            if len(inc_data["periods"]) >= 2:
                cols.append({"name":"change","label":"环比","field":"change","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell"})

            rows = []
            # 收入小计
            rev_vals = inc_data["summary"]["total_revenue"]
            row = {"item": "➕ 营业收入合计"}
            for i, v in enumerate(rev_vals):
                row[f"p{i}"] = f"¥{v:,.0f}"
            if len(rev_vals) >= 2 and rev_vals[-2] != 0:
                row["change"] = f"{(rev_vals[-1]-rev_vals[-2])/rev_vals[-2]*100:+.1f}%"
            rows.append(row)

            # 各收入项
            for item in inc_data["items"]:
                if item["type"] != "revenue":
                    continue
                if all(v == 0 for v in item["values"]):
                    continue
                row = {"item": f"    {item['name']}"}
                for i, v in enumerate(item["values"]):
                    row[f"p{i}"] = f"¥{v:,.0f}" if v else "-"
                if item["changes"] and item["changes"][-1] is not None:
                    row["change"] = f"{item['changes'][-1]:+.1f}%"
                rows.append(row)

            # 费用小计
            exp_vals = inc_data["summary"]["total_expense"]
            row = {"item": "➖ 费用合计"}
            for i, v in enumerate(exp_vals):
                row[f"p{i}"] = f"¥{v:,.0f}" if v else "-"
            if len(exp_vals) >= 2 and exp_vals[-2] != 0:
                row["change"] = f"{(exp_vals[-1]-exp_vals[-2])/exp_vals[-2]*100:+.1f}%"
            rows.append(row)

            # 各费用项
            for item in inc_data["items"]:
                if item["type"] != "expense":
                    continue
                if all(v == 0 for v in item["values"]):
                    continue
                row = {"item": f"    {item['name']}"}
                for i, v in enumerate(item["values"]):
                    row[f"p{i}"] = f"¥{v:,.0f}" if v else "-"
                if item["changes"] and item["changes"][-1] is not None:
                    row["change"] = f"{item['changes'][-1]:+.1f}%"
                rows.append(row)

            # 净利润
            np_vals = inc_data["summary"]["net_profit"]
            row = {"item": "💰 净利润", "bold": True}
            for i, v in enumerate(np_vals):
                row[f"p{i}"] = f"¥{v:,.0f}" if v else "-"
            if len(np_vals) >= 2 and np_vals[-2] != 0:
                row["change"] = f"{(np_vals[-1]-np_vals[-2])/np_vals[-2]*100:+.1f}%"
            rows.append(row)

            ui.table(columns=cols, rows=rows, row_key="item", pagination=False).classes("w-full text-sm")
        else:
            with ui.card_section():
                ui.label("暂无数据").classes("text-sm").style("color:var(--c-text-muted)")

    # 资产负债对比
    with ui.card().classes("w-full mt-3"):
        with ui.card_section().classes("py-2 px-3"):
            ui.label("📗 资产负债对比").classes("text-base font-bold")

        bs_data = get_period_compare_balance(lid, periods)
        if bs_data["periods"]:
            cols = [{"name":"item","label":"项目","field":"item","align":"left","headerClasses":"table-header-cell"}]
            for i, p in enumerate(bs_data["periods"]):
                cols.append({"name":f"p{i}","label":p,"field":f"p{i}","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell"})
            if len(bs_data["periods"]) >= 2:
                cols.append({"name":"change","label":"环比","field":"change","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell"})

            rows = []
            for label, key in [("资产总计","assets"),("负债总计","liabilities"),("所有者权益","equity")]:
                vals = bs_data["summary"][key]
                row = {"item": label, "bold": True}
                for i, v in enumerate(vals):
                    row[f"p{i}"] = f"¥{v:,.0f}"
                if len(vals) >= 2 and vals[-2] != 0:
                    row["change"] = f"{(vals[-1]-vals[-2])/vals[-2]*100:+.1f}%"
                rows.append(row)

            ui.table(columns=cols, rows=rows, row_key="item", pagination=False).classes("w-full text-sm")
        else:
            with ui.card_section():
                ui.label("暂无数据").classes("text-sm").style("color:var(--c-text-muted)")
