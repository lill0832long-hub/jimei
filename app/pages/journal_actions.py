"""凭证操作 — 过账/冲销/删除/审核"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from app.services import VoucherService


def _get_user_id():
    return state.current_user.get("id") if state.current_user else None


def do_submit_review(voucher_no):
    try:
        lid = state.selected_ledger_id
        VoucherService.submit_for_review(lid, voucher_no, user_id=_get_user_id())
        show_toast(f"凭证 {voucher_no} 已提交审核", "info")
        refresh_main()
    except Exception as e:
        show_toast(f"提交审核失败: {e}", "error")


def do_approve_voucher(voucher_no):
    try:
        lid = state.selected_ledger_id
        VoucherService.approve(lid, voucher_no, user_id=_get_user_id())
        show_toast(f"凭证 {voucher_no} 审核通过并已过账", "success")
        refresh_main()
    except Exception as e:
        show_toast(f"审核失败: {e}", "error")


def do_reject_voucher(voucher_no, reason="审核拒绝"):
    try:
        lid = state.selected_ledger_id
        VoucherService.reject(lid, voucher_no, reason=reason, user_id=_get_user_id())
        show_toast(f"凭证 {voucher_no} 已退回草稿", "warning")
        refresh_main()
    except Exception as e:
        show_toast(f"驳回失败: {e}", "error")


def show_reject_dialog(voucher_no):
    """驳回对话框（带原因输入）"""
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label(f"❌ 驳回凭证 {voucher_no}").classes("text-lg font-bold").style("color:var(--c-danger)")
            reason_input = ui.input("驳回原因", placeholder="请输入驳回原因").props("outlined").classes("w-full mt-2")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("确认驳回", color="red",
                          on_click=lambda: (do_reject_voucher(voucher_no, reason_input.value), d.close()))
    d.open()


def do_post_voucher(voucher_no):
    try:
        lid = state.selected_ledger_id
        VoucherService.post(lid, voucher_no)
        show_toast(f"凭证 {voucher_no} 已过账", "success")
        refresh_main()
    except Exception as e:
        show_toast(f"过账失败: {e}", "error")


def do_delete_voucher(voucher_no):
    try:
        lid = state.selected_ledger_id
        VoucherService.delete(voucher_no, ledger_id=lid)
        show_toast(f"✅ 凭证 {voucher_no} 已删除", "success")
        state.selected_voucher_no = None
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def show_reverse_dialog(voucher_no):
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label(f"🔄 冲销凭证 {voucher_no}").classes("text-lg font-bold")
            ui.label("冲销将生成红字凭证，原凭证标记为已冲销").style("color:var(--c-text-secondary)")
            reason_input = ui.input("冲销原因", placeholder="选填").props("outlined").classes("w-full mt-2")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("确认冲销", color="red", on_click=lambda: _do_reverse(d, voucher_no, reason_input.value))
    d.open()


def _do_reverse(d, voucher_no, reason):
    try:
        rev_no = VoucherService.reverse(voucher_no, reason or "")
        show_toast(f"✅ 已冲销，新凭证：{rev_no}", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
