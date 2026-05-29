"""报表中心 - 响应式卡片网格布局"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, show_toast, refresh_main
from app.services import LedgerService, ReportService

_REPORT_CARDS = [
    ("trial_balance",    "试算平衡表", "grid_on",          "检验借贷是否平衡，包含全部科目期初/本期/期末余额", "账簿"),
    ("balance_sheet",    "资产负债表", "account_balance",  "反映企业某一时点的资产、负债和权益状况", "报表"),
    ("income_statement", "利润表",     "trending_up",      "反映企业一定期间的经营成果和利润水平", "报表"),
    ("accounts",         "科目余额表", "bar_chart",        "按科目查看期初、本期发生额、期末余额", "账簿"),
    ("charts",           "图表分析",   "show_chart",       "可视化图表展示资产、负债、收入、费用分布", "分析"),
    ("close_period",     "期末结转",   "sync_alt",         "自动生成期末结转凭证，结转损益类科目", "工具"),
]


def render_reports_center():
    """报表中心主页 - 响应式布局"""
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

    # 初始化报表状态
    try:
        from nicegui import context
        _report_param = context.client.request.query_params.get("report")
        if _report_param:
            state._active_report = _report_param
        else:
            state._active_report = None
    except Exception:
        state._active_report = None

    def _open_report(key):
        state._active_report = key
        ui.navigate.to(f"/?page=reports_center&report={key}")

    def _back_to_grid():
        state._active_report = None
        ui.navigate.to("/?page=reports_center")

    # 使用标签页切换，而不是 splitter
    if state._active_report is None:
        _render_report_grid(_open_report)
    else:
        _render_report_viewer(_back_to_grid, _open_report)


def _render_report_grid(open_report_fn):
    """渲染报表选择页面 - 自适应卡片网格"""
    with ui.column().classes("w-full gap-4 p-4"):
        # 顶部工具栏
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-3 q-pa-md"):
                ui.icon("assessment", size="32px").classes("text-primary")
                with ui.column():
                    ui.label("报表中心").classes("text-h5 text-weight-bold")
                    ui.label("选择报表查看分析数据").classes("text-body2 text-grey-6")

        # 按类别分组显示
        categories = {}
        for key, label, icon, desc, cat in _REPORT_CARDS:
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((key, label, icon, desc))

        for cat_name, items in categories.items():
            with ui.card().classes("w-full"):
                # 类别标题
                with ui.row().classes("items-center gap-2 q-pa-md q-pb-none"):
                    ui.icon("folder", size="20px").classes("text-primary")
                    ui.label(cat_name).classes("text-h6 text-weight-bold")

                # 卡片网格 - 自适应列数
                with ui.grid().classes("w-full").style("grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; padding: 16px;"):
                    for key, label, icon, desc in items:
                        with ui.card().classes("cursor-pointer hover:shadow-lg").on("click", lambda _k=key: open_report_fn(_k)):
                            with ui.row().classes("items-center gap-3 q-pa-md"):
                                ui.icon(icon, size="40px").classes("text-primary")
                                with ui.column().classes("gap-1"):
                                    ui.label(label).classes("text-h6 text-weight-bold")
                                    ui.label(desc).classes("text-body2 text-grey-6")


def _render_report_viewer(back_fn, open_report_fn):
    """渲染报表查看页面"""
    with ui.column().classes("w-full gap-4 p-4"):
        # 顶部工具栏
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-3 q-pa-md"):
                ui.button(icon="arrow_back", on_click=back_fn).props("flat round dense")
                _label = next((l for k, l, _, _, _ in _REPORT_CARDS if k == state._active_report), state._active_report)
                ui.label(_label).classes("text-h5 text-weight-bold")
                ui.space()
                with ui.row().classes("items-center gap-3"):
                    year_sel = ui.select(
                        {str(y): str(y) for y in range(2020, 2031)},
                        value=str(state.selected_year), label="年度"
                    ).props("outlined dense").classes("w-28")
                    month_sel = ui.select(
                        {str(m): f"{m}月" for m in range(1, 13)},
                        value=str(state.selected_month), label="月份"
                    ).props("outlined dense").classes("w-24")
                    ui.button("刷新", icon="refresh", color="primary",
                              on_click=lambda: _refresh_report()).props("dense no-caps")

                    def _on_period_change():
                        state.selected_year = int(year_sel.value)
                        state.selected_month = int(month_sel.value)
                        _refresh_report()

                    year_sel.on("update:value", lambda e: _on_period_change())
                    month_sel.on("update:value", lambda e: _on_period_change())

        # 报表内容区
        with ui.card().classes("w-full"):
            with ui.column().classes("q-pa-md"):
                _render_report_content()

        # 底部快捷导航
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-2 q-pa-md"):
                ui.label("快捷导航:").classes("text-body2 text-grey-6")
                for key, label, icon, _, _ in _REPORT_CARDS:
                    is_active = state._active_report == key
                    ui.button(label, icon=icon, color="primary" if is_active else "grey-7",
                              on_click=lambda _k=key: open_report_fn(_k)).props("flat dense no-caps")


def _render_report_content():
    """渲染当前报表内容"""
    report = state._active_report
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
