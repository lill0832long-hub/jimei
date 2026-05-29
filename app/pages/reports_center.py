"""???? ? ???????????"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import format_amount, show_toast, refresh_main
from app.services import LedgerService, ReportService

# ????
_REPORT_CARDS = [
    ("trial_balance",    "?????", "grid_on",          "?????????????????/??/????", "??"),
    ("balance_sheet",    "?????", "account_balance",  "???????????????????", "??"),
    ("income_statement", "???",     "trending_up",      "??????????????????", "??"),
    ("accounts",         "?????", "bar_chart",        "??????????????????", "??"),
    ("charts",           "????",   "show_chart",       "????????????????????", "??"),
    ("close_period",     "????",   "sync_alt",         "??????????????????", "??"),
]


def render_reports_center():
    """?????? ? ??????"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("w-full max-w-md mx-auto mt-16"):
            with ui.column().classes("items-center gap-4 p-8"):
                ui.icon("account_balance", size="48px").classes("text-grey-5")
                ui.label("??????").classes("text-h6 text-grey-7")
        return

    # ???????
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
        ui.navigate.to(f'/?page=reports_center&report={key}')

    def _back_to_grid():
        state._active_report = None
        ui.navigate.to('/?page=reports_center')

    # ?? ui.splitter ??????
    with ui.splitter(value=25).classes("w-full h-full") as splitter:
        # ?????????
        with splitter.before:
            _render_left_panel(_open_report, _back_to_grid)

        # ?????????
        with splitter.after:
            if state._active_report is None:
                _render_report_grid(_open_report)
            else:
                _render_report_viewer(_back_to_grid, _open_report)


def _render_left_panel(open_report_fn, back_fn):
    """????????"""
    with ui.column().classes("w-full h-full bg-white"):
        # ????
        with ui.row().classes("items-center gap-2 p-4 border-b"):
            ui.icon("assessment", size="24px").classes("text-primary")
            ui.label("????").classes("text-h6 text-weight-bold")

        # ????
        with ui.column().classes("w-full p-2 gap-1"):
            # ???????????????
            if state._active_report:
                with ui.row().classes("items-center gap-2 p-2 rounded cursor-pointer hover:bg-blue-1").on("click", lambda: back_fn()):
                    ui.icon("arrow_back", size="20px").classes("text-grey-7")
                    ui.label("????").classes("text-body2 text-grey-7")

            # ?????
            categories = {}
            for key, label, icon, desc, cat in _REPORT_CARDS:
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append((key, label, icon, desc))

            for cat_name, items in categories.items():
                # ????
                ui.label(cat_name).classes("text-caption text-grey-5 q-px-sm q-pt-sm")

                # ???
                for key, label, icon, desc in items:
                    is_active = state._active_report == key
                    bg_class = "bg-blue-1 text-primary" if is_active else "hover:bg-grey-1"
                    with ui.row().classes(f"items-center gap-3 p-2 rounded cursor-pointer {bg_class}").on("click", lambda _k=key: open_report_fn(_k)):
                        ui.icon(icon, size="20px").classes("text-primary" if is_active else "text-grey-6")
                        ui.label(label).classes("text-body2 text-weight-medium")


def _render_report_grid(open_report_fn):
    """??????????????"""
    with ui.column().classes("w-full h-full"):
        # ?????
        with ui.row().classes("items-center gap-3 p-4 bg-white border-b"):
            ui.icon("dashboard", size="24px").classes("text-primary")
            ui.label("????").classes("text-h5 text-weight-bold")
            ui.space()
            ui.label("??????????").classes("text-body2 text-grey-6")

        # ????
        with ui.scroll_area().classes("w-full flex-grow"):
            with ui.column().classes("p-4 gap-6"):
                # ?????
                categories = {}
                for key, label, icon, desc, cat in _REPORT_CARDS:
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append((key, label, icon, desc))

                for cat_name, items in categories.items():
                    with ui.column().classes("gap-3"):
                        # ????
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("folder", size="18px").classes("text-primary")
                            ui.label(cat_name).classes("text-h6 text-weight-bold text-grey-8")

                        # ????
                        with ui.grid(columns=3).classes("w-full gap-4"):
                            for key, label, icon, desc in items:
                                with ui.card().classes("cursor-pointer hover:shadow-lg transition-all").on("click", lambda _k=key: open_report_fn(_k)):
                                    with ui.column().classes("p-4 gap-3"):
                                        # ??
                                        with ui.row().classes("items-center gap-3"):
                                            ui.icon(icon, size="32px").classes("text-primary")
                                            ui.label(label).classes("text-h6 text-weight-bold")

                                        # ??
                                        ui.label(desc).classes("text-body2 text-grey-6")

                                        # ????
                                        with ui.row().classes("items-center gap-2 mt-2"):
                                            ui.label("????").classes("text-primary text-weight-medium")
                                            ui.icon("arrow_forward", size="16px").classes("text-primary")


def _render_report_viewer(back_fn, open_report_fn):
    """????????"""
    with ui.column().classes("w-full h-full"):
        # ?????
        with ui.row().classes("items-center gap-3 p-4 bg-white border-b"):
            # ????
            ui.button(icon="arrow_back", on_click=back_fn).props("flat round dense")
            
            # ????
            _label = next((l for k, l, _, _, _ in _REPORT_CARDS if k == state._active_report), state._active_report)
            ui.label(_label).classes("text-h5 text-weight-bold")
            
            ui.space()
            
            # ?????
            with ui.row().classes("items-center gap-3"):
                year_sel = ui.select(
                    {str(y): str(y) for y in range(2020, 2031)},
                    value=str(state.selected_year), label="??"
                ).props("outlined dense").classes("w-28")
                month_sel = ui.select(
                    {str(m): f"{m}?" for m in range(1, 13)},
                    value=str(state.selected_month), label="??"
                ).props("outlined dense").classes("w-24")
                ui.button("??", icon="refresh", color="primary",
                          on_click=lambda: _refresh_report()).props("dense no-caps")

                def _on_period_change():
                    state.selected_year = int(year_sel.value)
                    state.selected_month = int(month_sel.value)
                    _refresh_report()

                year_sel.on("update:value", lambda e: _on_period_change())
                month_sel.on("update:value", lambda e: _on_period_change())

        # ?????
        with ui.scroll_area().classes("w-full flex-grow"):
            _render_report_content()


def _render_report_content():
    """????????"""
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
        ui.label("?????...").style("color:var(--c-text-muted)")


def _refresh_report():
    """??????"""
    refresh_main()
