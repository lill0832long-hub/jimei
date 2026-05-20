"""期末结转"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount, refresh_main
from app.components.ui_components import SectionHeader, MetricRow
from app.services import LedgerService, ReportService, VoucherService


def render_close_period():
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("🔄").classes("report-empty__icon")
                ui.label("请先创建账套").classes("report-empty__text")
        return

    period = LedgerService.get_period_status(lid, state.selected_year, state.selected_month)
    inc = ReportService.get_income_statement(lid, state.selected_year, state.selected_month)

    # ── 结转前检查清单 ──
    checklist = []
    try:
        draft_cnt = VoucherService.count(lid, status="draft")
        pending_cnt = VoucherService.count(lid, status="pending_review")
        unapproved_cnt = draft_cnt + pending_cnt
        checklist.append(("凭证全部审核", unapproved_cnt == 0,
                          f"{unapproved_cnt} 张凭证未审核（草稿{draft_cnt}+待审核{pending_cnt}）" if unapproved_cnt > 0 else "所有凭证已审核"))
        inc_rows = inc.get("rows", []) if isinstance(inc, dict) else []
        has_profit = any(r.get("type") in ("revenue_item", "revenue_header", "rev_total", "expense_header", "expense_item") for r in inc_rows)
        checklist.append(("存在损益数据", has_profit, "暂无损益数据" if not has_profit else "损益数据正常"))
        total_rev = sum(float(r.get("ytd", 0) or 0) for r in inc_rows if r.get("type") in ("revenue_item", "revenue_header"))
        total_exp = sum(abs(float(r.get("ytd", 0) or 0)) for r in inc_rows if r.get("type") in ("expense_item", "expense_header"))
        checklist.append(("损益数据有效", total_rev > 0 or total_exp > 0,
                          "收入和费用均为0" if total_rev == 0 and total_exp == 0 else "数据有效"))
    except Exception as e:
        checklist.append(("系统检查", False, f"检查异常: {e}"))

    is_closed = period.get("closed", False)
    all_passed = all(ok for _, ok, _ in checklist) and not is_closed

    with ui.card().classes("report-card"):
        # ── 头部 ──
        with ui.row().classes("report-header"):
            ui.label("🔄 期末损益结转").classes("report-header__title")
            ui.label(f"{state.selected_year}年{state.selected_month}月").classes("report-header__subtitle")

        # ── 状态横幅 ──
        if is_closed:
            with ui.row().classes("period-status-banner period-status-banner--closed"):
                ui.icon("check_circle").classes("text-lg")
                with ui.column().classes("gap-0"):
                    ui.label("本期已结转").classes("font-semibold")
                    ui.label(f"{period.get('voucher_no', '')} | {(period.get('closed_at') or '')[:10]}") \
                        .classes("text-xs").style("color:var(--c-success)")
        else:
            with ui.row().classes("period-status-banner period-status-banner--open"):
                ui.icon("warning").classes("text-lg")
                ui.label("本期尚未结转").classes("font-semibold")

        # ── 检查清单 ──
        with ui.card_section().classes("py-3 px-5"):
            ui.label("结转前检查清单").classes("text-sm font-semibold mb-2")
            for item_name, ok, desc in checklist:
                with ui.row().classes("checklist__item"):
                    with ui.element("div").classes(f"checklist__icon {'checklist__icon--pass' if ok else 'checklist__icon--fail'}"):
                        ui.label("✓" if ok else "✗").classes("text-xs")
                    ui.label(item_name).classes("checklist__text font-medium")
                    ui.label(f"— {desc}").classes("text-xs").style("color:var(--c-text-muted)")

        # ── 损益预览 ──
        rows_data = inc.get("rows", []) if isinstance(inc, dict) else []
        if any(r.get("type") in ("revenue_item", "revenue_header", "rev_total", "expense_header", "expense_item") for r in rows_data):
            with ui.card_section().classes("py-3 px-5 border-t").style("border-color:var(--c-border-light)"):
                ui.label("损益预览").classes("text-sm font-semibold mb-2")
                cols = [
                    {"name": "item", "label": "项目", "field": "item", "align": "left",
                     "headerClasses": "table-header-cell"},
                    {"name": "amount", "label": "金额", "field": "amount", "align": "right",
                     "classes": "tabular-nums text-sm", "headerClasses": "table-header-cell"},
                ]
                rows = []
                for r in rows_data:
                    if r.get("type") in ("revenue_item", "revenue_header", "rev_total"):
                        rows.append({"item": f"  ➕ {r.get('name', '')}", "amount": f"¥{r.get('ytd') or 0:,.2f}"})
                for r in rows_data:
                    if r.get("type") in ("expense_header", "expense_item", "subtotal"):
                        rows.append({"item": f"  ➖ {r.get('name', '')}", "amount": f"¥{r.get('ytd') or 0:,.2f}"})
                net = inc.get("net_profit", 0) if isinstance(inc, dict) else 0
                rows.append({"item": "💰 净利润", "amount": f"¥{net:,.2f}"})
                ui.table(columns=cols, rows=rows, row_key="item", pagination=False)

        # ── 操作按钮 ──
        with ui.card_section().classes("py-3 px-5 border-t flex justify-end gap-2").style("border-color:var(--c-border-light)"):
            if is_closed:
                ui.button("反结转（需谨慎）", color="orange", on_click=show_reverse_close_confirm) \
                    .props("dense no-caps")
            else:
                ui.button("执行结转", color="red", on_click=show_close_period_confirm) \
                    .props("dense no-caps").set_enabled(all_passed)


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
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label("⚠️ 反结转操作").classes("text-lg font-bold").style("color:var(--c-warning)")
        with ui.card_section():
            ui.label("反结转将删除结转凭证，恢复损益类科目余额。").classes("text-sm").style("color:var(--c-text-secondary)")
            ui.label("此操作需谨慎，请确认后续期间尚未结账。").classes("text-sm").style("color:var(--c-danger)")
        with ui.card_section().classes("flex justify-end gap-2"):
            ui.button("取消", on_click=d.close).props("flat")
            ui.button("确认反结转", color="orange", on_click=lambda: _do_reverse_close(d)).props("dense")
    d.open()


def _do_reverse_close(dialog):
    try:
        LedgerService.close_period(state.selected_ledger_id, state.selected_year, state.selected_month, reverse=True)
        show_toast("反结转成功", "success")
        dialog.close()
        refresh_main()
    except Exception as e:
        show_toast(f"反结转失败：{str(e)}", "error")


def do_close_period(d):
    lid = state.selected_ledger_id
    try:
        balances = ReportService.get_account_balances(lid, state.selected_year, state.selected_month)
        if balances:
            total_debit = sum(float(b.get("period_debit", 0) if b.get("period_debit") is not None else 0) for b in balances)
            total_credit = sum(float(b.get("period_credit", 0) if b.get("period_credit") is not None else 0) for b in balances)
            diff = abs(total_debit - total_credit)
            if diff >= 0.01:
                show_toast(f"借贷不平衡，差额 {format_amount(diff)}，请先修正凭证", "error")
                return
    except Exception as e:
        show_toast(f"余额校验异常: {e}", "error")
        return

    try:
        vn = LedgerService.close_period(lid, state.selected_year, state.selected_month)
        if vn:
            show_toast(f"✅ 损益结转成功！凭证号：{vn}", "success")
        else:
            show_toast("ℹ️ 本期无损益需要结转", "info")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
