"""登录/登出"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast
from app.services import AuthService, LedgerService


def do_logout():
    """登出"""
    state.current_user = None
    state.current_page = "dashboard"
    ui.run_javascript("document.cookie='sess=;path=/;max-age=0'")
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

                # 记住我
                remember_me = ui.checkbox("记住我").classes("mt-2 login-remember")

                # 加载状态标记
                login_btn = ui.button("登 录") \
                    .props("unelevated no-caps").classes("login-submit-btn w-full mt-4")

                def _clear_errors():
                    """清除输入框的错误状态"""
                    username.props(remove="error")
                    username.props(remove="title")
                    password.props(remove="error")
                    password.props(remove="title")

                def _try_login():
                    _clear_errors()
                    u = username.value if username.value is not None else ""
                    u = u.strip()
                    p = password.value if password.value is not None else ""
                    # 前端校验：用户名为空
                    if not u:
                        username.props("error")
                        username.props("title=请输入用户名")
                        show_toast("请输入用户名", "warning")
                        username.run_method("focus")
                        return
                    # 前端校验：密码为空
                    if not p:
                        password.props("error")
                        password.props("title=请输入密码")
                        show_toast("请输入密码", "warning")
                        password.run_method("focus")
                        return
                    do_login(u, p, login_btn, remember_me.value, username)

                login_btn.on_click(_try_login)
                username.on("keydown.enter", _try_login)
                password.on("keydown.enter", _try_login)

                # 页面加载时恢复记住的用户名
                ui.run_javascript("""
                    const saved = localStorage.getItem('remembered_username');
                    if (saved) {
                        // 延迟设置，等待组件挂载
                        setTimeout(() => {
                            const input = document.querySelector('.login-input input');
                            if (input) {
                                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                                    window.HTMLInputElement.prototype, 'value'
                                ).set;
                                nativeInputValueSetter.call(input, saved);
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        }, 300);
                    }
                """)

            # 底部提示
            with ui.element("div").classes("login-footer"):
                ui.label("请联系管理员获取账号").classes("login-hint-text")
                ui.label("© 2026 AI 财务系统").classes("login-hint-text mt-2")


def do_login(username, password, login_btn, remember, username_input):
    """执行登录逻辑

    Args:
        username: 用户名
        password: 密码
        login_btn: 登录按钮引用（用于控制加载状态）
        remember: 是否记住我
        username_input: 用户名输入框引用（用于错误标记）
    """
    # 开始加载动画，禁用按钮
    login_btn.props("loading")

    user = AuthService.authenticate(username, password)
    if user:
        # 处理「记住我」
        if remember:
            ui.run_javascript(
                f"localStorage.setItem('remembered_username', '{username}')"
            )
        else:
            ui.run_javascript("localStorage.removeItem('remembered_username')")

        state.current_user = user
        state.current_page = "dashboard"
        ledgers = LedgerService.get_all()
        if ledgers and not state.selected_ledger_id:
            state.selected_ledger_id = ledgers[0].get("id")
        show_toast(f"✅ 欢迎，{user.get('username', '')}！", "success")
        login_btn.props(remove="loading")
        # 写 cookie 后强制页面刷新（ui.navigate 是 SPA 导航，不触发 index() 重新执行）
        import json as _json
        ui.run_javascript(
            "try{var d=JSON.stringify(" + _json.dumps({
                "id": str(user.get("id", "")),
                "username": str(user.get("username", "")),
                "role": str(user.get("role", "")),
            }) + ");"
            "document.cookie='sess='+encodeURIComponent(d)+';path=/;max-age=86400;SameSite=Lax';"
            "window.location.href='/';}catch(e){console.error(e)}"
        )
    else:
        # 登录失败：输入框标红 + 具体错误提示
        username_input.props("error")
        username_input.props("title=用户名或密码错误")
        show_toast("用户名或密码错误，请重新输入", "error")
        login_btn.props(remove="loading")
