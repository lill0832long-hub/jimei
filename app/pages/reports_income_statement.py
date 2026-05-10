"""报表 — 利润表"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import refresh_main
from app.services import LedgerService, ReportService
from app.pages.reports_export import _export_income_statement


def render_income_statement():
    """利润表 — 项目 | 行次 | 本年累计 | 本月金额 | 同比变化"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    inc = ReportService.get_income_statement(lid, state.selected_year, state.selected_month)
    inc_yoy = ReportService.get_income_statement(lid, state.selected_year - 1, state.selected_month)

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2 px-4 border-b border-grey-2").style("color:var(--c-bg-hover)"):
            with ui.row().classes("items-center gap-3"):
                ui.label("📈 利润表").classes("text-base font-bold")
                ui.separator().props("vertical")
                inc_year_sel = ui.select(options=list(range(2020,2031)), value=state.selected_year, label="年度") \
                    .props("dense outlined").classes("w-28")
                inc_month_sel = ui.select(options=list(range(1,13)), value=state.selected_month, label="月份") \
                    .props("dense outlined").classes("w-24")
                ui.separator().props("vertical")
                ui.button("📥 导出Excel", color="green", on_click=lambda: _export_income_statement()) \
                    .props("dense").classes("text-xs")

                def _on_inc_period():
                    state.selected_year = inc_year_sel.value
                    state.selected_month = inc_month_sel.value
                    refresh_main()

                inc_year_sel.on("update:value", lambda e: _on_inc_period())
                inc_month_sel.on("update:value", lambda e: _on_inc_period())

        with ui.card_section().classes("py-1.5 px-4 border-b").style("border-color:var(--c-border);background:var(--c-bg-hover)"):
            ui.label(f"📈 利润表 — {inc['date']}").classes("text-sm font-semibold").style("color:var(--c-text-secondary)")

        cols = [
            {"name":"name","label":"项 目","field":"name","align":"left","headerClasses":"table-header-cell text-uppercase"},
            {"name":"code","label":"行次","field":"code","align":"center","headerClasses":"table-header-cell text-uppercase"},
            {"name":"ytd","label":"本年累计","field":"ytd","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell text-uppercase"},
            {"name":"month","label":"本月金额","field":"month","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell text-uppercase"},
            {"name":"yoy","label":"去年同期","field":"yoy","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell text-uppercase"},
            {"name":"yoy_pct","label":"同比%","field":"yoy_pct","align":"right","classes":"tabular-nums text-xs","headerClasses":"table-header-cell text-uppercase","style":"width:72px"},
        ]
        yoy_map = {r["name"]: r.get("ytd") for r in inc_yoy["rows"]}
        rows = []
        for r in inc["rows"]:
            ytd_val = r.get("ytd")
            yoy_val = yoy_map.get(r["name"])
            yoy_pct = ((ytd_val - yoy_val) / abs(yoy_val) * 100) if (yoy_val and ytd_val is not None) else None
            rows.append({
                "name": r["name"], "code": r.get("code", "") or "",
                "ytd": ytd_val, "month": r.get("month"),
                "yoy": yoy_val, "yoy_pct": yoy_pct,
                "type": r.get("type", ""), "level": r.get("level", 0)
            })

        tbl = ui.table(columns=cols, rows=rows, row_key="name", pagination=False).classes("w-full")

        tbl.add_slot("body-cell-name", r"""
            <q-td key="name" :props="props">
                <span :class="{
                    'font-bold': ['header','rev_total','expense_header','revenue_header','subtotal','total'].includes(props.row.type),
                    'font-bold': props.row.type === 'expense_header',
                    'font-bold': props.row.type === 'revenue_header',
                    'pl-4': props.row.level === 1,
                    'pl-8': props.row.level === 2,
                }" :style="['subtotal','total','rev_total'].includes(props.row.type) ? 'background:var(--c-bg-hover);' : ''">
                    {{ props.row.name }}
                </span>
            </q-td>
        """)
        tbl.add_slot("body-cell-ytd", r"""
            <q-td key="ytd" :props="props" class="tabular-nums"
                  :style="['subtotal','total','rev_total'].includes(props.row.type) ? 'background:var(--c-bg-hover);' : ''">
                <span :class="{
                    'font-bold': ['header','rev_total','expense_header','revenue_header','subtotal','total'].includes(props.row.type),
                    'font-bold': props.row.ytd < 0,
                }">
                    {{ props.row.ytd !== null ? '¥' + (props.row.ytd < 0 ? '(' + Math.abs(props.row.ytd).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) + ')' : props.row.ytd.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})) : '—' }}
                </span>
            </q-td>
        """)
        tbl.add_slot("body-cell-month", r"""
            <q-td key="month" :props="props" class="tabular-nums"
                  :style="['subtotal','total','rev_total'].includes(props.row.type) ? 'background:var(--c-bg-hover);' : ''">
                <span :class="{
                    'font-bold': ['header','rev_total','expense_header','revenue_header','subtotal','total'].includes(props.row.type),
                    'font-bold': props.row.month < 0,
                }">
                    {{ props.row.month !== null ? '¥' + (props.row.month < 0 ? '(' + Math.abs(props.row.month).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) + ')' : props.row.month.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})) : '—' }}
                </span>
            </q-td>
        """)
        tbl.add_slot("body-cell-code", r"""
            <q-td key="code" :props="props" class="text-muted text-xs font-mono tabular-nums">
                {{ props.row.code }}
            </q-td>
        """)
