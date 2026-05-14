"""报表 — 利润表"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import refresh_main, format_amount
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
                inc_year_sel = ui.select(
                    options={str(y): str(y) for y in range(2020, 2031)},
                    value=str(state.selected_year), label="年度"
                ).props("dense outlined").classes("w-28")
                inc_month_sel = ui.select(
                    options={str(m): f"{m}月" for m in range(1, 13)},
                    value=str(state.selected_month), label="月份"
                ).props("dense outlined").classes("w-24")
                ui.separator().props("vertical")
                ui.button("📥 导出Excel", color="green", on_click=lambda: _export_income_statement()) \
                    .props("dense").classes("text-xs")

                def _on_inc_period():
                    state.selected_year = int(inc_year_sel.value)
                    state.selected_month = int(inc_month_sel.value)
                    refresh_main()

                inc_year_sel.on("update:value", lambda e: _on_inc_period())
                inc_month_sel.on("update:value", lambda e: _on_inc_period())

        with ui.card_section().classes("py-1.5 px-4 border-b").style("border-color:var(--c-border);background:var(--c-bg-hover)"):
            ui.label(f"📈 利润表 — {inc['date']}").classes("text-sm font-semibold").style("color:var(--c-text-secondary)")

        yoy_map = {r["name"]: r.get("ytd") for r in inc_yoy.get("rows", [])}
        rows = []
        for r in inc.get("rows", []):
            ytd_val = r.get("ytd")
            yoy_val = yoy_map.get(r["name"])
            yoy_pct = ((ytd_val - yoy_val) / abs(yoy_val) * 100) if (yoy_val and ytd_val is not None) else None
            # 净利润亏损标红
            row_type = r.get("type", "")
            is_net_profit = row_type == "total" or r["name"] == "净利润"
            net_val = r.get("ytd", 0) or 0
            profit_color = "var(--c-danger)" if is_net_profit and net_val < 0 else ""
            rows.append({
                "name": r["name"], "code": r.get("code", "") or "",
                "ytd": format_amount(ytd_val) if ytd_val is not None else "—",
                "month": format_amount(r.get("month")) if r.get("month") is not None else "—",
                "yoy": format_amount(yoy_val) if yoy_val is not None else "—",
                "yoy_pct": f"{yoy_pct:+.1f}%" if yoy_pct is not None else "—",
                "type": row_type,
                "level": r.get("level", 0),
                "ytd_raw": ytd_val,
                "profit_color": profit_color,
            })

        # ── HTML 表格渲染 ──
        rows_html = ""
        for r in rows:
            row_type = r.get("type", "")
            is_net = row_type == "total" or r["name"] == "净利润"
            is_item = row_type.endswith("_item")
            row_class = "tb-row-subtotal" if is_net else ("tb-row" if is_item else "")
            profit_color = r.get("profit_color", "")
            name_style = f"font-weight:700;{profit_color}" if is_net else ("padding-left:24px;" if is_item else "font-weight:600;")
            ytd_val = r.get("ytd_raw")
            ytd_display = format_amount(ytd_val) if ytd_val is not None else "—"
            month_val = r.get("month")
            month_display = format_amount(month_val) if month_val is not None else "—"
            yoy_display = r.get("yoy", "—")
            yoy_pct = r.get("yoy_pct", "—")

            rows_html += f'''<tr class="tb-row {row_class}">
                <td class="tb-td" style="{name_style}">{r["name"]}</td>
                <td class="tb-td tb-td-num">{ytd_display}</td>
                <td class="tb-td tb-td-num">{month_display}</td>
                <td class="tb-td tb-td-num">{yoy_display}</td>
                <td class="tb-td tb-td-num">{yoy_pct}</td>
            </tr>'''

        table_html = f'''<table class="tb-table" id="tb_income">
        <thead>
            <tr>
                <th class="tb-th" style="text-align:left">项目</th>
                <th class="tb-th tb-th-num">本年累计</th>
                <th class="tb-th tb-th-num">本月金额</th>
                <th class="tb-th tb-th-num">去年同期</th>
                <th class="tb-th tb-th-num">同比</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
        </table>'''

        with ui.card_section().classes("p-0"):
            ui.html(table_html, sanitize=False)

    # ── 追溯按钮 ──
    with ui.row().classes("w-full gap-2 mt-2 justify-end"):
        ui.button("查看科目余额表", icon="grid_on",
                  on_click=lambda: navigate("trial_balance")).props("flat dense")
