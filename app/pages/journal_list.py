"""凭证列表"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import refresh_main, format_amount, navigate
from app.components.ui_components import SectionHeader, EmptyState
from app.services import LedgerService, VoucherService
from app.pages.journal_form_v2 import show_edit_voucher_dialog


def render_journal():
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # 清除已消费的钻取状态
    state.drill_down_voucher_no = None
    state.drill_down_account_code = None

    # 权限检查
    user = state.current_user
    can_create = user and user.get("role") in ("admin", "accountant")

    with ui.row().classes("w-full gap-3"):
        # ── 左侧：凭证列表（2/3）──
        with ui.column().classes("w-2/3 gap-2"):
            with ui.card().classes("w-full"):
                # 标题行
                with ui.card_section().classes("py-2.5 px-3"):
                    SectionHeader("凭证列表", icon="receipt_long",
                                  action=(lambda: navigate("journal_form")) if can_create else None,
                                  action_icon="新增凭证")

                # 按状态筛选获取凭证
                filter_status = state.voucher_status_filter if state.voucher_status_filter != "all" else None
                vouchers = VoucherService.get_all(lid, state.selected_year, state.selected_month,
                                       status=filter_status, limit=50)

                # 状态筛选 chip 栏（带数量统计）
                # 获取全部凭证用于计数
                all_vouchers = VoucherService.get_all(lid, state.selected_year, state.selected_month, limit=500)
                status_counts = {"all": len(all_vouchers)}
                for v in all_vouchers:
                    s = v.get("status", "draft")
                    status_counts[s] = status_counts.get(s, 0) + 1

                with ui.card_section().classes("py-1.5 px-3 border-t border-grey-1"):
                    with ui.row().classes("items-center gap-1.5"):
                        ALL_STATUS = [
                            ("all", "全部"), ("draft", "草稿"),
                            ("pending_review", "待审核"), ("posted", "已过账"),
                            ("reversed", "已冲销"),
                        ]
                        for skey, slabel in ALL_STATUS:
                            is_active = state.voucher_status_filter == skey
                            count = status_counts.get(skey, 0)
                            chip_label = f"{slabel} ({count})"
                            ui.chip(chip_label, on_click=lambda k=skey: (
                                setattr(state, 'voucher_status_filter', k),
                                refresh_main()
                            )).props("outline dense").style(
                                f"background:{'var(--c-primary-light)' if is_active else 'transparent'};"
                                f"color:{'var(--c-primary)' if is_active else 'var(--c-text-secondary)'};"
                                f"border-color:{'var(--c-primary)' if is_active else 'var(--c-border)'}"
                            )

                if not vouchers:
                    EmptyState(message="本月暂无凭证", hint="点击右上角「新增凭证」创建第一张凭证",
                              action=(lambda: navigate("journal_form")) if can_create else None,
                              action_label="新增凭证")

                status_labels = {"draft": "草稿", "posted": "已过账", "reversed": "已冲销", "pending_review": "待审核"}
                status_colors = {"draft": "orange", "posted": "green", "reversed": "red", "pending_review": "blue"}
                rows = [{**v,
                    "status": v.get("status", "draft"),
                    "status_label": status_labels.get(v.get("status", "draft"), "未知"),
                    "status_color": status_colors.get(v.get("status", "draft"), "grey"),
                    "total": format_amount(v.get("total_debit", 0)),
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
