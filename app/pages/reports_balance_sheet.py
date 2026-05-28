"""报表 — 资产负债表"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, show_toast, refresh_main, navigate
from app.components.ui_components import SectionHeader, KpiCard
from app.services import LedgerService, ReportService
from app.pages.reports_export import _export_balance_sheet, _export_balance_sheet_pdf

_YEAR_OPTS = {str(y): str(y) for y in range(2020, 2031)}
_MONTH_OPTS = {str(m): f"{m}月" for m in range(1, 13)}


def render_balance_sheet():
    """资产负债表 — 加载状态 + 双栏展示 + 导出 + 平衡校验"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0].get("id") if isinstance(ledgers[0], dict) else ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📗").classes("report-empty__icon")
                ui.label("请先创建账套").classes("report-empty__text")
        return

    page_container = ui.column().classes("w-full gap-3")

    # ── 头部 ──
    with page_container:
        with ui.row().classes("report-header"):
            ui.label("📗 资产负债表").classes("report-header__title")
            with ui.row().classes("report-header__actions"):
                year_sel = ui.select(options=_YEAR_OPTS, value=str(state.selected_year), label="年度") \
                    .props("dense outlined").classes("w-28")
                month_sel = ui.select(options=_MONTH_OPTS, value=str(state.selected_month), label="月份") \
                    .props("dense outlined").classes("w-24")
                ui.button("📥 Excel", color="green-7", on_click=lambda: _do_export_with_loading("excel")) \
                    .props("dense no-caps").classes("text-xs px-3")
                ui.button("📄 PDF", color="blue-7", on_click=lambda: _do_export_with_loading("pdf")) \
                    .props("dense no-caps").classes("text-xs px-3")
                compare_mode = ui.toggle(options={"mom": "环比", "yoy": "同比"}, value="mom") \
                    .props("dense")
                compare_mode.on("update:value", lambda e: _refresh_report())

    # ── Loading ──
    loading_area = ui.column().classes("w-full items-center py-10")
    with loading_area:
        ui.spinner("dots", size="lg", color="primary")
        ui.label("正在生成报表...").classes("text-sm mt-3").style("color:var(--c-text-muted)")

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
                with ui.card().classes("report-card"):
                    with ui.column().classes("report-empty"):
                        ui.label("⚠️").classes("report-empty__icon")
                        ui.label(f"加载失败: {e}").classes("report-empty__text").style("color:var(--c-danger)")
        finally:
            loading_area.set_visibility(False)

    def _on_period_change():
        state.selected_year = int(year_sel.value)
        state.selected_month = int(month_sel.value)
        _refresh_report()

    year_sel.on("update:value", lambda e: _on_period_change())
    month_sel.on("update:value", lambda e: _on_period_change())

    _refresh_report()


