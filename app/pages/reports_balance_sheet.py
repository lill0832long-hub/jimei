"""报表 — 资产负债表 (优化版)"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, show_toast, refresh_main, navigate
from app.components.ui_components import SectionHeader, KpiCard
from app.services import LedgerService, ReportService
from app.pages.reports_export import _export_balance_sheet, _export_balance_sheet_pdf

# 期间选择器选项
_YEAR_OPTS = {str(y): str(y) for y in range(2020, 2031)}
_MONTH_OPTS = {str(m): f"{m}月" for m in range(1, 13)}


def render_balance_sheet():
    """资产负债表 — 加载状态 + format_amount + 双栏展示 + 导出"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0].get("id") if isinstance(ledgers[0], dict) else ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        ui.label("请先创建账套").classes("text-sm").style("color:var(--c-text-muted)")
        return

    # ── 页面容器（用于 loading 替换）──
    page_container = ui.column().classes("w-full gap-3")

    # ── 顶部期间选择器 ──
    with page_container:
        with ui.card().classes("w-full"):
            with ui.card_section().classes("py-2 px-4 border-b border-grey-2").style("color:var(--c-bg-hover)"):
                with ui.row().classes("items-center gap-3"):
                    ui.label("📗 资产负债表").classes("text-base font-bold")
                    ui.separator().props("vertical")
                    year_sel = ui.select(
                        options=_YEAR_OPTS,
                        value=str(state.selected_year),
                        label="年度"
                    ).props("dense outlined").classes("w-28")
                    month_sel = ui.select(
                        options=_MONTH_OPTS,
                        value=str(state.selected_month),
                        label="月份"
                    ).props("dense outlined").classes("w-24")
                    ui.separator().props("vertical")
                    ui.button("📥 导出Excel", color="green", on_click=lambda: _do_export_with_loading("excel")) \
                        .props("dense").classes("text-xs")
                    ui.button("📄 导出PDF", color="blue", on_click=lambda: _do_export_with_loading("pdf")) \
                        .props("dense").classes("text-xs")
                    ui.separator().props("vertical")
                    compare_mode = ui.toggle(
                        options={"mom": "环比", "yoy": "同比"},
                        value="mom"
                    ).props("dense").classes("text-xs")

    # ── Loading 状态 ──
    loading_area = ui.column().classes("w-full items-center py-8")
    with loading_area:
        ui.spinner("dots", size="lg", color="primary")
        ui.label("正在生成报表...").classes("text-sm mt-2").style("color:var(--c-text-muted)")

    report_area = ui.column().classes("w-full gap-3")

    def _do_export_with_loading(fmt):
        try:
            if fmt == "excel":
                _export_balance_sheet()
            else:
                _export_balance_sheet_pdf()
        except Exception as e:
            show_toast(f"导出失败: {e}", "error")

    def _refresh_report():
        loading_area.set_visibility(True)
        report_area.clear()
        try:
            _render_report_data(report_area, compare_mode.value)
        except Exception as e:
            with report_area:
                ui.label(f"加载失败: {e}").classes("text-sm text-center").style("color:var(--c-danger)")
        finally:
            loading_area.set_visibility(False)

    def _on_period_change():
        state.selected_year = int(year_sel.value)
        state.selected_month = int(month_sel.value)
        _refresh_report()

    year_sel.on("update:value", lambda e: _on_period_change())
    month_sel.on("update:value", lambda e: _on_period_change())

    # 初始加载
    _refresh_report()


