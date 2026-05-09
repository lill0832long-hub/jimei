from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount, navigate
from database_v3 import (
    get_ledgers, get_account_ledger, get_accounts,
)

def render_account_ledger():
    """科目明细账 — 科目选择+期间选择+明细列表（日期、凭证号、摘要、借方、贷方、余额）"""
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # 获取所有科目供选择
    accounts = get_accounts()
    acct_opts = {a["code"]: f"{a['code']} {a['name']}" for a in accounts}

    # 支持从报表钻取跳转（通过 state 传递科目ID）
    default_code = getattr(state, '_drill_account_code', None) or (accounts[0]["code"] if accounts else "1001")
    if getattr(state, '_drill_account_code', None):
        state._drill_account_code = None  # 消费后清除

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2 px-4 bg-grey-5 border-b border-grey-2"):
            with ui.row().classes("items-center gap-3"):
                ui.label("📒 科目明细账").classes("text-base font-bold")
                ui.separator().props("vertical")
                al_year_sel = ui.select(options=list(range(2020, 2031)), value=state.selected_year, label="年度").props("dense outlined").classes("w-28")
                al_month_sel = ui.select(options=list(range(1, 13)), value=state.selected_month, label="月份").props("dense outlined").classes("w-24")
                al_acct_sel = ui.select(options=acct_opts, value=default_code, label="科目").props("outlined dense").classes("w-56")
                ui.button("🔍 查询", color="primary", on_click=lambda: refresh_main()).props("dense").classes("text-xs")

                def _on_al_period():
                    state.selected_year = al_year_sel.value
                    state.selected_month = al_month_sel.value
                    state._drill_account_code = al_acct_sel.value
                    refresh_main()

                al_year_sel.on("update:value", lambda e: _on_al_period())
                al_month_sel.on("update:value", lambda e: _on_al_period())

    # 获取科目明细账数据
    current_code = getattr(state, '_drill_account_code', None) or default_code
    try:
        ledger_data = get_account_ledger(lid, current_code, state.selected_year, state.selected_month)
    except Exception:
        ledger_data = None

    HC = "text-xs font-semibold uppercase tracking-wide text-grey-6"

    with ui.card().classes("w-full"):
        if not ledger_data:
            with ui.card_section().classes("py-12 text-center"):
                ui.icon("receipt_long").style("font-size: 48px; color: var(--gray-300)")
                ui.label("暂无明细数据").classes("text-lg font-semibold text-grey-4 mt-4")
                ui.label("请选择科目和期间后点击查询").classes("text-sm text-grey-3 mt-2")
            return

        acct = ledger_data["account"]
        opening = ledger_data["opening_balance"]
        closing = ledger_data["closing_balance"]
        period = ledger_data["period"]
        entries = ledger_data["entries"]

        # 科目信息栏
        with ui.card_section().classes("py-2 px-4 border-b border-grey-2 bg-blue-50"):
            with ui.row().classes("items-center gap-4"):
                ui.label(f"📒 {acct['code']} {acct['name']}").classes("text-base font-bold text-blue-7")
                ui.separator().props("vertical")
                ui.label(f"期间：{period}").classes("text-sm text-grey-6")
                ui.separator().props("vertical")
                ui.label(f"科目类别：{acct.get('category', '')}").classes("text-sm text-grey-6")

        # 期初/期末余额栏
        with ui.card_section().classes("py-1.5 px-4 border-b border-grey-2 bg-grey-50"):
            with ui.row().classes("justify-between items-center"):
                with ui.row().classes("gap-6"):
                    ui.label("期初余额").classes("text-xs text-grey-5")
                    ui.label(f"¥{opening:,.2f}").classes("text-sm font-bold text-grey-7 tabular-nums")
                with ui.row().classes("gap-6"):
                    ui.label("本期借方").classes("text-xs text-grey-5")
                    ui.label(f"¥{sum(e['debit'] for e in entries):,.2f}").classes("text-sm font-bold text-green-7 tabular-nums")
                    ui.label("本期贷方").classes("text-xs text-grey-5")
                    ui.label(f"¥{sum(e['credit'] for e in entries):,.2f}").classes("text-sm font-bold text-red-7 tabular-nums")
                with ui.row().classes("gap-6"):
                    ui.label("期末余额").classes("text-xs text-grey-5")
                    ui.label(f"¥{closing:,.2f}").classes("text-sm font-bold text-blue-7 tabular-nums")

        if not entries:
            with ui.card_section().classes("py-8 text-center"):
                ui.label("该期间内无发生额").classes("text-grey-5 text-sm")
        else:
            cols = [
                {"name": "date", "label": "日期", "field": "date", "align": "left",
                 "headerClasses": HC, "classes": "text-sm tabular-nums", "style": "width:100px"},
                {"name": "voucher_no", "label": "凭证号", "field": "voucher_no", "align": "left",
                 "headerClasses": HC, "classes": "text-sm text-blue-7", "style": "width:120px"},
                {"name": "summary", "label": "摘要", "field": "summary", "align": "left",
                 "headerClasses": HC, "classes": "text-sm text-grey-7", "style": "min-width:180px"},
                {"name": "debit", "label": "借方", "field": "debit", "align": "right",
                 "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:120px"},
                {"name": "credit", "label": "贷方", "field": "credit", "align": "right",
                 "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:120px"},
                {"name": "balance", "label": "余额", "field": "balance", "align": "right",
                 "headerClasses": HC, "classes": "tabular-nums text-sm font-semibold", "style": "width:120px"},
            ]
            rows = []
            for e in entries:
                rows.append({
                    "date": e.get("date", ""),
                    "voucher_no": e.get("voucher_no", ""),
                    "summary": e.get("summary", "") or e.get("voucher_desc", "") or "",
                    "debit": e.get("debit", 0) or 0,
                    "credit": e.get("credit", 0) or 0,
                    "balance": e.get("balance", 0) or 0,
                })

            tbl = ui.table(columns=cols, rows=rows, row_key="voucher_no",
                           pagination={"rowsPerPage": 25}).classes("w-full")

            tbl.add_slot("body-cell-voucher_no", r"""
                <q-td key="voucher_no" :props="props">
                    <q-btn flat dense no-caps color="primary" :label="props.row.voucher_no"
                           @click="$parent.$emit('view_voucher', props.row.voucher_no)" />
                </q-td>
            """)

            tbl.add_slot("body-cell-debit", r"""
                <q-td key="debit" :props="props" class="tabular-nums text-sm">
                    <span class="text-green-7">
                        {{ props.row.debit ? '¥' + props.row.debit.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                    </span>
                </q-td>
            """)

            tbl.add_slot("body-cell-credit", r"""
                <q-td key="credit" :props="props" class="tabular-nums text-sm">
                    <span class="text-red-7">
                        {{ props.row.credit ? '¥' + props.row.credit.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                    </span>
                </q-td>
            """)

            tbl.add_slot("body-cell-balance", r"""
                <q-td key="balance" :props="props" class="tabular-nums text-sm font-semibold">
                    <span :class="props.row.balance >= 0 ? 'text-blue-7' : 'text-red-7'">
                        {{ props.row.balance !== null ? '¥' + props.row.balance.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                    </span>
                </q-td>
            """)

            tbl.on("view_voucher", lambda e: (setattr(state, 'selected_voucher_no', e.args), refresh_main()))



