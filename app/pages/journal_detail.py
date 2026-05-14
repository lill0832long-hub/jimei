"""凭证详情"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import refresh_main, show_toast
from app.components.ui_components import StatusBadge
from app.services import VoucherService, AccountService
from app.pages.journal_actions import (
    do_submit_review, do_approve_voucher, do_post_voucher,
    show_reverse_dialog, show_reject_dialog, do_delete_voucher,
)


def render_voucher_detail(voucher_no):
    detail = VoucherService.get_detail(state.selected_ledger_id, voucher_no)
    if not detail or not isinstance(detail, dict):
        return
    user = state.current_user
    role = user.get("role", "viewer") if user else "viewer"
    status = detail.get("status", "draft")
    status_labels = {"draft": "草稿", "posted": "已过账", "reversed": "已冲销", "pending_review": "待审核"}
    status_colors = {"draft": "orange", "posted": "green", "reversed": "red", "pending_review": "blue"}

    # 流程可视化：草稿 → 待审核 → 已过账
    flow_steps = [
        ("draft",         "草稿",  "edit"),
        ("pending_review", "待审核", "hourglass_empty"),
        ("posted",        "已过账", "check_circle"),
    ]
    with ui.card().classes("w-full"):
        # ── 流程进度条 ──
        with ui.card_section().classes("py-1.5 px-3 border-b").style("border-color:var(--c-border-light)"):
            with ui.row().classes("items-center justify-center gap-0"):
                for i, (skey, slabel, sicon) in enumerate(flow_steps):
                    is_active = status == skey
                    is_passed = (skey == "draft" and status in ("pending_review", "posted", "reversed")) or \
                                (skey == "pending_review" and status == "posted")
                    if i > 0:
                        ui.element("div").style(
                            f"width:40px;height:2px;background:{'var(--c-success)' if is_passed or is_active else 'var(--c-border)'};flex-shrink:0"
                        )
                    with ui.column().classes("items-center gap-0").style("cursor:default"):
                        ui.icon(sicon).style(
                            f"font-size:20px;color:{'var(--c-success)' if is_passed else 'var(--c-primary)' if is_active else 'var(--c-border)'}"
                        )
                        ui.label(slabel).style(
                            f"font-size:10px;color:{'var(--c-success)' if is_passed else 'var(--c-primary)' if is_active else 'var(--c-text-muted)'}"
                        )

        # ── 头部信息 ──
        with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light);background:var(--c-bg-hover)"):
            with ui.row().classes("items-center justify-between"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(voucher_no).classes("font-bold text-base").style("color:var(--c-text-primary)")
                    ui.badge(status_labels.get(status, status), color=status_colors.get(status, "grey"))
                with ui.row().classes("gap-4 text-xs").style("color:var(--c-text-muted)"):
                    ui.label(f"📅 {detail.get('date', '')}")
                    ui.label(f"📝 {detail.get('description', '')}")

        # ── 分录明细 ──
        entries = detail.get("entries", [])
        cols = [
            {"name": "account_code", "label": "代码", "field": "account_code"},
            {"name": "account_name", "label": "科目", "field": "account_name"},
            {"name": "debit", "label": "借方", "field": "debit", "align": "right"},
            {"name": "credit", "label": "贷方", "field": "credit", "align": "right"},
        ]
        rows = [{**e, "debit": f'{e["debit"]:,.2f}' if e["debit"] else "",
                      "credit": f'{e["credit"]:,.2f}' if e["credit"] else ""} for e in entries]
        ui.table(columns=cols, rows=rows, row_key="id", pagination=False).classes("w-full text-sm")

        # ── 合计行 ──
        with ui.card_section().classes("py-1 px-3"):
            with ui.row().classes("justify-end gap-4 text-sm"):
                ui.label(f"借：¥{detail.get('total_debit', 0):,.2f}").style("color:var(--c-danger)")
                ui.label(f"贷：¥{detail.get('total_credit', 0):,.2f}").style("color:var(--c-primary)")

        # ── 操作记录时间线 ──
        try:
            _wf_list = VoucherService.get_workflow_history(state.selected_ledger_id, voucher_no)
        except Exception:
            _wf_list = []
        with ui.card_section().classes("py-2 px-3 border-t"):
            ui.label("操作记录").classes("text-xs font-semibold mb-1").style("color:var(--c-text-secondary)")
            if _wf_list:
                for _wf in _wf_list:
                    _action = _wf.get("action", "")
                    _from = _wf.get("from_status", "")
                    _to = _wf.get("to_status", "")
                    _user = _wf.get("username", "系统")
                    _time = _wf.get("created_at", "")
                    _comment = _wf.get("comment", "")
                    _action_labels = {
                        "create": "创建", "submit": "提交审核", "approve": "审核通过",
                        "reject": "驳回", "post": "过账", "reverse": "冲销", "delete": "删除",
                    }
                    _action_label = _action_labels.get(_action, _action)
                    with ui.row().classes("items-center gap-2 text-xs").style("color:var(--c-text-muted)"):
                        ui.label(f"[{_time}]" if _time else "").classes("text-xs").style("color:var(--c-text-muted);white-space:nowrap")
                        ui.label(f"{_user}").classes("text-xs font-medium").style("color:var(--c-text-secondary)")
                        ui.label(f"{_action_label}").classes("text-xs").style("color:var(--c-primary)")
                        if _from and _to:
                            ui.label(f"({_from} → {_to})").classes("text-xs").style("color:var(--c-text-muted)")
                        if _comment:
                            ui.label(f"备注: {_comment}").classes("text-xs").style("color:var(--c-text-muted)")
            else:
                ui.label("暂无操作记录").classes("text-xs").style("color:var(--c-text-muted)")

        # ── 操作按钮（按状态显示）──
        with ui.card_section().classes("py-1 px-3"):
            with ui.row().classes("justify-end gap-1"):
                if status == "draft":
                    if role in ("admin", "accountant"):
                        ui.button("编辑", icon="edit", on_click=lambda: _show_edit_dialog(detail)).props("flat dense")
                        ui.button("提交审核", color="blue", on_click=lambda: do_submit_review(voucher_no)).props("dense text-sm")
                        ui.button("直接过账", color="green", on_click=lambda: do_post_voucher(voucher_no)).props("dense text-sm")
                        ui.button("删除", icon="delete", color="red", on_click=lambda: do_delete_voucher(voucher_no)).props("flat dense")
                elif status == "pending_review":
                    if role in ("admin", "reviewer"):
                        ui.button("审核通过", icon="check", color="green", on_click=lambda: do_approve_voucher(voucher_no)).props("flat dense")
                        ui.button("驳回", icon="close", color="red", on_click=lambda: show_reject_dialog(voucher_no)).props("flat dense")
                    else:
                        ui.label("等待审核中...").classes("text-sm").style("color:var(--c-text-muted)")
                elif status == "posted":
                    if role in ("admin", "poster"):
                        ui.button("冲销", icon="undo", color="orange", on_click=lambda: show_reverse_dialog(voucher_no)).props("flat dense")
                elif status == "reversed":
                    ui.label("已冲销").classes("text-sm").style("color:var(--c-danger)")


def render_voucher_detail_page():
    """页面路由入口 — 从 state 读取凭证号"""
    if state.selected_voucher_no:
        render_voucher_detail(state.selected_voucher_no)
    else:
        ui.label("请先选择一张凭证").classes("text-center p-8").style("color:var(--c-text-muted)")


def _show_edit_dialog(detail):
    # deferred to avoid circular import: journal_form_v2 -> ui_helpers -> journal_detail
    from app.pages.journal_form_v2 import show_edit_voucher_dialog
    show_edit_voucher_dialog(detail)
