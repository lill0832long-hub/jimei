"""报表 — 利润表"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import refresh_main, format_amount, navigate, render_kpi_cards
from app.services import LedgerService, ReportService
from app.pages.reports_export import _export_income_statement


def render_income_statement():
    """利润表 — 项目 | 本年累计 | 本月金额 | 同比变化"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📈").classes("report-empty__icon")
                ui.label("请先创建账套").classes("report-empty__text")
        return

    inc = ReportService.get_income_statement(lid, state.selected_year, state.selected_month) or {}
    inc_yoy = ReportService.get_income_statement(lid, state.selected_year - 1, state.selected_month) or {}

    # ── 头部 ──
    with ui.row().classes("report-header"):
        ui.label("📈 利润表").classes("report-header__title")
        with ui.row().classes("report-header__actions"):
            inc_year_sel = ui.select(
                options={str(y): str(y) for y in range(2020, 2031)},
                value=str(state.selected_year), label="年度"
            ).props("dense outlined").classes("w-28")
            inc_month_sel = ui.select(
                options={str(m): f"{m}月" for m in range(1, 13)},
                value=str(state.selected_month), label="月份"
            ).props("dense outlined").classes("w-24")
            ui.button("📥 Excel", color="green-7", on_click=lambda: _export_income_statement()) \
                .props("dense no-caps").classes("text-xs px-3")

            def _on_inc_period():
                state.selected_year = int(inc_year_sel.value)
                state.selected_month = int(inc_month_sel.value)
                refresh_main()

            inc_year_sel.on("update:value", lambda e: _on_inc_period())
            inc_month_sel.on("update:value", lambda e: _on_inc_period())

    # ── 空状态 ──
    if not inc or not inc.get("rows"):
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📋").classes("report-empty__icon")
                ui.label("暂无利润表数据").classes("report-empty__text")
                ui.label("请检查所选期间是否有凭证数据").classes("report-empty__hint")
        return

    # ── KPI 概览 ──
    date_str = inc.get("date", f"{state.selected_year}年{state.selected_month}月")
    total_revenue = sum(r.get("ytd", 0) or 0 for r in inc.get("rows", []) if r.get("type", "").startswith("rev"))
    total_expense = sum(r.get("ytd", 0) or 0 for r in inc.get("rows", []) if r.get("type", "").startswith("exp"))
    net_profit = total_revenue - total_expense

    kpis = [
        ("营业收入", total_revenue, "trending_up", "green", ""),
        ("营业成本", total_expense, "trending_down", "red", ""),
    ]
    if net_profit >= 0:
        kpis.append(("净利润", net_profit, "savings", "green", ""))
    else:
        kpis.append(("净利润", net_profit, "warning", "red", ""))
    render_kpi_cards(kpis)

    # ── 构建行数据 ──
    yoy_map = {r["name"]: r.get("ytd") for r in inc_yoy.get("rows", [])}
    rows = []
    for r in inc.get("rows", []):
        ytd_val = r.get("ytd")
        yoy_val = yoy_map.get(r["name"])
        yoy_pct = ((ytd_val - yoy_val) / abs(yoy_val) * 100) if (yoy_val and yoy_val != 0 and ytd_val is not None) else None
        row_type = r.get("type", "")
        is_net_profit = row_type == "total" or r["name"] == "净利润"
        net_val = r.get("ytd", 0) or 0

        rows.append({
            "name": r["name"], "code": r.get("code", "") or "",
            "ytd": format_amount(ytd_val) if ytd_val is not None else "—",
            "month": format_amount(r.get("month")) if r.get("month") is not None else "—",
            "yoy": format_amount(yoy_val) if yoy_val is not None else "—",
            "yoy_pct": f"{yoy_pct:+.1f}%" if yoy_pct is not None else "—",
            "yoy_pct_class": "yoy-up" if yoy_pct and yoy_pct > 0 else ("yoy-down" if yoy_pct and yoy_pct < 0 else "yoy-flat"),
            "type": row_type,
            "level": r.get("level", 0),
            "ytd_raw": ytd_val,
            "is_net_profit": is_net_profit,
            "net_negative": is_net_profit and net_val < 0,
        })

    # ── HTML 表格 ──
    rows_html = ""
    for r in rows:
        row_type = r.get("type", "")
        is_net = r.get("is_net_profit", False)
        is_item = row_type.endswith("_item")
        row_class = "tb-row-subtotal" if is_net else "tb-row"
        name_weight = "font-weight:700;" if (is_net or not is_item) else ""
        indent = "padding-left:28px;" if is_item else ""
        profit_color = "color:var(--c-danger);" if r.get("net_negative") else ""
        name_style = f"{name_weight}{indent}{profit_color}"
        yoy_pct_class = r.get("yoy_pct_class", "yoy-flat")

        rows_html += f'''<tr class="{row_class}">
            <td class="tb-td tb-td-name" style="{name_style}">{r["name"]}</td>
            <td class="tb-td tb-td-num">{r["ytd"]}</td>
            <td class="tb-td tb-td-num">{r["month"]}</td>
            <td class="tb-td tb-td-num">{r["yoy"]}</td>
            <td class="tb-td tb-td-num {yoy_pct_class}">{r["yoy_pct"]}</td>
        </tr>'''

    table_html = f'''<table class="tb-table">
    <thead><tr>
        <th class="tb-th">项目</th>
        <th class="tb-th tb-th-num">本年累计</th>
        <th class="tb-th tb-th-num">本月金额</th>
        <th class="tb-th tb-th-num">去年同期</th>
        <th class="tb-th tb-th-num">同比</th>
    </tr></thead>
    <tbody>{rows_html}</tbody></table>'''

    with ui.card().classes("report-card"):
        with ui.row().classes("report-section__header px-5 pt-4 pb-0"):
            ui.label(f"— {date_str}").classes("text-xs").style("color:var(--c-text-muted)")
        with ui.card_section().classes("p-0"):
            ui.html(table_html, sanitize=False)

    # ── 追溯 ──
    with ui.row().classes("report-nav"):
        ui.button("查看科目余额表", icon="grid_on",
                  on_click=lambda: navigate("trial_balance")).props("flat dense no-caps")
