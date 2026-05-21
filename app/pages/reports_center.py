"""报表中心 — 统一标签页入口"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, show_toast, refresh_main, drill_down_to_account, drill_down_to_voucher
from app.services import LedgerService, ReportService

# 子报表配置：key -> (标签名, 图标)
_REPORT_TABS = [
    ("trial_balance",    "试算平衡表", "grid_on"),
    ("balance_sheet",    "资产负债表", "account_balance"),
    ("income_statement", "利润表",     "trending_up"),
    ("accounts",         "科目余额表", "bar_chart"),
    ("charts",           "图表分析",   "show_chart"),
    ("close_period",     "期末结转",   "sync_alt"),
]


def render_reports_center():
    """报表中心主页 — 全局期间选择器 + 子报表标签页"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📊").classes("report-empty__icon")
                ui.label("请先创建账套").classes("report-empty__text")
        return

    # ── 全局期间选择器 ──
    with ui.row().classes("w-full items-center justify-between"):
        # 左侧：标题
        ui.label("📊 报表中心").classes("text-base font-bold")
        # 右侧：筛选控件
        with ui.row().classes("items-center gap-2"):
            year_sel = ui.select(
                {str(y): str(y) for y in range(2020, 2031)},
                value=str(state.selected_year), label="年度"
            ).props("outlined dense").classes("w-28")
            month_sel = ui.select(
                {str(m): f"{m}月" for m in range(1, 13)},
                value=str(state.selected_month), label="月份"
            ).props("outlined dense").classes("w-24")
            ui.button("刷新", icon="refresh", color="primary",
                      on_click=lambda: _refresh_all()).props("dense no-caps")

            def _on_period_change():
                state.selected_year = int(year_sel.value)
                state.selected_month = int(month_sel.value)
                _refresh_all()

            year_sel.on("update:value", lambda e: _on_period_change())
            month_sel.on("update:value", lambda e: _on_period_change())

    # ── 报表钻取 JS → Python 桥接 ──
    # 使用 ui.run_javascript 定时轮询 JS 变量
    _drill_poll_active = [True]  # 使用 list 以便在闭包中修改

    async def _poll_drill():
        """每 500ms 轮询一次 JS 变量（仅当前页面是 reports_center 时运行）"""
        # 页面离开后自动停止
        if state.current_page != "reports_center":
            _drill_poll_active[0] = False
            return
        if not _drill_poll_active[0]:
            return
        try:
            acc = await ui.run_javascript("window._drillAccountCode||''", timeout=3)
            if acc:
                await ui.run_javascript("window._drillAccountCode=''", timeout=2)
                _drill_poll_active[0] = False
                drill_down_to_account(acc)
                return
        except Exception:
            pass
        try:
            vno = await ui.run_javascript("window._drillVoucherNo||''", timeout=3)
            if vno:
                await ui.run_javascript("window._drillVoucherNo=''", timeout=2)
                _drill_poll_active[0] = False
                drill_down_to_voucher(vno)
                return
        except Exception:
            pass
        if _drill_poll_active[0]:
            ui.timer(0.5, _poll_drill, once=True)

    ui.add_head_html('''<script>
    window._drillAccountCode = '';
    window._drillVoucherNo = '';
    window._drillDownAccount = function(code) { window._drillAccountCode = code; };
    window._drillDownVoucher = function(vno) { window._drillVoucherNo = vno; };
    </script>''')
    ui.run_javascript('''
        window._drillAccountCode = '';
        window._drillVoucherNo = '';
        window._drillDownAccount = function(code) { window._drillAccountCode = code; };
        window._drillDownVoucher = function(vno) { window._drillVoucherNo = vno; };
    ''')
    ui.timer(1.0, _poll_drill, once=True)

    # ── 子报表标签页 ──
    # 初始化 reports_center 的 tab 列表
    if not hasattr(state, '_reports_tabs') or state._reports_tabs is None:
        state._reports_tabs = [
            {"key": "trial_balance", "label": "试算平衡表", "icon": "grid_on"}
        ]
    if not hasattr(state, '_reports_active_idx'):
        state._reports_active_idx = 0

    # 标签栏
    with ui.row().classes("reports-tab-bar"):
        for i, (rkey, rlabel, ricon) in enumerate(_REPORT_TABS):
            is_active = (i == state._reports_active_idx) if hasattr(state, '_reports_active_idx') else (i == 0)
            with ui.button(
                on_click=lambda _i=i, _k=rkey: _switch_report(_i, _k)
            ).props("flat no-caps").classes(
                f"reports-tab {'reports-tab--active' if is_active else 'reports-tab--inactive'}"
            ):
                ui.icon(ricon).classes("text-sm")
                ui.label(rlabel).classes("text-sm")

    # 内容区
    with ui.element("div").classes("reports-tab-content") as state._reports_content_area:
        _render_current_report()