def _render_report_data(container, compare_mom):
    """渲染报表数据（在 loading 之后调用）"""
    lid = state.selected_ledger_id
    bs = ReportService.get_balance_sheet(lid, state.selected_year, state.selected_month)
    if not bs:
        with container:
            ui.label("暂无数据").classes("text-sm text-center py-6").style("color:var(--c-text-muted)")
        return

    # 获取对比期间数据
    if compare_mom == "mom":
        prev_month = state.selected_month - 1
        prev_year = state.selected_year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1
        label_prev = f"{prev_year}年{prev_month}月"
    else:
        prev_year = state.selected_year - 1
        prev_month = state.selected_month
        label_prev = f"{prev_year}年{prev_month}月"
    bs_prev = ReportService.get_balance_sheet(lid, prev_year, prev_month)
    if not bs_prev:
        bs_prev = {"assets": [], "liabilities": [], "equity": [], "total_assets": 0, "total_liab": 0, "total_equity": 0}

    with container:
        # ── KPI 概览 ──
        ta = bs.get("total_assets", 0) if isinstance(bs, dict) else 0
        tl = bs.get("total_liab", 0) if isinstance(bs, dict) else 0
        te = bs.get("total_equity", 0) if isinstance(bs, dict) else 0
        net = ta - (tl + te)
        with ui.row().classes("w-full gap-3"):
            KpiCard("资产总计", format_amount(ta), "account_balance", "green")
            KpiCard("负债合计", format_amount(tl), "assignment", "red")
            KpiCard("所有者权益", format_amount(te), "shield", "blue")
            KpiCard("平衡差额", format_amount(net), "balance", "green" if abs(net) < 0.01 else "red")

        # ── HTML 表格渲染 ──
        def _build_bs_table(title, items, icon, color):
            rows_html = ""
            for item in items:
                name = item.get("name", "")
                end_val = item.get("end", 0)
                open_val = item.get("open", 0)
                level = item.get("level", 1)
                is_parent = level == 0
                indent = "" if is_parent else "padding-left:24px;"
                weight = "font-weight:600;" if is_parent else ""

                rows_html += f'''<tr class="tb-row">
                    <td class="tb-td" style="{indent}{weight}">{name}</td>
                    <td class="tb-td tb-td-num">{format_amount(end_val)}</td>
                    <td class="tb-td tb-td-num">{format_amount(open_val)}</td>
                </tr>'''

            # 小计行
            total_end = sum(float(i.get("end", 0) if i.get("end") is not None else 0) for i in items)
            total_open = sum(float(i.get("open", 0) if i.get("open") is not None else 0) for i in items)
            rows_html += f'''<tr class="tb-row tb-row-subtotal">
                <td class="tb-td" style="text-align:center;font-weight:700">{title}合计</td>
                <td class="tb-td tb-td-num" style="font-weight:700">{format_amount(total_end)}</td>
                <td class="tb-td tb-td-num" style="font-weight:700">{format_amount(total_open)}</td>
            </tr>'''

            return f'''<table class="tb-table">
            <thead>
                <tr>
                    <th class="tb-th" style="text-align:left">{title}</th>
                    <th class="tb-th tb-th-num">期末余额</th>
                    <th class="tb-th tb-th-num">年初余额</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
            </table>'''

        date_str = bs.get("date", "") if isinstance(bs, dict) else ""

        # 资产
        with ui.card().classes("w-full"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("account_balance").style("color:var(--c-success)")
                    ui.label("资产").classes("text-sm font-semibold")
                    ui.label(f"— {date_str}").classes("text-xs").style("color:var(--c-text-muted)")
            with ui.card_section().classes("p-0"):
                ui.html(_build_bs_table("资产", bs.get("assets", []), "account_balance", "blue"), sanitize=False)

        # 负债
        with ui.card().classes("w-full mt-2"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("credit_card").style("color:var(--c-danger)")
                    ui.label("负债").classes("text-sm font-semibold")
            with ui.card_section().classes("p-0"):
                ui.html(_build_bs_table("负债", bs.get("liabilities", []), "credit_card", "red"), sanitize=False)

        # 所有者权益
        with ui.card().classes("w-full mt-2"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("savings").style("color:var(--c-primary)")
                    ui.label("所有者权益").classes("text-sm font-semibold")
            with ui.card_section().classes("p-0"):
                ui.html(_build_bs_table("所有者权益", bs.get("equity", []), "savings", "green"), sanitize=False)

        # ── 平衡校验 ──
        with ui.card().classes("w-full"):
            with ui.card_section().classes("py-3 px-4"):
                diff = abs(ta - (tl + te))
                with ui.row().classes("justify-center gap-4 items-center text-sm"):
                    for lbl, val, clr in [("资产总计", ta, "text-success"), ("负债合计", tl, "text-danger"), ("所有者权益", te, "text-primary")]:
                        ui.label(lbl).style("color:var(--c-text-muted)")
                        ui.label(format_amount(val)).classes(f"{clr} font-bold tabular-nums text-base")
                    if diff < 0.01:
                        ui.label("✅ 平衡").classes("font-bold ml-2").style("color:var(--c-success)")
                    else:
                        ui.label(f"❌ 差额 {format_amount(diff)}").classes("font-bold tabular-nums ml-2").style("color:var(--c-danger)")

        # ── 追溯按钮 ──
        with ui.row().classes("w-full gap-2 mt-2 justify-end"):
            ui.button("查看科目余额表", icon="grid_on",
                      on_click=lambda: navigate("trial_balance")).props("flat dense")
