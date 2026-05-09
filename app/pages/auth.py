"""登录/登出"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast
from database_v3 import authenticate, get_ledgers


def do_logout():
    """登出"""
    state.current_user = None
    state.current_page = "dashboard"
    ui.navigate.to("/")


def render_login():
    """登录页 — 全屏居中卡片，深蓝渐变背景"""
    with ui.element("div").classes("login-page"):
        with ui.element("div").classes("login-card"):
            # 顶部 Logo 区域
            with ui.element("div").classes("login-header"):
                ui.icon("account_balance").classes("login-logo-icon")
                ui.label("AI 财务系统").classes("login-title")
                ui.label("智能记账 · 自动报表 · AI助手").classes("login-subtitle")

            # 登录表单
            with ui.element("div").classes("login-body"):
                username = ui.input("用户名", placeholder="请输入用户名") \
                    .props("outlined dense").classes("w-full login-input")
                password = ui.input("密码", password=True, password_toggle_button=True,
                                    placeholder="请输入密码") \
                    .props("outlined dense").classes("w-full login-input mt-3")

                def _try_login():
                    do_login(username.value, password.value)
                username.on("keydown.enter", _try_login)
                password.on("keydown.enter", _try_login)

                with ui.element("div").classes("mt-6"):
                    ui.button("登 录", on_click=_try_login) \
                        .props("unelevated no-caps").classes("login-submit-btn w-full")

            # 底部提示
            with ui.element("div").classes("login-footer"):
                ui.label("默认账户：admin / admin123").classes("login-hint-text")
                ui.label("© 2026 AI 财务系统").classes("login-hint-text mt-2")


def do_login(username, password):
    if not username or not password:
        show_toast("请输入用户名和密码", "warning")
        return
    user = authenticate(username, password)
    if user:
        state.current_user = user
        state.current_page = "dashboard"
        ledgers = get_ledgers()
        if ledgers and not state.selected_ledger_id:
            state.selected_ledger_id = ledgers[0]["id"]
        show_toast(f"✅ 欢迎，{user['username']}！", "success")
        ui.navigate.to("/")
    else:
        show_toast("❌ 用户名或密码错误", "error")
