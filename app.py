"""
AI 财务系统 — 模块化主入口
"""
import sys, os

# ── 版本信息 ──
VERSION = "5.1.0"
VERSION_NAME = "V5.1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ── Monkey-patch: 增大 Engine.IO 最大消息体积，防止复杂页面 WebSocket 报错 ──
# 必须在 import nicegui 之前执行，因为 nicegui 在导入时即创建 AsyncServer
import socketio as _sio_mod
_orig_sio_init = _sio_mod.AsyncServer.__init__
def _patched_sio_init(self, *args, **kwargs):
    kwargs.setdefault('max_http_buffer_size', 16 * 1024 * 1024)
    _orig_sio_init(self, *args, **kwargs)
_sio_mod.AsyncServer.__init__ = _patched_sio_init

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

# ── JS → Python 导航桥接（底部导航栏/抽屉菜单用）──
# JS 通过 fetch 写入目标页面到 app.storage，Python 端轮询检测并执行导航
_pending_nav_page = [None]  # 用 list 实现可变闭包

@app.post("/api/navigate/{page}")
async def api_navigate(page: str):
    """JS 导航入口：写入待导航页面（由 index() 中的 timer 消费）"""
    _pending_nav_page[0] = page

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
from app.pages.reports_center import render_reports_center
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
from app.pages.general_ledger import render_general_ledger
from app.pages.bank_reconciliation import render_bank_reconciliation
from app.pages.cash_flow_statement import render_cash_flow_statement
from app.pages.auth import render_login
from app.pages.journal_form import render_journal_form
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
register_page("general_ledger", render_general_ledger)
register_page("bank_reconciliation", render_bank_reconciliation)
register_page("cash_flow_statement", render_cash_flow_statement)
register_page("about", render_about)
register_page("audit_log", render_audit_log)
register_page("settings", render_settings)
register_page("journal_form", render_journal_form)
register_page("reports_center", render_reports_center)


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
    import os as _os, time as _time
    _static_dir = _os.path.join(_os.path.dirname(__file__), "app", "static")
    _css_dir = _os.path.join(_static_dir, "style")
    _css_path = _os.path.join(_css_dir, "index.css")
    _js_path = _os.path.join(_static_dir, "script.js")
    # 用 <link> 标签加载 CSS（支持浏览器缓存刷新），用时间戳强制更新
    _ts = str(int(_time.time()))
    if _os.path.exists(_css_path):
        import re as _re
        with open(_css_path, encoding="utf-8") as _f:
            _css_content = _f.read()
        _imports = _re.findall(r'@import\s+url\(["\']([^"\']+)["\']\);', _css_content)
        if _imports:
            for _imp in _imports:
                _mod_url = f"/static/style/{_imp}?v={_ts}"
                ui.add_head_html(f'<link rel="stylesheet" href="{_mod_url}">')
        else:
            ui.add_head_html(f'<link rel="stylesheet" href="/static/style/index.css?v={_ts}">')
    # JS 延迟到登录后主界面加载，减少登录页初始 HTML 体积
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700&display=swap" rel="stylesheet">'
    )

    # 从 cookie 恢复 session（登录后页面刷新，Python 内存状态丢失）
    import json as _json
    try:
        from nicegui import context
        session_cookie = context.client.cookies.get("sess")
        if session_cookie:
            data = _json.loads(session_cookie)
            state.current_user = {
                "id": data.get("id", 0),
                "username": data.get("username", data.get("u", "")),
                "role": data.get("role", data.get("r", "")),
            }
    except Exception:
        pass

    if state.current_user is None:
        render_login()
    else:
        # 主界面才加载 JS（登录页不需要）
        if _os.path.exists(_js_path):
            with open(_js_path, encoding="utf-8") as _f:
                ui.add_head_html(f"<script>{_f.read()}</script>")
        _ann_js_path = _os.path.join(_static_dir, "annotation.js")
        if _os.path.exists(_ann_js_path):
            with open(_ann_js_path, encoding="utf-8") as _f:
                ui.add_head_html(f"<script>{_f.read()}</script>")
        render_header()
        with ui.row().classes("w-full main-row"):
            render_sidebar()
            with ui.column().classes("main-content-area flex-grow gap-3") as state.main_content:
                # Tab 系统容器
                with ui.row().classes("w-full items-center gap-2") as state._tab_bar_container:
                    pass
                with ui.column().classes("w-full flex-grow") as state._tab_contents:
                    render_page()

        # ── JS 导航桥接轮询（消费底部导航栏/抽屉菜单的导航请求）──
        from app.components.ui_helpers import navigate as _navigate

        def _check_js_nav():
            page = _pending_nav_page[0]
            if page is not None:
                _pending_nav_page[0] = None
                _navigate(page)

        ui.timer(0.1, _check_js_nav)


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
        ws_max_size=16 * 1024 * 1024,  # 16MB WebSocket 消息上限
    )
