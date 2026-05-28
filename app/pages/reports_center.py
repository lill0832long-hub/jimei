"""报表中心 — 统一布局容器（柠檬云架构）"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, show_toast, refresh_main
from app.services import LedgerService, ReportService

# 报表配置
_REPORT_CARDS = [
    ("trial_balance",    "试算平衡表", "grid_on",          "检验借贷是否平衡，包含全部科目期初/本期/期末余额", "账簿"),
    ("balance_sheet",    "资产负债表", "account_balance",  "反映企业某一时点的资产、负债和权益状况", "报表"),
    ("income_statement", "利润表",     "trending_up",      "反映企业一定期间的经营成果和利润水平", "报表"),
    ("accounts",         "科目余额表", "bar_chart",        "按科目查看期初、本期发生额、期末余额", "账簿"),
    ("charts",           "图表分析",   "show_chart",       "可视化图表展示资产、负债、收入、费用分布", "分析"),
    ("close_period",     "期末结转",   "sync_alt",         "自动生成期末结转凭证，结转损益类科目", "工具"),
]


def render_reports_center():
    """报表中心主页 — 统一布局容器"""
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

    # ── 初始化报表状态 ──
    # 从URL参数读取报表
    try:
        from nicegui import context
        _report_param = context.client.request.query_params.get("report")
        if _report_param:
            state._active_report = _report_param
        else:
            # 没有report参数时，强制显示卡片网格
            state._active_report = None
    except Exception:
        state._active_report = None

    def _open_report(key):
        state._active_report = key
        ui.navigate.to(f'/?page=reports_center&report={key}')

    def _back_to_grid():
        state._active_report = None
        ui.navigate.to('/?page=reports_center')

    if state._active_report is None:
        # ── 报表选择页面 ──
        _render_report_grid(_open_report)
    else:
        # ── 报表查看页面（统一布局） ──
        _render_report_viewer(_back_to_grid, _open_report)


def _render_report_grid(open_report_fn):
    """渲染报表选择页面（卡片网格）"""
    # 整体布局：左侧导航 + 右侧内容
    with ui.row().classes("lemon-layout"):
        # 左侧导航栏
        with ui.column().classes("lemon-sidebar"):
            ui.label("报表中心").classes("lemon-sidebar__title")
            ui.label("财务分析与报表").classes("lemon-sidebar__subtitle")
            
            # 导航菜单
            with ui.column().classes("lemon-sidebar__menu"):
                for key, label, icon, desc, cat in _REPORT_CARDS:
                    with ui.row().classes("lemon-sidebar__item").on("click", lambda _k=key: open_report_fn(_k)):
                        ui.icon(icon).classes("lemon-sidebar__icon")
                        ui.label(label).classes("lemon-sidebar__label")

        # 右侧主内容区
        with ui.column().classes("lemon-content"):
            # 顶部工具栏
            with ui.row().classes("lemon-toolbar"):
                ui.icon("assessment").style("color:var(--c-primary);font-size:24px")
                ui.label("报表中心").classes("lemon-toolbar__title")
                ui.space()
                ui.label("选择报表查看分析数据").classes("lemon-toolbar__hint")

            # 卡片网格（按类别分组）
            with ui.column().classes("lemon-grid-container"):
                # 按类别分组
                categories = {}
                for key, label, icon, desc, cat in _REPORT_CARDS:
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append((key, label, icon, desc))

                for cat_name, items in categories.items():
                    with ui.column().classes("lemon-category"):
                        ui.label(cat_name).classes("lemon-category__title")
                        with ui.row().classes("lemon-card-grid"):
                            for key, label, icon, desc in items:
                                with ui.card().classes("lemon-card").on("click", lambda _k=key: open_report_fn(_k)):
                                    with ui.column().classes("lemon-card__content"):
                                        ui.icon(icon).classes("lemon-card__icon")
                                        ui.label(label).classes("lemon-card__title")
                                        ui.label(desc).classes("lemon-card__desc")
                                    with ui.row().classes("lemon-card__footer"):
                                        ui.label("查看报表").classes("lemon-card__action")
                                        ui.icon("arrow_forward", size="sm").classes("lemon-card__arrow")


def _render_report_viewer(back_fn, open_report_fn):
    """渲染报表查看页面（统一布局）"""
    # 整体布局：左侧导航 + 右侧内容
    with ui.row().classes("lemon-layout"):
        # 左侧导航栏（可折叠）
        with ui.column().classes("lemon-sidebar lemon-sidebar--viewer"):
            with ui.row().classes("lemon-sidebar__header"):
                ui.button(icon="arrow_back", on_click=back_fn).props("flat round dense")
                ui.label("报表列表").classes("lemon-sidebar__title")
            
            # 导航菜单
            with ui.column().classes("lemon-sidebar__menu"):
                for key, label, icon, desc, cat in _REPORT_CARDS:
                    is_active = state._active_report == key
                    with ui.row().classes(f"lemon-sidebar__item {'lemon-sidebar__item--active' if is_active else ''}").on("click", lambda _k=key: open_report_fn(_k)):
                        ui.icon(icon).classes("lemon-sidebar__icon")
                        ui.label(label).classes("lemon-sidebar__label")

        # 右侧主内容区
        with ui.column().classes("lemon-content"):
            # 顶部工具栏（统一年月选择器）
            with ui.row().classes("lemon-toolbar"):
                _label = next((l for k, l, _, _, _ in _REPORT_CARDS if k == state._active_report), state._active_report)
                ui.label(_label).classes("lemon-toolbar__title")
                ui.space()
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
                              on_click=lambda: _refresh_report()).props("dense no-caps")

                    def _on_period_change():
                        state.selected_year = int(year_sel.value)
                        state.selected_month = int(month_sel.value)
                        _refresh_report()

                    year_sel.on("update:value", lambda e: _on_period_change())
                    month_sel.on("update:value", lambda e: _on_period_change())

            # 报表内容区（自适应高度）
            with ui.column().classes("lemon-report-content"):
                _render_report_content()


def _render_report_content():
    """渲染当前报表内容（只渲染数据，不包含布局）"""
    lid = state.selected_ledger_id
    year = state.selected_year
    month = state.selected_month
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
