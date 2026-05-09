"""期末结转"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount
from database_v3 import (
    get_ledgers, get_income_statement, get_period_status, close_period,
    query_db,
)

def render_close_period():
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return
    lid = state.selected_ledger_id
    period = get_period_status(lid, state.selected_year, state.selected_month)
    inc = get_income_statement(lid, state.selected_year, state.selected_month)

    # ── 结转前检查清单 ──
    checklist = []
    try:
        unapproved = query_db("SELECT COUNT(*) as cnt FROM vouchers WHERE ledger_id=? AND status='draft'", (lid,))
        unapproved_cnt = unapproved[0]["cnt"] if unapproved else 0
        checklist.append(("凭证全部审核", unapproved_cnt == 0, f"{unapproved_cnt} 张凭证未审核" if unapproved_cnt > 0 else "所有凭证已审核"))
        has_profit = any(r["type"] in ("revenue_item","revenue_header","rev_total","expense_header","expense_item") for r in inc["rows"])
        checklist.append(("存在损益数据", has_profit, "暂无损益数据" if not has_profit else "损益数据正常"))
        total_rev = sum(float(r.get("ytd",0) or 0) for r in inc["rows"] if r["type"] in ("revenue_item","revenue_header"))
        total_exp = sum(abs(float(r.get("ytd",0) or 0)) for r in inc["rows"] if r["type"] in ("expense_item","expense_header"))
        checklist.append(("损益数据有效", total_rev > 0 or total_exp > 0, "收入和费用均为0" if total_rev == 0 and total_exp == 0 else "数据有效"))
    except Exception as e:
        checklist.append(("系统检查", False, f"检查异常: {e}"))
    all_passed = all(ok for _, ok, _ in checklist) and not period["closed"]

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            with ui.row().classes("items-center justify-between"):
                ui.label("🔄 期末损益结转").classes("text-base font-bold")
                ui.label(f"{state.selected_year}年{state.selected_month}月").classes("text-sm").style("color:var(--c-text-muted)")

        if period["closed"]:
            with ui.card_section().classes("py-2.5 px-4 bg-green-50"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle").style("color:var(--c-success)")
                    ui.label("已结转").classes("font-semibold").style("color:var(--c-success)")
                    ui.label(f"{period['voucher_no']} | {(period['closed_at'] or '')[:10]}").classes("text-xs tabular-nums").style("color:var(--c-success)")
                ui.button("🔙 反结转（需谨慎）", color="orange", on_click=show_reverse_close_confirm).props("dense").classes("mt-2")
        else:
            with ui.card_section().classes("py-2.5 px-4 bg-orange-50"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning").style("color:var(--c-warning)")
                    ui.label("尚未结转").classes("font-semibold").style("color:var(--c-warning)")

        # ── 结转前检查清单 ──
        with ui.card_section().classes("py-2 px-4"):
            ui.label("✅ 结转前检查清单").classes("text-sm font-semibold mb-1")
            for item_name, ok, desc in checklist:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle" if ok else "cancel").style(f"color:var(--c-success)" if ok else f"color:var(--c-danger)")
                    ui.label(item_name).classes("text-sm").style("color:var(--c-text-secondary)")
                    ui.label(f"— {desc}").classes("text-xs").style("color:var(--c-text-muted)")

        if any(r["type"] in ("revenue_item","revenue_header","rev_total","expense_header","expense_item") for r in inc["rows"]):
            with ui.card_section().classes("py-2 px-4"):
                ui.label("损益预览").classes("text-sm font-semibold mb-1")
                cols = [
                    {"name":"item","label":"项目","field":"item","align":"left","headerClasses":"table-header-cell"},
                    {"name":"amount","label":"金额","field":"amount","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell"},
                ]
                rows = []
                for r in inc["rows"]:
                    if r["type"] in ("revenue_item","revenue_header","rev_total"):
                        rows.append({"item": f"  ➕ {r['name']}", "amount": f"¥{r.get('ytd',0) or 0:,.2f}"})
                for r in inc["rows"]:
                    if r["type"] in ("expense_header","expense_item","subtotal"):
                        rows.append({"item": f"  ➖ {r['name']}", "amount": f"¥{r.get('ytd',0) or 0:,.2f}"})
                rows.append({"item": "💰 净利润", "amount": f"¥{inc['net_profit']:,.2f}"})
                ui.table(columns=cols, rows=rows, row_key="item", pagination=False)

        with ui.card_section().classes("py-2 px-4"):
            ui.button("🔄 执行结转", color="red", on_click=show_close_period_confirm).props("dense").set_enabled(all_passed)
def show_close_period_confirm():
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label("⚠️ 确认期末结转").classes("text-lg font-bold").style("color:var(--c-danger)")
            ui.label(f"即将结转 {state.selected_year}年{state.selected_month}月 的损益").classes("mt-2")
            ui.label("此操作不可撤销").style("color:var(--c-text-secondary)")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("确认结转", color="red", on_click=lambda: do_close_period(d))
    d.open()


def show_reverse_close_confirm():
    """反结转确认弹窗"""
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section().style("color:var(--c-warning-light)"):
            ui.label("⚠️ 反结转操作").classes("text-lg font-bold").style("color:var(--c-warning)")
        with ui.card_section():
            ui.label("反结转将删除结转凭证，恢复损益类科目余额。").classes("text-sm").style("color:var(--c-text-secondary)")
            ui.label("此操作需谨慎，请确认后续期间尚未结账。").classes("text-sm").style("color:var(--c-danger)")
        with ui.card_section().classes("flex justify-end gap-2"):
            ui.button("取消", on_click=d.close).props("flat")
            ui.button("确认反结转", color="orange", on_click=lambda: _do_reverse_close(d)).props("dense")
    d.open()

def _do_reverse_close(dialog):
    """执行反结转"""
    try:
        close_period(state.selected_ledger_id, state.selected_year, state.selected_month, reverse=True)
        show_toast("反结转成功", "success")
        dialog.close()
        refresh_main()
    except Exception as e:
        show_toast(f"反结转失败：{str(e)}", "error")

def do_close_period(d):
    lid = state.selected_ledger_id
    try:
        vn = close_period(lid, state.selected_year, state.selected_month)
        if vn:
            show_toast(f"✅ 损益结转成功！凭证号：{vn}", "success")
        else:
            show_toast("ℹ️ 本期无损益需要结转", "info")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