def _switch_report(idx, key):
    """切换到指定子报表"""
    state._reports_active_idx = idx
    # 重绘整个报表中心（标签栏高亮 + 内容区）
    from app.components.ui_helpers import _rebuild_content
    _rebuild_content()


def _render_current_report():
    """渲染当前激活的子报表"""
    tabs = state._reports_tabs if hasattr(state, '_reports_tabs') and state._reports_tabs else [
        {"key": "trial_balance", "label": "试算平衡表", "icon": "grid_on"}
    ]
    idx = state._reports_active_idx if hasattr(state, '_reports_active_idx') else 0
    if idx >= len(tabs):
        idx = 0
    tab = tabs[idx]
    key = tab["key"]

    # 动态导入并渲染对应报表
    _REPORT_RENDERERS = {
        "trial_balance":    lambda: _render_minimal("trial_balance"),
        "balance_sheet":    lambda: _render_minimal("balance_sheet"),
        "income_statement": lambda: _render_minimal("income_statement"),
        "accounts":         lambda: _render_minimal("accounts"),
        "charts":           lambda: _render_minimal("charts"),
        "close_period":     lambda: _render_minimal("close_period"),
    }
    renderer = _REPORT_RENDERERS.get(key)
    if renderer:
        renderer()


def _render_minimal(page_key):
    """渲染无头部的纯报表内容（期间选择器已在顶部统一）"""
    lid = state.selected_ledger_id
    year, month = state.selected_year, state.selected_month

    if page_key == "trial_balance":
        _render_trial_balance_content(lid, year, month)
    elif page_key == "balance_sheet":
        _render_balance_sheet_content(lid, year, month)
    elif page_key == "income_statement":
        _render_income_statement_content(lid, year, month)
    elif page_key == "accounts":
        _render_accounts_content(lid, year, month)
    elif page_key == "charts":
        _render_charts_content(lid, year, month)
    elif page_key == "close_period":
        from app.pages.close_period import render_close_period
        render_close_period()


def _refresh_all():
    """刷新当前报表"""
    from app.components.ui_helpers import _rebuild_content
    _rebuild_content()


# ── 各报表纯内容渲染（无头部期间选择器）──

