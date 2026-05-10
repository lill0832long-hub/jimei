"""凭证列表"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import refresh_main
from database_v3 import get_ledgers, get_vouchers
from app.pages.journal_actions import show_new_voucher_dialog, show_voucher_detail


def render_journal():
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # 权限检查
    user = state.current_user
    can_create = user and user.get("role") in ("admin", "accountant")

    with ui.row().classes("w-full gap-3"):
        # ── 左侧：凭证列表（2/3）──
        with ui.column().classes("w-2/3 gap-2"):
            with ui.card().classes("w-full"):
                # 标题行 + 状态筛选
                with ui.card_section().classes("py-2 px-3"):
                    with ui.row().classes("items-center justify-between"):
                        ui.label("📋 凭证列表").classes("text-base font-bold")
                        with ui.row().classes("items-center gap-2"):
                            ALL_STATUS = [
                                ("all", "全部"), ("draft", "草稿"),
                                ("pending_review", "待审核"), ("posted", "已过账"),
                                ("reversed", "已冲销"),
                            ]
                            for skey, slabel in ALL_STATUS:
                                is_active = state.voucher_status_filter == skey
                                ui.chip(slabel, on_click=lambda k=skey: (
                                    setattr(state, 'voucher_status_filter', k),
                                    refresh_main()
                                )).props("outline dense").style(
                                    f"background:{'var(--c-primary-light)' if is_active else 'transparent'};"
                                    f"color:{'var(--c-primary)' if is_active else 'var(--c-text-secondary)'};"
                                    f"border-color:{'var(--c-primary)' if is_active else 'var(--c-border)'}"
                                )
                            if can_create:
                                ui.button("➕ 新增凭证", color="primary", on_click=show_new_voucher_dialog).props("dense")

                # 按状态筛选获取凭证
                filter_status = state.voucher_status_filter if state.voucher_status_filter != "all" else None
                vouchers = get_vouchers(lid, state.selected_year, state.selected_month,
                                       status=filter_status, limit=50)
                if not vouchers:
                    with ui.card_section():
                        ui.label("本月暂无凭证").classes("text-sm").style("color:var(--c-text-muted)")

                status_labels = {"draft": "草稿", "posted": "已过账", "reversed": "已冲销", "pending_review": "待审核"}
                status_colors = {"draft": "orange", "posted": "green", "reversed": "red", "pending_review": "blue"}
                rows = [{**v,
                    "status_label": status_labels.get(v["status"], v["status"]),
                    "status_color": status_colors.get(v["status"], "grey"),
                    "total": f'¥{v["total_debit"]:,.2f}',
                } for v in vouchers]

                cols = [
                    {"name": "voucher_no", "label": "凭证号", "field": "voucher_no", "align": "left"},
                    {"name": "date", "label": "日期", "field": "date"},
                    {"name": "description", "label": "摘要", "field": "description", "align": "left"},
                    {"name": "total", "label": "金额", "field": "total", "align": "right"},
                    {"name": "status", "label": "状态", "field": "status_label", "align": "center"},
                ]
                tbl = ui.table(columns=cols, rows=rows, row_key="voucher_no",
                              pagination={"rowsPerPage": 12}).classes("w-full text-sm")
                tbl.add_slot("body-cell-voucher_no", r"""
                    <q-td key="voucher_no" :props="props">
                        <q-btn flat dense no-caps color="primary" :label="props.row.voucher_no"
                               @click="$parent.$emit('show', props.row.voucher_no)" />
                    </q-td>
                """)
                tbl.add_slot("body-cell-status", r"""
                    <q-td key="status" :props="props">
                        <q-badge :color="props.row.status_color" :label="props.row.status_label" size="sm" />
                    </q-td>
                """)
                tbl.on("show", lambda e: show_voucher_detail(e.args))

        # ── 右侧：凭证详情（1/3）──
        with ui.column().classes("w-1/3 gap-2"):
            if state.selected_voucher_no:
                from app.pages.journal_detail import render_voucher_detail
                render_voucher_detail(state.selected_voucher_no)
            else:
                with ui.card().classes("w-full"):
                    with ui.card_section().classes("text-center py-8"):
                        ui.icon("receipt_long").classes("text-4xl").style("color:var(--c-text-muted)")
                        ui.label("点击凭证号查看详情").classes("text-sm mt-2").style("color:var(--c-text-muted)")


def show_voucher_detail(voucher_no):
    state.selected_voucher_no = voucher_no
    refresh_main()
