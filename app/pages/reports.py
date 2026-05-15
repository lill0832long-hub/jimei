"""报表 — 科目余额表"""
from nicegui import ui
from app.components.state import state
from app.services import LedgerService, ReportService


def render_accounts():
    """科目余额表 — ui.table 严格列对齐，金额等宽，借贷分色"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return
    balances = ReportService.get_account_balances(lid, state.selected_year, state.selected_month)

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            ui.label(f"📊 科目余额表 — {state.selected_year}年{state.selected_month}月").classes("text-base font-bold")

        if not balances:
            with ui.card_section().classes("py-12"):
                ui.label("暂无数据").classes("text-sm text-center").style("color:var(--c-text-muted)")
            return

        # 构建行数据
        total = dict.fromkeys(["opening", "debit", "credit", "closing"], 0)
        rows = []
        for b in balances:
            ob = b.get("opening_balance") or 0
            pd = b.get("period_debit") or 0
            pc = b.get("period_credit") or 0
            cb = b.get("closing_balance") or 0
            is_t = b.get("name") == "合计"
            if not is_t:
                for k, v in [("opening", ob), ("debit", pd), ("credit", pc), ("closing", cb)]:
                    total[k] += v
            rows.append({
                "code": b.get("code", ""),
                "name": b.get("name", ""),
                "opening": ob, "debit": pd, "credit": pc, "closing": cb,
                "level": b.get("level", 0), "is_total": is_t,
            })

        # 合计行
        rows.append({
            "code": "", "name": "合 计",
            "opening": total["opening"], "debit": total["debit"],
            "credit": total["credit"], "closing": total["closing"],
            "level": 0, "is_total": True,
        })

        HC = "table-header-cell text-uppercase"
        cols = [
            {"name": "code", "label": "科目编码", "field": "code", "align": "left", "headerClasses": HC, "classes": "text-xs font-mono", "style": "width:96px"},
            {"name": "name", "label": "科目名称", "field": "name", "align": "left", "headerClasses": HC, "classes": "text-sm", "style": "min-width:140px"},
            {"name": "opening", "label": "期初余额", "field": "opening", "align": "right", "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:112px"},
            {"name": "debit", "label": "本期借方", "field": "debit", "align": "right", "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:112px"},
            {"name": "credit", "label": "本期贷方", "field": "credit", "align": "right", "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:112px"},
            {"name": "closing", "label": "期末余额", "field": "closing", "align": "right", "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:112px"},
        ]

        tbl = ui.table(columns=cols, rows=rows, row_key="name", pagination={"rowsPerPage": 50}).classes("w-full")

        # 金额列 slot
        for col_name in ["opening", "debit", "credit", "closing"]:
            slot_template = (
                '<q-td key="' + col_name + '" :props="props" class="tabular-nums text-sm"'
                ' :style="props.row.is_total ? \'background:var(--c-bg-hover);font-weight:700;\' : \'\'">'
                '<span :class="props.row.is_total ? \'font-bold\' : \'\'">'
                '{{ props.row.' + col_name + ' ? \'¥\' + props.row.' + col_name + '.toLocaleString(\'en-US\',{minimumFractionDigits:2,maximumFractionDigits:2}) : \'—\' }}'
                '</span></q-td>'
            )
            tbl.add_slot(f"body-cell-{col_name}", slot_template)

        tbl.add_slot("body-cell-name", r"""
            <q-td key="name" :props="props"
                   :style="props.row.is_total ? 'background:var(--c-bg-hover);font-weight:700;' : ''">
                <span :class="props.row.is_total ? 'font-bold text-base' : (props.row.level === 2 ? 'pl-4 text-sm text-grey-6' : 'text-sm text-secondary')">
                    {{ props.row.name }}
                </span>
            </q-td>
        """)

        # 借贷平衡校验
        with ui.card_section().classes("py-2.5 px-4 bg-grey-50 border-t border-grey-2"):
            with ui.row().classes("justify-center gap-8 items-center text-sm"):
                ui.label("本期借方合计").style("color:var(--c-text-muted)")
                ui.label(f"¥{total['debit']:,.2f}").classes("font-bold tabular-nums").style("color:var(--c-success)")
                ui.label("本期贷方合计").classes("ml-4").style("color:var(--c-text-muted)")
                ui.label(f"¥{total['credit']:,.2f}").classes("font-bold tabular-nums").style("color:var(--c-danger)")
                if abs(total['debit'] - total['credit']) < 0.01:
                    ui.label("✅ 借贷平衡").classes("font-bold ml-4").style("color:var(--c-success)")
                else:
                    ui.label(f"❌ 差额 ¥{abs(total['debit']-total['credit']):,.2f}").classes("font-bold tabular-nums ml-4").style("color:var(--c-danger)")
