"""报表 — 科目余额表"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, render_kpi_cards
from app.services import LedgerService, ReportService


def render_accounts():
    """科目余额表 — 期间选择 + ui.table 严格列对齐，金额等宽，借贷分色"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # ── 期间选择器 ──
    with ui.row().classes("report-header"):
        ui.label("📊 科目余额表").classes("report-header__title")
        with ui.row().classes("report-header__actions"):
            years = [str(y) for y in range(2020, 2031)]
            months = [f"{m:02d}" for m in range(1, 13)]
            ui.select(years, value=str(state.selected_year), label="年度") \
                .classes("w-28").props("dense outlined") \
                .on_value_change(lambda e: (setattr(state, 'selected_year', int(e.value)), ui.navigate.to("/accounts")))
            ui.select(months, value=f"{state.selected_month:02d}", label="月份") \
                .classes("w-24").props("dense outlined") \
                .on_value_change(lambda e: (setattr(state, 'selected_month', int(e.value)), ui.navigate.to("/accounts")))

    balances = ReportService.get_account_balances(lid, state.selected_year, state.selected_month)

    # ── 空状态 ──
    if not balances:
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📋").classes("report-empty__icon")
                ui.label("暂无科目余额数据").classes("report-empty__text")
                ui.label("请检查所选期间是否有凭证数据").classes("report-empty__hint")
        return

    # ── 构建行数据 ──
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

    with ui.card().classes("report-card"):
        tbl = ui.table(columns=cols, rows=rows, row_key="name", pagination={"rowsPerPage": 50}).classes("w-full")

        for col_name in ["opening", "debit", "credit", "closing"]:
            slot_template = (
                '<q-td key="' + col_name + '" :props="props" class="tabular-nums text-sm"'
                ' :style="props.row.is_total ? \'background:var(--c-bg-subtotal);font-weight:700;\' : \'\'">'
                '<span :class="props.row.is_total ? \'font-bold\' : \'\'">'
                '{{ props.row.' + col_name + ' ? \'¥\' + props.row.' + col_name + '.toLocaleString(\'en-US\',{minimumFractionDigits:2,maximumFractionDigits:2}) : \'—\' }}'
                '</span></q-td>'
            )
            tbl.add_slot(f"body-cell-{col_name}", slot_template)

        tbl.add_slot("body-cell-name", r"""
            <q-td key="name" :props="props"
                   :style="props.row.is_total ? 'background:var(--c-bg-subtotal);font-weight:700;' : ''">
                <span :class="props.row.is_total ? 'font-bold text-base' : (props.row.level === 2 ? 'pl-4 text-sm text-grey-6' : 'text-sm text-secondary')">
                    {{ props.row.name }}
                </span>
            </q-td>
        """)

        # ── KPI 统计卡片 ──
        is_balanced = abs(total['debit'] - total['credit']) < 0.01
        kpis = [
            ("借方合计", total['debit'], "add_circle", "red", ""),
            ("贷方合计", total['credit'], "remove_circle", "green", ""),
        ]
        if is_balanced:
            kpis.append(("平衡状态", "✓ 平衡", "check_circle", "green", ""))
        else:
            diff = abs(total['debit'] - total['credit'])
            kpis.append(("差额", diff, "warning", "orange", "不平衡"))
        render_kpi_cards(kpis)
