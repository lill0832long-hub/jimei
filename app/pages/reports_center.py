"""报表中心 - Excel风格标签页切换"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, show_toast, refresh_main
from app.services import LedgerService, ReportService

_REPORT_CARDS = [
    ("trial_balance",    "试算平衡表", "grid_on",          "检验借贷是否平衡", "账簿"),
    ("balance_sheet",    "资产负债表", "account_balance",  "反映资产/负债/权益", "报表"),
    ("income_statement", "利润表",     "trending_up",      "反映经营成果", "报表"),
    ("accounts",         "科目余额表", "bar_chart",        "查看科目余额", "账簿"),
    ("charts",           "图表分析",   "show_chart",       "可视化图表", "分析"),
    ("close_period",     "期末结转",   "sync_alt",         "结转损益科目", "工具"),
]


def render_reports_center():
    """报表中心 - Excel风格标签页切换"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("w-full max-w-md mx-auto mt-16"):
            with ui.column().classes("items-center gap-4 p-8"):
                ui.icon("account_balance", size="48px").classes("text-grey-5")
                ui.label("请先创建账套").classes("text-h6 text-grey-7")
        return

    # 顶部工具栏
    with ui.row().classes("items-center gap-3 w-full reports-toolbar"):
        ui.icon("assessment", size="28px").classes("text-primary")
        ui.label("报表中心").classes("text-h6 text-weight-bold")
        ui.space()
        with ui.row().classes("items-center gap-2"):
            year_sel = ui.select(
                {str(y): str(y) for y in range(2020, 2031)},
                value=str(state.selected_year), label="年度"
            ).props("outlined dense").classes("w-24")
            month_sel = ui.select(
                {str(m): str(m) + "月" for m in range(1, 13)},
                value=str(state.selected_month), label="月份"
            ).props("outlined dense").classes("w-20")
            ui.button("刷新", icon="refresh", color="primary",
                      on_click=lambda: refresh_main()).props("dense no-caps")

            def _on_change():
                state.selected_year = int(year_sel.value)
                state.selected_month = int(month_sel.value)

            year_sel.on("update:value", lambda e: _on_change())
            month_sel.on("update:value", lambda e: _on_change())

    # Excel风格标签页
    with ui.tabs().classes("w-full reports-tabs") as tabs:
        for key, label, icon, _, _ in _REPORT_CARDS:
            ui.tab(key, label=label, icon=icon).props("no-caps")

    # 标签页内容面板
    with ui.tab_panels(tabs, value=_REPORT_CARDS[0][0]).classes("w-full reports-tab-panels"):
        for key, _, _, _, _ in _REPORT_CARDS:
            with ui.tab_panel(key).classes("reports-tab-panel"):
                _render_report_content(key)


def _render_report_content(report):
    """渲染指定报表内容"""
    if report == "trial_balance":
        from app.pages.trial_balance import render_trial_balance
        render_trial_balance()
    elif report == "balance_sheet":
        from app.pages.reports_balance_sheet import render_balance_sheet
        render_balance_sheet()
    elif report == "income_statement":
        from app.pages.reports_income_statement import render_income_statement
        render_income_statement()
    elif report == "accounts":
        from app.pages.reports import render_accounts
        render_accounts()
    elif report == "charts":
        from app.pages.charts import render_charts
        render_charts()
    elif report == "close_period":
        from app.pages.close_period import render_close_period
        render_close_period()
    else:
        ui.label("报表开发中...").style("color:var(--c-text-muted)")


def _refresh_report():
    """刷新当前报表"""
    refresh_main()
