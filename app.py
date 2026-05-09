"""
AI 财务系统 v3 — 模块化主入口
"""
import sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from database_v3 import init_db, init_v3_tables, init_system_templates, get_ledgers

# ── 初始化数据库 ──
init_db()
try:
    init_v3_tables()
except Exception as e:
    print(f"v3 init: {e}")
try:
    for ledger in get_ledgers():
        init_system_templates(ledger["id"])
except Exception as e:
    print(f"templates init: {e}")

from nicegui import ui, app

# ── 注册 API 路由 ──
from app.routes import register_routes
register_routes(app)

# ── 自动备份 ──
from app.services.backup import start_auto_backup
start_auto_backup()

# ── 导入所有页面渲染函数 ──
from app.pages.dashboard import render_dashboard
from app.pages.journal import render_journal, render_voucher_detail, render_voucher_detail_page
from app.pages.reports import render_accounts, render_balance_sheet, render_income_statement
from app.pages.close_period import render_close_period
from app.pages.charts import render_charts
from app.pages.compare import render_compare
from app.pages.ai_assistant import render_ai_assistant
from app.pages.import_export import render_import, render_export
from app.pages.fixed_assets import render_fixed_assets
from app.pages.cashier import render_cashier
from app.pages.auxiliary import render_auxiliary
from app.pages.settings import render_settings
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


def render_page():
    """根据 state.current_page 分发到对应渲染函数"""
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    page = state.current_page
    if page == "dashboard":
        render_dashboard()
    elif page == "journal":
        render_journal()
    elif page == "voucher_detail":
        render_voucher_detail_page()
    elif page == "accounts":
        render_accounts()
    elif page == "balance_sheet":
        render_balance_sheet()
    elif page == "income_statement":
        render_income_statement()
    elif page == "close_period":
        render_close_period()
    elif page == "charts":
        render_charts()
    elif page == "compare":
        render_compare()
    elif page == "ai_assistant":
        render_ai_assistant()
    elif page == "import":
        render_import()
    elif page == "export":
        render_export()
    elif page == "fixed_assets":
        render_fixed_assets()
    elif page == "cashier":
        render_cashier()
    elif page == "auxiliary":
        render_auxiliary()
    elif page == "tax":
        render_tax()
    elif page == "cash_flow":
        render_cash_flow()
    elif page == "budget":
        render_budget()
    elif page == "scheduled_vouchers":
        render_scheduled_vouchers()
    elif page == "invoices":
        render_invoices()
    elif page == "multi_currency":
        render_multi_currency()
    elif page == "setup_wizard":
        render_setup_wizard()
    elif page == "voucher_template":
        render_voucher_template()
    elif page == "account_ledger":
        render_account_ledger()
    elif page == "bank_reconciliation":
        render_bank_reconciliation()
    elif page == "cash_flow_statement":
        render_cash_flow_statement()
    elif page == "audit_log":
        render_audit_log()
    elif page == "settings":
        render_settings()
    else:
        # 未知页面，回退到 dashboard
        render_dashboard()


@ui.page("/")
def index():
    if state.current_user is None:
        render_login()
    else:
        render_header()
        with ui.row().classes("w-full main-row"):
            render_sidebar()
            with ui.column().classes("main-content-area flex-grow gap-3") as state.main_content:
                render_page()


# ── 注入全局 CSS & JS ──
import os
_CSS_PATH = os.path.join(os.path.dirname(__file__), "app", "static", "style.css")
_JS_PATH  = os.path.join(os.path.dirname(__file__), "app", "static", "script.js")
if os.path.exists(_CSS_PATH):
    with open(_CSS_PATH) as _css_f:
        ui.add_head_html(f"<style>{_css_f.read()}</style>", shared=True)
if os.path.exists(_JS_PATH):
    with open(_JS_PATH) as _js_f:
        ui.add_head_html(f"<script>{_js_f.read()}</script>", shared=True)

# ── 手机端抽屉式侧边栏 + 遮罩层 ──

# Google Fonts
ui.add_head_html('''
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700&display=swap" rel="stylesheet">
''', shared=True)


# ── 启动 ──
if __name__ == "__main__":
    ui.run(
        title="AI 财务系统 v3",
        port=8090,
        host="0.0.0.0",
        reload=False,
        show=False,
        language="zh-CN",
    )