def _render_report_data(container, compare_mom):
    lid = state.selected_ledger_id
    bs = ReportService.get_balance_sheet(lid, state.selected_year, state.selected_month)
    if not bs:
        with container:
            with ui.card().classes("report-card"):
                with ui.column().classes("report-empty"):
                    ui.label("📋").classes("report-empty__icon")
                    ui.label("暂无资产负债表数据").classes("report-empty__text")
                    ui.label("请检查所选期间是否有凭证数据").classes("report-empty__hint")
        return

    # 对比期间
    if compare_mom == "mom":
        prev_month = state.selected_month - 1
        prev_year = state.selected_year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1
    else:
        prev_year = state.selected_year - 1
        prev_month = state.selected_month
    bs_prev = ReportService.get_balance_sheet(lid, prev_year, prev_month)
    if not bs_prev:
        bs_prev = {"assets": [], "liabilities": [], "equity": [], "total_assets": 0, "total_liab": 0, "total_equity": 0}

    ta = bs.get("total_assets", 0) if isinstance(bs, dict) else 0
    tl = bs.get("total_liab", 0) if isinstance(bs, dict) else 0
    te = bs.get("total_equity", 0) if isinstance(bs, dict) else 0
    net = ta - (tl + te)

    with container:
        # ── KPI ──
        with ui.row().classes("report-kpi-grid"):
            for label, value, color_class in [
                ("资产总计", ta, "report-kpi__value--success"),
                ("负债合计", tl, "report-kpi__value--danger"),
                ("所有者权益", te, "report-kpi__value--primary"),
                ("平衡差额", net, "report-kpi__value--success" if abs(net) < 0.01 else "report-kpi__value--danger"),
            ]:
                with ui.element("div").classes("report-kpi"):
                    ui.label(label).classes("report-kpi__label")
                    ui.label(format_amount(value)).classes(f"report-kpi__value {color_class}")
                    if label == "平衡差额":
                        ui.label("借贷平衡" if abs(net) < 0.01 else "不平衡").classes("report-kpi__hint")

        # ── 表格构建 ──
        def _build_bs_table(title, items, icon, color_var):
            rows_html = ""
            for item in items:
                name = item.get("name", "")
                end_val = item.get("end", 0)
                open_val = item.get("open", 0)
                level = item.get("level", 1)
                is_parent = level == 0
                indent = "" if is_parent else "padding-left:28px;"
                weight = "font-weight:700;" if is_parent else ""
                name_class = "tb-td-name" if is_parent else ""

                rows_html += f'''<tr class="tb-row">
                    <td class="tb-td {name_class}" style="{indent}{weight}">{name}</td>
                    <td class="tb-td tb-td-num">{format_amount(end_val)}</td>
                    <td class="tb-td tb-td-num">{format_amount(open_val)}</td>
                </tr>'''

            total_end = sum(float(i.get("end", 0) if i.get("end") is not None else 0) for i in items)
            total_open = sum(float(i.get("open", 0) if i.get("open") is not None else 0) for i in items)
            rows_html += f'''<tr class="tb-row tb-row-subtotal">
                <td class="tb-td tb-td-name">{title}合计</td>
                <td class="tb-td tb-td-num">{format_amount(total_end)}</td>
                <td class="tb-td tb-td-num">{format_amount(total_open)}</td>
            </tr>'''

            return f'''<table class="tb-table">
            <thead><tr>
                <th class="tb-th">{title}</th>
                <th class="tb-th tb-th-num">期末余额</th>
                <th class="tb-th tb-th-num">年初余额</th>
            </tr></thead>
            <tbody>{rows_html}</tbody></table>'''

        date_str = bs.get("date", "") if isinstance(bs, dict) else ""
        sections = [
            ("资产", bs.get("assets", []), "account_balance", "var(--c-success)"),
            ("负债", bs.get("liabilities", []), "credit_card", "var(--c-danger)"),
            ("所有者权益", bs.get("equity", []), "savings", "var(--c-primary)"),
        ]

        for title, items, icon, color in sections:
            with ui.card().classes("report-card"):
                with ui.row().classes("report-section__header px-5 pt-4 pb-0"):
                    ui.icon(icon).style(f"color:{color}")
                    ui.label(title).classes("report-section__title")
                    if date_str:
                        ui.label(f"— {date_str}").classes("text-xs").style("color:var(--c-text-muted)")
                with ui.card_section().classes("p-0"):
                    ui.html(_build_bs_table(title, items, icon, color), sanitize=False)

        # ── 平衡校验 ──
        is_balanced = abs(net) < 0.01
        with ui.row().classes("report-footer"):
            with ui.row().classes(f"report-footer__status {'report-footer__status--ok' if is_balanced else 'report-footer__status--error'}"):
                ui.label("✓" if is_balanced else "✗").classes("text-base")
                ui.label("资产 = 负债 + 所有者权益" if is_balanced else "不平衡")
            with ui.row().classes("gap-6 report-footer__detail"):
                ui.label(f"资产：{format_amount(ta)}")
                ui.label(f"负债：{format_amount(tl)}")
                ui.label(f"权益：{format_amount(te)}")
                if not is_balanced:
                    ui.label(f"差额：{format_amount(abs(net))}").style("color:var(--c-danger)")

        # ── 追溯 ──
        with ui.row().classes("report-nav"):
            ui.button("查看科目余额表", icon="grid_on",
                      on_click=lambda: navigate("trial_balance")).props("flat dense no-caps")
