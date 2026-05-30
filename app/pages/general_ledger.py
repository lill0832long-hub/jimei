from nicegui import ui
from app.components.ui_components import SectionHeader, EmptyState
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount, navigate, refresh_main, drill_down_to_voucher, render_kpi_cards
from app.services import LedgerService, AccountService


def render_general_ledger():
    """总分类账 — 期间筛选+科目筛选+全部科目明细列表"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # 获取所有科目供选择
    accounts = AccountService.get_all()
    acct_opts = {"": "全部科目"}
    acct_opts.update({a["code"]: f"{a['code']} {a['name']}" for a in accounts})

    # 检查是否有报表钻取的科目筛选
    drill_code = state.drill_down_account_code
    initial_acct = drill_code if drill_code else ""

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2 px-4 bg-grey-5 border-b border-grey-2"):
            with ui.row().classes("items-center gap-3"):
                ui.label("📖 总分类账").classes("text-base font-bold")
                ui.separator().props("vertical")
                ui.label(f"期间：{state.selected_year}年{state.selected_month}月").classes("text-sm text-grey-6 px-2 py-1 bg-blue-50 rounded")
                gl_acct_sel = ui.select(options=acct_opts, value=initial_acct, label="科目").props("outlined dense").classes("w-56")
                ui.button("🔍 查询", color="primary", on_click=lambda: refresh_main()).props("dense").classes("text-xs")

    # 获取总分类账数据
    selected_code = gl_acct_sel.value or None

    # 清除钻取状态（已消费）
    if drill_code:
        state.drill_down_account_code = None
    try:
        entries = AccountService.get_general_ledger(
            lid, account_code=selected_code,
            year=state.selected_year, month=state.selected_month
        )
    except Exception:
        entries = None

    HC = "text-xs font-semibold uppercase tracking-wide text-grey-6"

    with ui.card().classes("w-full"):
        if entries is None:
            with ui.card_section().classes("py-12 text-center"):
                ui.icon("menu_book").style("font-size: 48px; color: var(--gray-300)")
                ui.label("加载失败").classes("text-lg font-semibold text-grey-4 mt-4")
                ui.label("请稍后重试").classes("text-sm text-grey-3 mt-2")
            return

        if not entries:
            with ui.card_section().classes("py-12 text-center"):
                ui.icon("menu_book").style("font-size: 48px; color: var(--gray-300)")
                ui.label("暂无明细数据").classes("text-lg font-semibold text-grey-4 mt-4")
                ui.label("请选择期间后点击查询").classes("text-sm text-grey-3 mt-2")
            return

        # 期间信息栏
        period_label = f"{state.selected_year}年{state.selected_month}月"
        with ui.card_section().classes("py-2 px-4 border-b border-grey-2 bg-blue-50"):
            with ui.row().classes("items-center gap-4"):
                ui.label(f"📖 总分类账").classes("text-base font-bold text-blue-7")
                ui.separator().props("vertical")
                ui.label(f"期间：{period_label}").classes("text-sm text-grey-6")
                ui.separator().props("vertical")
                ui.label(f"共 {len(entries)} 条分录").classes("text-sm text-grey-6")

        # 合计行数据
        total_debit = sum(e.get("debit", 0) or 0 for e in entries)
        total_credit = sum(e.get("credit", 0) or 0 for e in entries)

        # 表格
        cols = [
            {"name": "date", "label": "日期", "field": "date", "align": "left",
             "headerClasses": HC, "classes": "text-sm tabular-nums", "style": "width:100px"},
            {"name": "voucher_no", "label": "凭证号", "field": "voucher_no", "align": "left",
             "headerClasses": HC, "classes": "text-sm text-blue-7", "style": "width:120px"},
            {"name": "account_code", "label": "科目代码", "field": "account_code", "align": "left",
             "headerClasses": HC, "classes": "text-sm tabular-nums", "style": "width:90px"},
            {"name": "account_name", "label": "科目名称", "field": "account_name", "align": "left",
             "headerClasses": HC, "classes": "text-sm", "style": "width:120px"},
            {"name": "summary", "label": "摘要", "field": "summary", "align": "left",
             "headerClasses": HC, "classes": "text-sm text-grey-7", "style": "min-width:180px"},
            {"name": "debit", "label": "借方金额", "field": "debit", "align": "right",
             "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:120px"},
            {"name": "credit", "label": "贷方金额", "field": "credit", "align": "right",
             "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:120px"},
        ]

        rows = []
        for e in entries:
            rows.append({
                "date": e.get("date", ""),
                "voucher_no": e.get("voucher_no", ""),
                "account_code": e.get("account_code", ""),
                "account_name": e.get("account_name", ""),
                "summary": e.get("summary", "") or e.get("voucher_desc", "") or "",
                "debit": e.get("debit", 0) or 0,
                "credit": e.get("credit", 0) or 0,
            })

        # 追加合计行
        rows.append({
            "date": "",
            "voucher_no": "",
            "account_code": "",
            "account_name": "",
            "summary": "合  计",
            "debit": total_debit,
            "credit": total_credit,
        })

        tbl = ui.table(columns=cols, rows=rows,
                       pagination={"rowsPerPage": 50}).classes("w-full")

        tbl.add_slot("body-cell-voucher_no", r"""
            <q-td key="voucher_no" :props="props">
                <q-btn v-if="props.row.voucher_no" flat dense no-caps color="primary"
                       :label="props.row.voucher_no"
                       @click="$parent.$emit('view_voucher', props.row.voucher_no)" />
                <span v-else></span>
            </q-td>
        """)

        tbl.add_slot("body-cell-debit", r"""
            <q-td key="debit" :props="props" class="tabular-nums text-sm">
                <span :class="props.row.summary === '合  计' ? 'font-bold text-green-8' : 'text-green-7'">
                    {{ props.row.debit ? '¥' + props.row.debit.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                </span>
            </q-td>
        """)

        tbl.add_slot("body-cell-credit", r"""
            <q-td key="credit" :props="props" class="tabular-nums text-sm">
                <span :class="props.row.summary === '合  计' ? 'font-bold text-red-8' : 'text-red-7'">
                    {{ props.row.credit ? '¥' + props.row.credit.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                </span>
            </q-td>
        """)

        # 合计行高亮
        tbl.add_slot("body-cell-summary", r"""
            <q-td key="summary" :props="props" class="text-sm"
                :class="props.row.summary === '合  计' ? 'font-bold text-base bg-grey-2' : 'text-grey-7'">
                {{ props.row.summary }}
            </q-td>
        """)

        tbl.on("view_voucher", lambda e: drill_down_to_voucher(e.args))

        # ── KPI 统计卡片 ──
        is_balanced = abs(total_debit - total_credit) < 0.01
        kpis = [
            ("借方合计", total_debit, "add_circle", "red", ""),
            ("贷方合计", total_credit, "remove_circle", "green", ""),
            ("分录数", len(entries), "receipt_long", "blue", "条"),
        ]
        if is_balanced:
            kpis.append(("平衡", "✓", "check_circle", "green", ""))
        render_kpi_cards(kpis)
