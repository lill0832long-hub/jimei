"""预算管理 P2-4"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from database_v3 import (
    get_budgets, set_budget, get_budget_execution, get_budget_summary,
    get_accounts,
)


def render_budget():
    """预算管理主页面"""
    if not state.selected_ledger_id:
        from database_v3 import get_ledgers
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    year, month = state.selected_year, state.selected_month
    summary = get_budget_summary(lid, year, month)

    # ── 顶部：预算汇总卡片 ──
    with ui.row().classes("w-full gap-3"):
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("预算总额").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"¥{summary['total_budget']:,.2f}").classes("text-xl font-bold").style("color:var(--c-primary)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("实际支出").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"¥{summary['total_actual']:,.2f}").classes("text-xl font-bold").style("color:var(--c-text-primary)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("差异").classes("text-xs").style("color:var(--c-text-muted)")
                    var = summary['total_variance']
                    ui.label(f"¥{var:,.2f}").classes("text-xl font-bold").style(
                        f"color:{'var(--c-danger)' if var > 0 else 'var(--c-success)'}"
                    )

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("超预算科目").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"{summary['over_budget_count']} / {summary['item_count']}").classes("text-xl font-bold").style(
                        f"color:{'var(--c-danger)' if summary['over_budget_count'] > 0 else 'var(--c-success)'}"
                    )

    # ── 下部：预算编制 + 执行追踪 ──
    with ui.row().classes("w-full gap-3 mt-1"):
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center justify-between"):
                    ui.label("📝 预算编制").classes("text-sm font-semibold")
                    ui.button("➕ 添加预算科目", color="primary", on_click=lambda: _show_add_budget_dialog(lid, year, month)).props("dense")

            budgets = get_budgets(lid, year, month)
            if budgets:
                cols = [
                    {"name":"account","label":"科目","field":"account_name","align":"left","headerClasses":"table-header-cell text-uppercase"},
                    {"name":"budget_amount","label":"预算金额","field":"budget_amount","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:140px"},
                    {"name":"description","label":"备注","field":"description","align":"left","headerClasses":"table-header-cell text-uppercase"},
                ]
                rows = [{**b, "account": f"{b['account_code']} {b['account_name']}", "budget_amount": f"¥{b['budget_amount']:,.2f}"} for b in budgets]
                ui.table(columns=cols, rows=rows, row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full text-sm")
            else:
                with ui.card_section():
                    ui.label("暂无预算数据，点击「添加预算科目」").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                ui.label("📊 执行追踪").classes("text-sm font-semibold")

            execution = get_budget_execution(lid, year, month)
            if execution:
                cols = [
                    {"name":"account","label":"科目","field":"account_name","align":"left","headerClasses":"table-header-cell text-uppercase"},
                    {"name":"budget","label":"预算","field":"budget_amount","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
                    {"name":"actual","label":"实际","field":"actual_amount","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
                    {"name":"variance","label":"差异","field":"variance","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
                    {"name":"status","label":"状态","field":"is_over_budget","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:70px"},
                ]
                rows = []
                for e in execution:
                    rows.append({
                        "id": e["id"],
                        "account": f"{e['account_code']} {e['account_name']}",
                        "budget": f"¥{e['budget_amount']:,.2f}",
                        "actual": f"¥{e['actual_amount']:,.2f}",
                        "variance": f"{'⚠️ ' if e['is_over_budget'] else ''}¥{e['variance']:,.2f}",
                        "status": "🔴 超支" if e["is_over_budget"] else "✅ 正常",
                    })
                ui.table(columns=cols, rows=rows, row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full text-sm")
            else:
                with ui.card_section():
                    ui.label("暂无执行数据").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")


def _show_add_budget_dialog(ledger_id: int, year: int, month: int):
    """添加预算科目对话框"""
    d = ui.dialog()
    accounts = get_accounts()
    account_options = {f"{a['code']} {a['name']}": a for a in accounts}

    with d, ui.card().classes("w-[480px]"):
        with ui.card_section():
            ui.label("➕ 添加预算科目").classes("text-lg font-bold")
        with ui.card_section().classes("gap-3"):
            acct_select = ui.select(
                options=list(account_options.keys()),
                label="选择科目"
            ).props("outlined dense").classes("w-full")
            amount_input = ui.number(
                label="预算金额", value=0, format="%.2f"
            ).props("outlined dense").classes("w-full")
            desc_input = ui.input(
                label="备注", placeholder="选填"
            ).props("outlined dense").classes("w-full")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("✅ 保存", color="primary", on_click=lambda: _do_save_budget(
                    d, ledger_id, year, month,
                    account_options.get(acct_select.value) if acct_select.value else None,
                    float(amount_input.value or 0),
                    desc_input.value or ""
                ))
    d.open()


def _do_save_budget(d, ledger_id, year, month, account, amount, desc):
    if not account:
        show_toast("请选择科目", "warning")
        return
    if amount <= 0:
        show_toast("请输入预算金额", "warning")
        return
    try:
        set_budget(ledger_id, account["code"], account["name"], year, month, amount, desc)
        show_toast(f"✅ {account['name']} 预算已设置", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
