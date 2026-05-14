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
        ui.label("请先创建账套").classes("text-sm").style("color:var(--c-text-muted)")
        return

    year, month = state.selected_year, state.selected_month

    # ── 顶部：期间选择 + 操作栏 ──
    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b").style("border-color:var(--c-border-light)"):
            with ui.row().classes("items-center justify-between w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("grid_on").style("color:var(--c-primary)")
                    ui.label("科目余额表").classes("text-base font-bold")
                    ui.label(f"{year}年{month}月").classes("text-sm ml-2").style("color:var(--c-text-muted)")
                with ui.row().classes("items-center gap-2"):
                    # 期间选择器
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

                    year_sel.on("update:model-value", lambda: _on_period_change())
                    month_sel.on("update:model-value", lambda: _on_period_change())

                    # 导出按钮
                    ui.button("导出Excel", icon="download", on_click=lambda: _export_excel(lid, year, month)).props("flat dense")

    # ── 获取数据 ──
    balances = ReportService.get_account_balances(lid, year, month)
    if not balances:
        with ui.card().classes("w-full mt-2"):
            EmptyState(icon="grid_on", message="暂无科目余额数据",
                      hint="请先录入记账凭证并过账",
                      action=lambda: navigate("journal"), action_label="去填凭证")
        return

    # ── 分类汇总 ──
    assets = []      # 资产类
    liabilities = [] # 负债类
    equity = []      # 权益类
    revenue = []     # 收入类
    expense = []     # 费用类

    for b in balances:
        cat = b.get("category", "")
        if cat == "资产":
            assets.append(b)
        elif cat == "负债":
            liabilities.append(b)
        elif cat == "权益":
            equity.append(b)
        elif cat == "收入":
            revenue.append(b)
        elif cat == "费用":
            expense.append(b)

    # ── 计算汇总 ──
    def _sum_field(items, field):
        return sum(float(b.get(field, 0) if b.get(field) is not None else 0) for b in items)

    total_opening = _sum_field(balances, "opening_balance")
    total_debit = _sum_field(balances, "period_debit")
    total_credit = _sum_field(balances, "period_credit")
    total_closing = _sum_field(balances, "closing_balance")
    diff = abs(total_debit - total_credit)

    # ── KPI 汇总卡片 ──
    with ui.row().classes("w-full gap-3 mt-2"):
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3"):
                ui.label("期初合计").classes("text-xs").style("color:var(--c-text-muted)")
                ui.label(format_amount(total_opening)).classes("text-lg font-bold tabular-nums")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3"):
                ui.label("本期借方合计").classes("text-xs").style("color:var(--c-text-muted)")
                ui.label(format_amount(total_debit)).classes("text-lg font-bold tabular-nums").style("color:var(--c-danger)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3"):
                ui.label("本期贷方合计").classes("text-xs").style("color:var(--c-text-muted)")
                ui.label(format_amount(total_credit)).classes("text-lg font-bold tabular-nums").style("color:var(--c-primary)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3"):
                ui.label("期末合计").classes("text-xs").style("color:var(--c-text-muted)")
                ui.label(format_amount(total_closing)).classes("text-lg font-bold tabular-nums")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3"):
                ui.label("借贷平衡校验").classes("text-xs").style("color:var(--c-text-muted)")
                if diff < 0.01:
                    ui.label("✅ 平衡").classes("text-lg font-bold").style("color:var(--c-success)")
                else:
                    ui.label(f"❌ 差额 {format_amount(diff)}").classes("text-lg font-bold").style("color:var(--c-danger)")

    # ── 分类展示表格 ──
    _CATEGORY_CONFIG = [
        ("资产类", assets, "account_balance", "blue"),
        ("负债类", liabilities, "credit_card", "red"),
        ("权益类", equity, "savings", "green"),
        ("收入类", revenue, "trending_up", "purple"),
        ("费用类", expense, "money_off", "orange"),
    ]

    for cat_name, cat_items, icon, color in _CATEGORY_CONFIG:
        if not cat_items:
            continue

        cat_open = _sum_field(cat_items, "opening_balance")
        cat_dr = _sum_field(cat_items, "period_debit")
        cat_cr = _sum_field(cat_items, "period_credit")
        cat_close = _sum_field(cat_items, "closing_balance")

        with ui.card().classes("w-full mt-2"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center justify-between"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon(icon).style(f"color:var(--c-{color})")
                        ui.label(cat_name).classes("text-sm font-semibold")
                    with ui.row().classes("items-center gap-4 text-xs"):
                        ui.label(f"小计: {format_amount(cat_close)}").style("color:var(--c-text-secondary)")

            # HTML 表格
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
                    <td class="tb-td tb-td-num" style="color:var(--c-danger)">{format_amount(debit) if debit else "—"}</td>
                    <td class="tb-td tb-td-num" style="color:var(--c-primary)">{format_amount(credit) if credit else "—"}</td>
                    <td class="tb-td tb-td-num" style="font-weight:600">{format_amount(closing) if closing else "—"}</td>
                </tr>'''

            # 小计行
            rows_html += f'''<tr class="tb-row tb-row-subtotal">
                <td class="tb-td" colspan="2" style="text-align:center;font-weight:700">小计</td>
                <td class="tb-td tb-td-num" style="font-weight:700">{format_amount(cat_open)}</td>
                <td class="tb-td tb-td-num" style="font-weight:700;color:var(--c-danger)">{format_amount(cat_dr)}</td>
                <td class="tb-td tb-td-num" style="font-weight:700;color:var(--c-primary)">{format_amount(cat_cr)}</td>
                <td class="tb-td tb-td-num" style="font-weight:700">{format_amount(cat_close)}</td>
            </tr>'''

            table_html = f'''<table class="tb-table" id="tb_{cat_name}">
            <thead>
                <tr>
                    <th class="tb-th tb-th-code">科目代码</th>
                    <th class="tb-th tb-th-name">科目名称</th>
                    <th class="tb-th tb-th-num">期初余额</th>
                    <th class="tb-th tb-th-num">本期借方</th>
                    <th class="tb-th tb-th-num">本期贷方</th>
                    <th class="tb-th tb-th-num">期末余额</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
            </table>'''

            with ui.card_section().classes("p-0"):
                ui.html(table_html, sanitize=False)

    # ── 总计行 ──
    with ui.card().classes("w-full mt-2"):
        with ui.card_section().classes("py-2 px-3"):
            with ui.row().classes("items-center justify-between"):
                ui.label("全部科目合计").classes("text-sm font-bold")
                with ui.row().classes("items-center gap-6 text-sm"):
                    ui.label(f"期初: {format_amount(total_opening)}").classes("tabular-nums")
                    ui.label(f"借方: {format_amount(total_debit)}").classes("tabular-nums").style("color:var(--c-danger)")
                    ui.label(f"贷方: {format_amount(total_credit)}").classes("tabular-nums").style("color:var(--c-primary)")
                    ui.label(f"期末: {format_amount(total_closing)}").classes("tabular-nums font-bold")

    # ── 导航追溯 ──
    with ui.row().classes("w-full gap-2 mt-2 justify-end"):
        ui.button("查看资产负债表", icon="balance", on_click=lambda: navigate("balance_sheet")).props("flat dense")
        ui.button("查看利润表", icon="assessment", on_click=lambda: navigate("income_statement")).props("flat dense")
        ui.button("查看现金流量表", icon="swap_horiz", on_click=lambda: navigate("cash_flow_statement")).props("flat dense")

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
