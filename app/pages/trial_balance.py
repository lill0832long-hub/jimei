"""科目余额表 — 会计主线核心中间环节"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, show_toast, navigate, refresh_main
from app.components.ui_components import SectionHeader, EmptyState
from app.services import LedgerService, ReportService


def render_trial_balance():
    """科目余额表 — 从凭证汇总，为报表提供数据源"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0].get("id") if isinstance(ledgers[0], dict) else ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📊").classes("report-empty__icon")
                ui.label("请先创建账套").classes("report-empty__text")
        return

    year, month = state.selected_year, state.selected_month

    # ── 头部 ──
    with ui.row().classes("report-header"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("grid_on").style("color:var(--c-primary)")
            ui.label("科目余额表").classes("report-header__title")
            ui.label(f"{year}年{month}月").classes("report-header__subtitle")
        with ui.row().classes("report-header__actions"):
            year_sel = ui.select(
                {str(y): str(y) for y in range(2020, 2031)},
                value=str(year), label="年"
            ).props("outlined dense").classes("w-24")
            month_sel = ui.select(
                {str(m): f"{m}月" for m in range(1, 13)},
                value=str(month), label="月"
            ).props("outlined dense").classes("w-20")

            def _on_period_change():
                state.selected_year = int(year_sel.value)
                state.selected_month = int(month_sel.value)
                refresh_main()

            year_sel.on("update:value", lambda: _on_period_change())
            month_sel.on("update:value", lambda: _on_period_change())
            ui.button("导出Excel", icon="download",
                      on_click=lambda: _export_excel(lid, year, month)).props("flat dense no-caps")

    # ── 获取数据 ──
    balances = ReportService.get_account_balances(lid, year, month)
    if not balances:
        with ui.card().classes("report-card"):
            EmptyState(icon="grid_on", message="暂无科目余额数据",
                      hint="请先录入记账凭证并过账",
                      action=lambda: navigate("journal"), action_label="去填凭证")
        return

    # ── 分类汇总 ──
    assets, liabilities, equity, revenue, expense = [], [], [], [], []
    for b in balances:
        cat = b.get("category", "")
        if cat == "资产": assets.append(b)
        elif cat == "负债": liabilities.append(b)
        elif cat == "权益": equity.append(b)
        elif cat == "收入": revenue.append(b)
        elif cat == "费用": expense.append(b)

    def _sum_field(items, field):
        return sum(float(b.get(field, 0) if b.get(field) is not None else 0) for b in items)

    total_opening = _sum_field(balances, "opening_balance")
    total_debit = _sum_field(balances, "period_debit")
    total_credit = _sum_field(balances, "period_credit")
    total_closing = _sum_field(balances, "closing_balance")
    diff = abs(total_debit - total_credit)

    # ── KPI 卡片 ──
    with ui.row().classes("report-kpi-grid"):
        kpis = [
            ("期初合计", total_opening, ""),
            ("本期借方", total_debit, "report-kpi__value--danger"),
            ("本期贷方", total_credit, "report-kpi__value--primary"),
            ("期末合计", total_closing, ""),
        ]
        for label, value, color_class in kpis:
            with ui.element("div").classes("report-kpi"):
                ui.label(label).classes("report-kpi__label")
                ui.label(format_amount(value)).classes(f"report-kpi__value {color_class}")
        # 平衡校验单独一个
        with ui.element("div").classes("report-kpi"):
            ui.label("借贷平衡").classes("report-kpi__label")
            if diff < 0.01:
                ui.label("✓ 平衡").classes("report-kpi__value report-kpi__value--success")
            else:
                ui.label(f"✗ 差额 {format_amount(diff)}").classes("report-kpi__value report-kpi__value--danger")

    # ── 分类展示表格 ──
    _CATEGORY_CONFIG = [
        ("资产类", assets, "account_balance", "var(--c-success)"),
        ("负债类", liabilities, "credit_card", "var(--c-danger)"),
        ("权益类", equity, "savings", "var(--c-primary)"),
        ("收入类", revenue, "trending_up", "#9333ea"),
        ("费用类", expense, "money_off", "#ea580c"),
    ]

    for cat_name, cat_items, icon, color in _CATEGORY_CONFIG:
        if not cat_items:
            continue

        cat_open = _sum_field(cat_items, "opening_balance")
        cat_dr = _sum_field(cat_items, "period_debit")
        cat_cr = _sum_field(cat_items, "period_credit")
        cat_close = _sum_field(cat_items, "closing_balance")

        with ui.card().classes("report-card"):
            with ui.row().classes("report-section__header px-5 pt-4 pb-2"):
                ui.icon(icon).style(f"color:{color}")
                ui.label(cat_name).classes("report-section__title")
                ui.label(f"{len(cat_items)} 个科目").classes("report-section__count")
                ui.space()
                ui.label(f"小计 {format_amount(cat_close)}").classes("text-xs font-semibold").style("color:var(--c-text-muted)")

            rows_html = ""
            for b in cat_items:
                code = b.get("account_code", "")
                name = b.get("account_name", "")
                opening = float(b.get("opening_balance", 0) if b.get("opening_balance") is not None else 0)
                debit = float(b.get("period_debit", 0) if b.get("period_debit") is not None else 0)
                credit = float(b.get("period_credit", 0) if b.get("period_credit") is not None else 0)
                closing = float(b.get("closing_balance", 0) if b.get("closing_balance") is not None else 0)

                rows_html += f'''<tr class="tb-row" onclick="navigateToAccount('{code}')">
                    <td class="tb-td tb-td-code">{code}</td>
                    <td class="tb-td tb-td-name">{name}</td>
                    <td class="tb-td tb-td-num">{format_amount(opening) if opening else "—"}</td>
                    <td class="tb-td tb-td-num amount-negative">{format_amount(debit) if debit else "—"}</td>
                    <td class="tb-td tb-td-num amount-positive">{format_amount(credit) if credit else "—"}</td>
                    <td class="tb-td tb-td-num" style="font-weight:600">{format_amount(closing) if closing else "—"}</td>
                </tr>'''

            rows_html += f'''<tr class="tb-row tb-row-subtotal">
                <td class="tb-td tb-td-name" colspan="2">小计</td>
                <td class="tb-td tb-td-num">{format_amount(cat_open)}</td>
                <td class="tb-td tb-td-num amount-negative">{format_amount(cat_dr)}</td>
                <td class="tb-td tb-td-num amount-positive">{format_amount(cat_cr)}</td>
                <td class="tb-td tb-td-num">{format_amount(cat_close)}</td>
            </tr>'''

            table_html = f'''<table class="tb-table">
            <thead><tr>
                <th class="tb-th">科目代码</th>
                <th class="tb-th">科目名称</th>
                <th class="tb-th tb-th-num">期初余额</th>
                <th class="tb-th tb-th-num">本期借方</th>
                <th class="tb-th tb-th-num">本期贷方</th>
                <th class="tb-th tb-th-num">期末余额</th>
            </tr></thead>
            <tbody>{rows_html}</tbody></table>'''

            with ui.card_section().classes("p-0"):
                ui.html(table_html, sanitize=False)

    # ── 总计 footer ──
    with ui.row().classes("report-footer"):
        ui.label("全部科目合计").classes("font-bold text-sm")
        with ui.row().classes("gap-6 report-footer__detail"):
            ui.label(f"期初 {format_amount(total_opening)}")
            ui.label(f"借方 {format_amount(total_debit)}")
            ui.label(f"贷方 {format_amount(total_credit)}")
            ui.label(f"期末 {format_amount(total_closing)}")

    # ── 导航追溯 ──
    with ui.row().classes("report-nav"):
        ui.button("资产负债表", icon="balance", on_click=lambda: navigate("balance_sheet")).props("flat dense no-caps")
        ui.button("利润表", icon="assessment", on_click=lambda: navigate("income_statement")).props("flat dense no-caps")
        ui.button("现金流量表", icon="swap_horiz", on_click=lambda: navigate("cash_flow_statement")).props("flat dense no-caps")

    # ── 科目钻取 JS ──
    ui.add_head_html('''<script>
    function navigateToAccount(code) {
        window.dispatchEvent(new CustomEvent('account-drilldown', {detail: code}));
    }
    </script>''')


def _export_excel(ledger_id, year, month):
    """导出科目余额表为 Excel"""
    try:
        import os
        from datetime import datetime
        balances = ReportService.get_account_balances(ledger_id, year, month)
        if not balances:
            show_toast("无数据可导出", "warning")
            return

        export_dir = os.path.join(os.path.dirname(__file__), "..", "exports")
        os.makedirs(export_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fpath = os.path.join(export_dir, f"科目余额表_{year}{month:02d}_{ts}.xlsx")

        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "科目余额表"

        headers = ["科目代码", "科目名称", "类别", "期初余额", "本期借方", "本期贷方", "期末余额"]
        ws.append(headers)

        thin = Side(style="thin", color="E5E7EB")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF", size=11)
            cell.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
            cell.border = border

        for b in balances:
            ws.append([
                b.get("account_code", ""),
                b.get("account_name", ""),
                b.get("category", ""),
                float(b.get("opening_balance", 0) if b.get("opening_balance") is not None else 0),
                float(b.get("period_debit", 0) if b.get("period_debit") is not None else 0),
                float(b.get("period_credit", 0) if b.get("period_credit") is not None else 0),
                float(b.get("closing_balance", 0) if b.get("closing_balance") is not None else 0),
            ])

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            for cell in row:
                cell.border = border

        wb.save(fpath)
        show_toast(f"导出成功: {fpath}", "success")
    except Exception as e:
        show_toast(f"导出失败: {e}", "error")
