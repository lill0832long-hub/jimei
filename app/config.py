"""配置常量"""
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "finance.db")

# ── 页面列表 ──
PAGES = [
    "dashboard", "journal", "voucher_detail", "accounts",
    "balance_sheet", "income_statement", "close_period",
    "charts", "compare", "ai_assistant",
    "import", "export", "settings",
    "fixed_assets", "cashier", "auxiliary",
    "tax", "cash_flow", "budget", "scheduled_vouchers",
    "invoices", "multi_currency", "audit_log",
    "setup_wizard", "voucher_template", "account_ledger",
    "bank_reconciliation", "cash_flow_statement",
]

# ── 页面路由表 ──
_page_routes = {}

def register_page(page_key, render_fn):
    """注册页面渲染函数"""
    _page_routes[page_key] = render_fn

def get_page_render(page_key):
    """获取页面渲染函数"""
    return _page_routes.get(page_key)

def get_all_pages():
    """获取所有已注册页面"""
    return list(_page_routes.keys())
