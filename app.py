"""
AI 财务系统 — 模块化主入口
"""
import sys, os

# ── 版本信息 ──
VERSION = "3.0.0"
VERSION_NAME = "V3"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from database.connection import init_db, init_v3_tables, init_system_templates
from app.services import LedgerService

# ── 初始化数据库 ──
init_db()
try:
    init_v3_tables()
except Exception as e:
    print(f"v3 init: {e}")
try:
    for ledger in LedgerService.get_all():
        init_system_templates(ledger["id"])
except Exception as e:
    print(f"templates init: {e}")

from nicegui import ui, app

# ── 注册静态文件路由 ──
import os as _os
_STATIC_DIR = _os.path.join(_os.path.dirname(__file__), "app", "static")
app.add_static_files("/static", _STATIC_DIR)

# ── 注册 API 路由 ──
from app.routes import register_routes
register_routes(app)

# ── 自动备份 ──
from app.services.backup import start_auto_backup
start_auto_backup()

# ── 导入所有页面渲染函数 ──
from app.config import register_page
from app.pages.dashboard import render_dashboard
from app.pages.journal import render_journal, render_voucher_detail, render_voucher_detail_page
from app.pages.reports import render_accounts
from app.pages.reports_balance_sheet import render_balance_sheet
from app.pages.reports_income_statement import render_income_statement
from app.pages.trial_balance import render_trial_balance
from app.pages.close_period import render_close_period
from app.pages.charts import render_charts
from app.pages.compare import render_compare
from app.pages.ai_assistant import render_ai_assistant
from app.pages.import_export import render_import, render_export
from app.pages.fixed_assets import render_fixed_assets
from app.pages.cashier import render_cashier
from app.pages.auxiliary import render_auxiliary
from app.pages.settings import render_settings, render_about
from app.pages.tax import render_tax
from app.pages.cash_flow import render_cash_flow
from app.pages.budget import render_budget
from app.pages.scheduled_vouchers import render_scheduled_vouchers
from app.pages.invoices import render_invoices
from app.pages.multi_currency import render_multi_currency
from app.pages.audit_log import render_audit_log
from app.pages.setup_wizard import render_setup_wizard
from app.pages.voucher_template import render_voucher_template
from app.pages.account_ledger import render_account_ledger
from app.pages.bank_reconciliation import render_bank_reconciliation
from app.pages.cash_flow_statement import render_cash_flow_statement
from app.pages.auth import render_login
from app.components.ui_helpers import render_header, render_sidebar
from app.components.state import state

# ── 注册页面路由表 ──
register_page("dashboard", render_dashboard)
register_page("journal", render_journal)
register_page("voucher_detail", render_voucher_detail_page)
register_page("accounts", render_accounts)
register_page("balance_sheet", render_balance_sheet)
register_page("trial_balance", render_trial_balance)
register_page("income_statement", render_income_statement)
register_page("close_period", render_close_period)
register_page("charts", render_charts)
register_page("compare", render_compare)
register_page("ai_assistant", render_ai_assistant)
register_page("import", render_import)
register_page("export", render_export)
register_page("fixed_assets", render_fixed_assets)
register_page("cashier", render_cashier)
register_page("auxiliary", render_auxiliary)
register_page("tax", render_tax)
register_page("cash_flow", render_cash_flow)
register_page("budget", render_budget)
register_page("scheduled_vouchers", render_scheduled_vouchers)
register_page("invoices", render_invoices)
register_page("multi_currency", render_multi_currency)
register_page("setup_wizard", render_setup_wizard)
register_page("voucher_template", render_voucher_template)
register_page("account_ledger", render_account_ledger)
register_page("bank_reconciliation", render_bank_reconciliation)
register_page("cash_flow_statement", render_cash_flow_statement)
register_page("about", render_about)
register_page("audit_log", render_audit_log)
register_page("settings", render_settings)


def render_page():
    """根据 state.current_page 分发到对应渲染函数（通过路由表查找）"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    page = state.current_page
    from app.config import get_page_render
    render_fn = get_page_render(page)
    if render_fn:
        render_fn()
    else:
        render_dashboard()


@ui.page("/")
def index():
    # 注入全局 CSS & JS（内联到 head，确保每次页面加载都生效）
    import os as _os
    _static_dir = _os.path.join(_os.path.dirname(__file__), "app", "static")
    _css_path = _os.path.join(_static_dir, "style.css")
    _js_path = _os.path.join(_static_dir, "script.js")
    if _os.path.exists(_css_path):
        with open(_css_path, encoding="utf-8") as _f:
            ui.add_head_html(f"<style>{_f.read()}</style>")
    if _os.path.exists(_js_path):
        with open(_js_path, encoding="utf-8") as _f:
            ui.add_head_html(f"<script>{_f.read()}</script>")
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700&display=swap" rel="stylesheet">'
    )

    if state.current_user is None:
        render_login()
    else:
        render_header()
        with ui.row().classes("w-full main-row"):
            render_sidebar()
            with ui.column().classes("main-content-area flex-grow gap-3") as state.main_content:
                render_page()


# ── 手机端抽屉式侧边栏 + 遮罩层 ──


# ── 启动 ──
if __name__ == "__main__":
    ui.run(
        title=f"AI 财务系统 {VERSION_NAME} v{VERSION}",
        port=8090,
        host="0.0.0.0",
        reload=False,
        show=False,
        language="zh-CN",
    )