def _render_trial_balance_content(lid, year, month):
    """试算平衡表内容"""
    balances = ReportService.get_account_balances(lid, year, month)
    if not balances:
        with ui.card().classes("report-card"):
            from app.components.ui_components import EmptyState
            EmptyState(icon="grid_on", message="暂无科目余额数据",
                      hint="请先录入记账凭证并过账",
                      action=lambda: None, action_label="去填凭证")
        return

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

    with ui.row().classes("report-kpi-grid"):
        for label, value, color_class in [
            ("期初合计", total_opening, ""),
            ("本期借方", total_debit, "report-kpi__value--danger"),
            ("本期贷方", total_credit, "report-kpi__value--primary"),
            ("期末合计", total_closing, ""),
        ]:
            with ui.element("div").classes("report-kpi"):
                ui.label(label).classes("report-kpi__label")
                ui.label(format_amount(value)).classes(f"report-kpi__value {color_class}")
        with ui.element("div").classes("report-kpi"):
            ui.label("借贷平衡").classes("report-kpi__label")
            if diff < 0.01:
                ui.label("✓ 平衡").classes("report-kpi__value report-kpi__value--success")
            else:
                ui.label(f"✗ 差额 {format_amount(diff)}").classes("report-kpi__value report-kpi__value--danger")

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
                rows_html += f'''<tr class="tb-row" style="cursor:pointer" onclick="window._drillDownAccount&&window._drillDownAccount('{code}')">
                    <td class="tb-td tb-td-code"><a class="tb-link" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount('{code}')">{code}</a></td>
                    <td class="tb-td tb-td-name"><a class="tb-link" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount('{code}')">{name}</a></td>
                    <td class="tb-td tb-td-num" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount('{code}')">{format_amount(opening) if opening else "—"}</td>
                    <td class="tb-td tb-td-num amount-negative" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount('{code}')">{format_amount(debit) if debit else "—"}</td>
                    <td class="tb-td tb-td-num amount-positive" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount('{code}')">{format_amount(credit) if credit else "—"}</td>
                    <td class="tb-td tb-td-num" style="font-weight:600" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount('{code}')">{format_amount(closing) if closing else "—"}</td>
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

    with ui.row().classes("report-footer"):
        ui.label("全部科目合计").classes("font-bold text-sm")
        with ui.row().classes("gap-6 report-footer__detail"):
            ui.label(f"期初 {format_amount(total_opening)}")
            ui.label(f"借方 {format_amount(total_debit)}")
            ui.label(f"贷方 {format_amount(total_credit)}")
            ui.label(f"期末 {format_amount(total_closing)}")


def _render_balance_sheet_content(lid, year, month):
    """资产负债表内容"""
    bs = ReportService.get_balance_sheet(lid, year, month)
    if not bs or not isinstance(bs, dict):
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📋").classes("report-empty__icon")
                ui.label("暂无资产负债表数据").classes("report-empty__text")
        return

    # bs 现在返回带 code 的扁平结构
    assets = bs.get("assets", [])
    liabilities = bs.get("liabilities", [])
    equity = bs.get("equity", [])
    total_assets = bs.get("total_assets", 0) or sum(float(a.get("end", 0) or 0) for a in assets)
    total_liabilities = bs.get("total_liab", 0) or sum(float(l.get("end", 0) or 0) for l in liabilities)
    total_equity = bs.get("total_equity", 0) or sum(float(e.get("end", 0) or 0) for e in equity)
    diff = abs(total_assets - (total_liabilities + total_equity))

    with ui.row().classes("report-kpi-grid"):
        for label, value, color_class in [
            ("资产总计", total_assets, "report-kpi__value--success"),
            ("负债合计", total_liabilities, "report-kpi__value--danger"),
            ("所有者权益", total_equity, "report-kpi__value--primary"),
            ("平衡差额", diff, "report-kpi__value--danger" if diff >= 0.01 else "report-kpi__value--success"),
        ]:
            with ui.element("div").classes("report-kpi"):
                ui.label(label).classes("report-kpi__label")
                ui.label(format_amount(value)).classes(f"report-kpi__value {color_class}")

    table_html = '<table class="tb-table"><thead><tr><th class="tb-th">项目</th><th class="tb-th tb-th-num">金额</th></tr></thead><tbody>'
    # 资产
    table_html += f'<tr class="tb-row-subtotal"><td class="tb-td tb-td-name font-bold">资产类</td><td class="tb-td tb-td-num font-bold"></td></tr>'
    for a in assets:
        code = a.get("code", "")
        name = a.get("name", "")
        amount = a.get("end", 0) or 0
        if code:
            table_html += f'<tr class="tb-row" style="cursor:pointer"><td class="tb-td tb-td-name" style="padding-left:24px"><a class="tb-link" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount(\'{code}\')">{name}</a></td><td class="tb-td tb-td-num" onclick="window._drillDownAccount&&window._drillDownAccount(\'{code}\')">{format_amount(amount)}</td></tr>'
        else:
            table_html += f'<tr class="tb-row"><td class="tb-td tb-td-name" style="padding-left:24px">{name}</td><td class="tb-td tb-td-num">{format_amount(amount)}</td></tr>'
    table_html += f'<tr class="tb-row-subtotal"><td class="tb-td tb-td-name font-bold">资产总计</td><td class="tb-td tb-td-num font-bold">{format_amount(total_assets)}</td></tr>'
    # 负债
    table_html += f'<tr class="tb-row-subtotal"><td class="tb-td tb-td-name font-bold">负债类</td><td class="tb-td tb-td-num font-bold"></td></tr>'
    for l in liabilities:
        code = l.get("code", "")
        name = l.get("name", "")
        amount = l.get("end", 0) or 0
        if code:
            table_html += f'<tr class="tb-row" style="cursor:pointer"><td class="tb-td tb-td-name" style="padding-left:24px"><a class="tb-link" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount(\'{code}\')">{name}</a></td><td class="tb-td tb-td-num" onclick="window._drillDownAccount&&window._drillDownAccount(\'{code}\')">{format_amount(amount)}</td></tr>'
        else:
            table_html += f'<tr class="tb-row"><td class="tb-td tb-td-name" style="padding-left:24px">{name}</td><td class="tb-td tb-td-num">{format_amount(amount)}</td></tr>'
    table_html += f'<tr class="tb-row-subtotal"><td class="tb-td tb-td-name font-bold">负债合计</td><td class="tb-td tb-td-num font-bold">{format_amount(total_liabilities)}</td></tr>'
    # 权益
    table_html += f'<tr class="tb-row-subtotal"><td class="tb-td tb-td-name font-bold">所有者权益类</td><td class="tb-td tb-td-num font-bold"></td></tr>'
    for e in equity:
        code = e.get("code", "")
        name = e.get("name", "")
        amount = e.get("end", 0) or 0
        if code:
            table_html += f'<tr class="tb-row" style="cursor:pointer"><td class="tb-td tb-td-name" style="padding-left:24px"><a class="tb-link" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount(\'{code}\')">{name}</a></td><td class="tb-td tb-td-num" onclick="window._drillDownAccount&&window._drillDownAccount(\'{code}\')">{format_amount(amount)}</td></tr>'
        else:
            table_html += f'<tr class="tb-row"><td class="tb-td tb-td-name" style="padding-left:24px">{name}</td><td class="tb-td tb-td-num">{format_amount(amount)}</td></tr>'
    table_html += f'<tr class="tb-row-subtotal"><td class="tb-td tb-td-name font-bold">所有者权益合计</td><td class="tb-td tb-td-num font-bold">{format_amount(total_equity)}</td></tr>'
    table_html += '</tbody></table>'

    with ui.card().classes("report-card"):
        with ui.card_section().classes("p-0"):
            ui.html(table_html, sanitize=False)

    is_balanced = diff < 0.01
    with ui.row().classes("report-footer"):
        with ui.row().classes(f"report-footer__status {'report-footer__status--ok' if is_balanced else 'report-footer__status--error'}"):
            ui.label("✓" if is_balanced else "✗").classes("text-base")
            ui.label("资产负债表平衡" if is_balanced else "资产负债表不平衡")


def _render_income_statement_content(lid, year, month):
    """利润表内容"""
    inc = ReportService.get_income_statement(lid, year, month) or {}
    inc_yoy = ReportService.get_income_statement(lid, year - 1, month) or {}

    if not inc or not inc.get("rows"):
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📋").classes("report-empty__icon")
                ui.label("暂无利润表数据").classes("report-empty__text")
        return

    rows_data = inc.get("rows", [])
    total_revenue = sum(r.get("ytd", 0) or 0 for r in rows_data if r.get("type", "").startswith("rev"))
    total_expense = sum(r.get("ytd", 0) or 0 for r in rows_data if r.get("type", "").startswith("exp"))
    net_profit = total_revenue - total_expense

    with ui.row().classes("report-kpi-grid"):
        for label, value, color_class in [
            ("营业收入", total_revenue, "report-kpi__value--success"),
            ("营业成本", total_expense, "report-kpi__value--danger"),
            ("净利润", net_profit, "report-kpi__value--success" if net_profit >= 0 else "report-kpi__value--danger"),
        ]:
            with ui.element("div").classes("report-kpi"):
                ui.label(label).classes("report-kpi__label")
                ui.label(format_amount(value)).classes(f"report-kpi__value {color_class}")

    yoy_map = {r["name"]: r.get("ytd") for r in inc_yoy.get("rows", [])}
    rows_html = ""
    for r in rows_data:
        ytd_val = r.get("ytd")
        yoy_val = yoy_map.get(r["name"])
        yoy_pct = ((ytd_val - yoy_val) / abs(yoy_val) * 100) if (yoy_val and yoy_val != 0 and ytd_val is not None) else None
        row_type = r.get("type", "")
        is_net = row_type == "total" or r["name"] == "净利润"
        is_item = row_type.endswith("_item")
        row_class = "tb-row-subtotal" if is_net else "tb-row"
        name_weight = "font-weight:700;" if (is_net or not is_item) else ""
        indent = "padding-left:28px;" if is_item else ""
        profit_color = "color:var(--c-danger);" if (is_net and net_profit < 0) else ""
        name_style = f"{name_weight}{indent}{profit_color}"
        yoy_pct_class = "yoy-up" if yoy_pct and yoy_pct > 0 else ("yoy-down" if yoy_pct and yoy_pct < 0 else "yoy-flat")
        yoy_pct_str = f"{yoy_pct:+.1f}%" if yoy_pct is not None else "—"
        acct_code = r.get("code", "")
        is_drillable = bool(acct_code and is_item)

        if is_drillable:
            rows_html += f'''<tr class="{row_class}" style="cursor:pointer">
                <td class="tb-td tb-td-name" style="{name_style}"><a class="tb-link" onclick="event.stopPropagation();window._drillDownAccount&&window._drillDownAccount('{acct_code}')">{r["name"]}</a></td>
                <td class="tb-td tb-td-num" onclick="window._drillDownAccount&&window._drillDownAccount('{acct_code}')">{format_amount(ytd_val) if ytd_val is not None else "—"}</td>
                <td class="tb-td tb-td-num" onclick="window._drillDownAccount&&window._drillDownAccount('{acct_code}')">{format_amount(r.get("month")) if r.get("month") is not None else "—"}</td>
                <td class="tb-td tb-td-num" onclick="window._drillDownAccount&&window._drillDownAccount('{acct_code}')">{format_amount(yoy_val) if yoy_val is not None else "—"}</td>
                <td class="tb-td tb-td-num {yoy_pct_class}" onclick="window._drillDownAccount&&window._drillDownAccount('{acct_code}')">{yoy_pct_str}</td>
            </tr>'''
        else:
            rows_html += f'''<tr class="{row_class}">
                <td class="tb-td tb-td-name" style="{name_style}">{r["name"]}</td>
                <td class="tb-td tb-td-num">{format_amount(ytd_val) if ytd_val is not None else "—"}</td>
                <td class="tb-td tb-td-num">{format_amount(r.get("month")) if r.get("month") is not None else "—"}</td>
                <td class="tb-td tb-td-num">{format_amount(yoy_val) if yoy_val is not None else "—"}</td>
                <td class="tb-td tb-td-num {yoy_pct_class}">{yoy_pct_str}</td>
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
        with ui.card_section().classes("p-0"):
            ui.html(table_html, sanitize=False)


def _render_accounts_content(lid, year, month):
    """科目余额表内容"""
    balances = ReportService.get_account_balances(lid, year, month)
    if not balances:
        with ui.card().classes("report-card"):
            with ui.column().classes("report-empty"):
                ui.label("📋").classes("report-empty__icon")
                ui.label("暂无科目余额数据").classes("report-empty__text")
        return

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
        rows.append({"code": b.get("code", ""), "name": b.get("name", ""),
                     "opening": ob, "debit": pd, "credit": pc, "closing": cb,
                     "level": b.get("level", 0), "is_total": is_t})

    rows.append({"code": "", "name": "合 计", "opening": total["opening"], "debit": total["debit"],
                 "credit": total["credit"], "closing": total["closing"], "level": 0, "is_total": True})

    with ui.row().classes("report-kpi-grid"):
        for label, value, color_class in [
            ("期初余额", total["opening"], ""),
            ("本期借方", total["debit"], "report-kpi__value--success"),
            ("本期贷方", total["credit"], "report-kpi__value--danger"),
            ("期末余额", total["closing"], "report-kpi__value--primary"),
        ]:
            with ui.element("div").classes("report-kpi"):
                ui.label(label).classes("report-kpi__label")
                ui.label(f"¥{value:,.2f}").classes(f"report-kpi__value {color_class}")

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
                <a v-if="props.row.code && !props.row.is_total" class="tb-link"
                   @click="$parent.$emit('drillDown', props.row.code)">
                    <span :class="props.row.level === 2 ? 'pl-4 text-sm text-grey-6' : 'text-sm'">
                        {{ props.row.name }}
                    </span>
                </a>
                <span v-else :class="props.row.is_total ? 'font-bold text-base' : (props.row.level === 2 ? 'pl-4 text-sm text-grey-6' : 'text-sm text-secondary')">
                    {{ props.row.name }}
                </span>
            </q-td>
        """)
        tbl.on("drillDown", lambda e: drill_down_to_account(e.args))

    is_balanced = abs(total['debit'] - total['credit']) < 0.01
    with ui.row().classes("report-footer"):
        with ui.row().classes(f"report-footer__status {'report-footer__status--ok' if is_balanced else 'report-footer__status--error'}"):
            ui.label("✓" if is_balanced else "✗").classes("text-base")
            ui.label("借贷平衡" if is_balanced else "借贷不平衡")


def _render_charts_content(lid, year, month):
    """图表分析内容"""
    from app.pages.charts import render_charts
    render_charts()
