"""UI辅助函数 — Sidebar v2 重做版"""
from nicegui import ui
from app.components.state import state
from database_v3 import query_db, get_ledgers

def format_amount(value, show_currency=True):
    """统一金额格式化：¥1,234.56 或 —"""
    if value is None:
        return "—"
    try:
        v = float(value)
        if show_currency:
            if v < 0:
                return f"¥({abs(v):,.2f})"
            return f"¥{v:,.2f}"
        else:
            if v < 0:
                return f"({abs(v):,.2f})"
            return f"{v:,.2f}"
    except (ValueError, TypeError):
        return "—"

def apply_table_style(table):
    """统一表格样式"""
    try:
        table.props("separator=cell")
        table.classes("styled-table")
    except:
        pass
    return table

def get_table_classes():
    return "w-full text-sm bordered"

def get_table_header_classes():
    return "table-header-cell"

def show_toast(message, msg_type="info"):
    colors = {
        "success": ("positive", "✓"),
        "error": ("negative", "✗"),
        "warning": ("warning", "⚠"),
        "info": ("info", "ℹ"),
    }
    color, icon = colors.get(msg_type, ("info", "ℹ"))
    ui.notify(f"{icon} {message}", color=color, position="top", timeout=4000)

def show_field_error(input_elem, message):
    try:
        input_elem.props("error")
        input_elem.props(f'title="{message}"')
    except:
        pass

def show_page_error(container, title="出错了", message="请稍后重试", retry_fn=None):
    container.clear()
    with container:
        with ui.column().classes("items-center justify-center py-12 gap-3"):
            ui.label("⚠").classes("text-4xl")
            ui.label(title).classes("text-lg font-semibold").style("color:var(--c-text-primary)")
            ui.label(message).classes("text-sm").style("color:var(--c-text-secondary)")
            if retry_fn:
                ui.button("重试", color="primary", on_click=retry_fn).props("dense")

def show_modal_error(title="错误", message=""):
    with ui.dialog() as dialog, ui.card():
        ui.label(title).classes("text-lg font-semibold mb-2")
        ui.label(message).classes("text-sm").style("color:var(--c-text-secondary)")
        ui.button("确定", color="primary", on_click=dialog.close).classes("mt-3 w-full")
    dialog.open()


# ===== 导航 =====

def navigate(page):
    """页面导航 — Sidebar v2 架构
    
    导航时只重渲染主内容区，sidebar 由 JS 接管（切换 active class）。
    只有 sidebar 折叠/展开时才需要重渲染 sidebar。
    """
    if page == state.current_page:
        return
    state.current_page = page
    state.selected_voucher_no = None
    _rebuild_content()  # 只重渲染 main_content，sidebar 不动


# ===== 全局搜索 =====

def open_global_search():
    """全局搜索弹窗 — Ctrl+K 触发"""
    with ui.dialog() as search_dialog, ui.card().style("width: 600px; max-width: 90vw;"):
        ui.label("全局搜索").classes("text-lg font-bold mb-2")
        ui.label("搜索凭证号、摘要、科目名称、金额").classes("text-xs mb-3").style("color:var(--c-text-muted)")
        search_input = ui.input("输入关键词...", icon="search").props("autofocus outlined dense").classes("full-width mb-3")
        results_area = ui.column().classes("gap-1").style("max-height: 400px; overflow-y: auto;")

        def do_search():
            results_area.clear()
            kw = search_input.value.strip()
            if not kw:
                return
            vouchers = search_vouchers(kw)
            if vouchers:
                with results_area:
                    ui.label(f"📋 凭证 ({len(vouchers)}条)").classes("text-xs font-bold mt-2 mb-1").style("color:var(--c-text-muted)")
                    for v in vouchers[:10]:
                        with ui.row().classes("items-center gap-2 p-2 rounded hover:bg-blue-5 cursor-pointer") \
                                .on_click(lambda vno=v['voucher_no']: (search_dialog.close(), navigate('journal'), show_voucher_detail(vno))):
                            ui.label(v['voucher_no']).classes("text-sm font-mono w-24").style("color:var(--c-primary)")
                            ui.label(v.get('summary', '')[:30]).classes("text-sm flex-1").style("color:var(--c-text-secondary)")
                            ui.label(v.get('date', '')).classes("text-xs").style("color:var(--c-text-muted)")
            accounts = search_accounts_by_kw(kw)
            if accounts:
                with results_area:
                    ui.label(f"📖 科目 ({len(accounts)}条)").classes("text-xs font-bold mt-2 mb-1").style("color:var(--c-text-muted)")
                    for a in accounts[:10]:
                        with ui.row().classes("items-center gap-2 p-2 rounded hover:bg-blue-5 cursor-pointer"):
                            ui.label(a['code']).classes("text-sm font-mono w-16").style("color:var(--c-success)")
                            ui.label(a.get('name', '')).classes("text-sm").style("color:var(--c-text-secondary)")
            if not vouchers and not accounts:
                with results_area:
                    ui.label("未找到匹配结果").classes("text-sm p-4 text-center").style("color:var(--c-text-muted)")

        search_input.on("keydown.enter", do_search)
        ui.button("搜索", icon="search", on_click=do_search).props("dense color=primary").classes("mt-2")

    search_dialog.open()


# ===== Loading 状态管理 =====
_loading_dialog = None

def show_loading(text="加载中..."):
    global _loading_dialog
    if _loading_dialog is not None:
        try:
            _loading_dialog.close()
        except Exception:
            pass
    _loading_dialog = ui.dialog()
    with _loading_dialog, ui.card().classes("items-center gap-4 p-8"):
        ui.spinner("dots", size="3x")
        ui.label(text).style("color:var(--c-text-secondary)")
    _loading_dialog.open()

def hide_loading():
    global _loading_dialog
    if _loading_dialog is not None:
        try:
            _loading_dialog.close()
        except Exception:
            pass
        _loading_dialog = None


# ===== 内容重渲染 =====

def refresh_main():
    _rebuild_content()


def _rebuild_content():
    """重渲染主内容区（sidebar 由 JS 接管，不重渲染）"""
    if state.main_content is None:
        return
    state.main_content.clear()
    with state.main_content:
        import sys as _sys
        _main_mod = _sys.modules.get('__main__')
        if _main_mod is None:
            raise RuntimeError('__main__ module not found')
        _render_page = getattr(_main_mod, 'render_page', None)
        if _render_page is None:
            raise RuntimeError('render_page not found in __main__')
        _render_page()
    # 通知 JS 切换 active 状态
    try:
        ui.run_javascript(f"""
            if (window.sidebarCtrl && window.sidebarCtrl.setActiveItem) {{
                window.sidebarCtrl.setActiveItem('{state.current_page}');
            }}
        """)
    except Exception:
        pass


# ===== Header =====

def render_header():
    """顶部导航栏"""
    # 选择框居中样式（只添加一次）
    if not state._header_css_added:
        ui.add_head_html('''
        <style>
        .header-select .q-field__control,
        .header-select .q-field__native,
        .header-select .q-field__control > div,
        .header-year-select .q-field__control,
        .header-year-select .q-field__native,
        .header-year-select .q-field__control > div,
        .header-month-select .q-field__control,
        .header-month-select .q-field__native,
        .header-month-select .q-field__control > div {
            text-align: center !important;
            justify-content: center !important;
        }
        </style>
        ''')
        state._header_css_added = True

    with ui.header().props("elevated").classes("header-bar"):
        with ui.element("div").classes("header-grid"):
            with ui.row().classes("header-left items-center gap-2"):
                # 汉堡菜单按钮（手机端显示）
                ui.button(icon="menu", on_click=lambda: ui.run_javascript("window.sidebarCtrl&&window.sidebarCtrl.toggleDrawer()"))                     .props("flat dense").classes("hamburger-btn")
                ui.icon("account_balance").classes("header-logo-icon")
                ui.label("AI财务系统").classes("header-title")
                ui.label("v3.0").classes("header-version")
                with ui.element("div").classes("header-divider"):
                    pass
                ledgers = get_ledgers()
                ledger_options = {l["id"]: l['name'] for l in ledgers}
                if ledger_options:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("business").classes("header-ledger-icon")
                        ui.select(
                            options=ledger_options,
                            value=state.selected_ledger_id or (ledgers[0]["id"] if ledgers else None),
                            on_change=lambda e: [setattr(state,'selected_ledger_id',e.value), refresh_main()]
                        ).props("dense dark").classes("header-select")

            with ui.row().classes("header-center items-center gap-2").style("justify-content: center"):
                ui.select(
                    list(range(2024,2031)), value=state.selected_year,
                    on_change=lambda e: [setattr(state,'selected_year',e.value), refresh_main()]
                ).props("dense dark input-style=\"text-align: center\"").classes("header-year-select")
                ui.label("年").classes("header-period-label")
                ui.select(
                    list(range(1,13)), value=state.selected_month,
                    on_change=lambda e: [setattr(state,'selected_month',e.value), refresh_main()]
                ).props("dense dark input-style=\"text-align: center\"").classes("header-month-select")
                ui.label("月").classes("header-period-label")

            with ui.row().classes("header-right items-center gap-3"):
                ui.button(icon="search", color="primary", on_click=open_global_search) \
                    .props("dense flat round data-search-trigger=true").classes("header-search-btn")
                ui.label("Ctrl+K").classes("text-xs").style("color:var(--c-text-muted)")
                if state.current_user:
                    with ui.element("div").classes("header-notif-wrapper"):
                        ui.icon("notifications").classes("header-notif-icon")
                        with ui.element("div").classes("header-notif-dot"):
                            pass
                    with ui.row().classes("items-center gap-2"):
                        first_letter = state.current_user['username'][0].upper() if state.current_user['username'] else "U"
                        with ui.element("div").classes("header-avatar"):
                            ui.label(first_letter)
                        with ui.column().classes("gap-0 leading-tight"):
                            ui.label(f"{state.current_user['username']}").classes("header-username")
                            role_text = "管理员" if state.current_user['role'] == 'admin' else "操作员"
                            ui.label(role_text).classes("header-role")
                    ui.button(icon="dark_mode", on_click=lambda: ui.run_javascript("toggleDarkTheme()")) \
                        .props("flat dense").classes("header-logout-btn").classes("mr-1")

                    def _logout():
                        state.current_user = None
                        state.current_page = "dashboard"
                        ui.navigate.to("/")
                    ui.button(icon="logout", on_click=_logout).props("flat dense").classes("header-logout-btn")


# ===== Sidebar v2 =====

# ── 分组定义（4个主分组 + 底部固定入口）──
# 按工作流组织：工作台 → 账务处理 → 报表中心 → 财务管理
_nav_groups = [
    {
        "key": "work",
        "label": "工作台",
        "icon": "dashboard",
        "items": [
            ("dashboard", "仪表盘", "dashboard"),
            ("ai_assistant", "AI助手", "smart_toy"),
        ],
    },
    {
        "key": "operations",
        "label": "账务处理",
        "icon": "edit_note",
        "items": [
            ("journal", "记账凭证", "edit_note"),
            ("voucher_detail", "凭证详情", "description"),
            ("import", "批量导入", "cloud_upload"),
            ("invoices", "发票管理", "receipt_long"),
        ],
    },
    {
        "key": "reports",
        "label": "报表中心",
        "icon": "assessment",
        "items": [
            ("balance_sheet", "资产负债表", "account_balance"),
            ("income_statement", "利润表", "trending_up"),
            ("cash_flow", "现金流量表", "waterfall_chart"),
            ("cash_flow_statement", "现金流量表(新)", "waterfall_chart"),
            ("account_ledger", "科目明细账", "table_chart"),
            ("accounts", "科目余额表", "table_chart"),
            ("charts", "图表分析", "bar_chart"),
            ("compare", "对比分析", "compare_arrows"),
        ],
    },
    {
        "key": "finance",
        "label": "财务管理",
        "icon": "account_balance_wallet",
        "items": [
            ("cashier", "出纳管理", "point_of_sale"),
            ("bank_reconciliation", "银行对账", "account_balance"),
            ("fixed_assets", "固定资产", "precision_manufacturing"),
            ("auxiliary", "辅助核算", "hub"),
            ("tax", "增值税管理", "receipt"),
            ("budget", "预算管理", "savings"),
            ("scheduled_vouchers", "定时凭证", "schedule_send"),
            ("multi_currency", "多币种", "currency_exchange"),
            ("close_period", "期末结转", "sync_alt"),
        ],
    },
]

# ── 底部固定入口（不参与分组折叠）──
_bottom_items = [
    ("audit_log", "审计日志", "fact_check"),
    ("export", "数据导出", "cloud_download"),
    ("settings", "系统设置", "settings"),
]


def render_sidebar():
    """左侧导航菜单 v3 — Python状态驱动分组折叠
    
    改进：
    1. 分组折叠/展开由 Python state.sidebar_group_expanded 控制，不依赖 JS
    2. 整体折叠按钮同时重渲染 sidebar + 切换 CSS class
    3. 菜单项使用 flex-start 对齐（更自然的阅读体验）
    4. 分组标题有颜色左边框，视觉层次清晰
    5. 折叠按钮在底部，hover 变蓝色
    """
    # ── 初始化分组折叠状态（首次渲染） ──
    if state.sidebar_group_expanded is None:
        state.sidebar_group_expanded = {
            "work": True,
            "operations": True,
            "reports": True,
            "finance": True,
        }

    # ── 获取或创建 sidebar 容器 ──
    _need_new_container = (
        not hasattr(state, '_sidebar_container') or
        state._sidebar_container is None
    )
    if not _need_new_container:
        try:
            state._sidebar_container.client
        except (RuntimeError, AttributeError):
            _need_new_container = True
    if _need_new_container:
        sidebar_classes = "sidebar-nav h-full"
        if state.sidebar_collapsed:
            sidebar_classes += " sidebar-collapsed"
        state._sidebar_container = ui.column().classes(sidebar_classes)
    sidebar_el = state._sidebar_container
    sidebar_el.clear()
    if state.sidebar_collapsed:
        sidebar_el.classes("sidebar-collapsed")
    else:
        sidebar_el.classes(remove="sidebar-collapsed")

    with sidebar_el:
        # ── Logo ──
        with ui.element("div").classes("sidebar-logo"):
            ui.icon("account_balance").classes("sidebar-logo-icon")
            if not state.sidebar_collapsed:
                ui.label("AI财务").classes("sidebar-logo-text")

        # ── 分组导航 ──
        for group_idx, group in enumerate(_nav_groups):
            gkey = group["key"]
            glabel = group["label"]
            gicon = group["icon"]
            items = group["items"]
            is_expanded = state.sidebar_group_expanded.get(gkey, True)

            if group_idx > 0:
                with ui.element("div").classes("sidebar-group-divider"):
                    pass

            # 分组标题（点击折叠/展开）— Python 驱动
            arrow = "expand_less" if is_expanded else "expand_more"
            header_classes = "sidebar-group-header" + (" sidebar-group-header--expanded" if is_expanded else "")
            with ui.button(on_click=lambda _k=gkey: _toggle_sidebar_group(_k)).props(
                "flat no-caps align-left"
            ).classes(header_classes).style(
                "height: 36px; padding: 0 12px; gap: 6px; width: 100%; "
                "border-radius: 6px; margin: 2px 4px; justify-content: flex-start; "
                "background: rgba(255,255,255,0.04);"
            ):
                ui.icon(gicon).classes("sidebar-group-icon")
                if not state.sidebar_collapsed:
                    ui.label(glabel).classes("sidebar-group-label")
                    with ui.element("div").style("flex-grow: 1"):
                        pass
                    ui.icon(arrow).classes("sidebar-group-arrow")

            # 分组内容（Python 控制显隐）
            if is_expanded and not state.sidebar_collapsed:
                for key, label, item_icon in items:
                    is_active = state.current_page == key
                    btn_classes = "sidebar-menu-item" + (" sidebar-menu-active" if is_active else "")
                    _p = "flat no-caps align-left data-page=" + str(key) + " data-label=" + str(label)
                    with ui.button(on_click=lambda k=key: navigate(k)).props(_p).classes(btn_classes):
                        ui.icon(item_icon).classes("sidebar-menu-icon")
                        ui.label(label).classes("sidebar-menu-label")

        # ── 底部固定区域 ──
        with ui.element("div").classes("sidebar-spacer"):
            pass
        with ui.element("div").classes("sidebar-group-divider"):
            pass

        for key, label, item_icon in _bottom_items:
            is_active = state.current_page == key
            btn_classes = "sidebar-menu-item" + (" sidebar-menu-active" if is_active else "")
            _p = "flat no-caps align-left data-page=" + str(key) + " data-label=" + str(label)
            with ui.button(on_click=lambda k=key: navigate(k)).props(_p).classes(btn_classes):
                ui.icon(item_icon).classes("sidebar-menu-icon")
                ui.label(label).classes("sidebar-menu-label")

        # ── 折叠按钮 ──
        with ui.element("div").classes("sidebar-collapse-row"):
            collapse_icon = "chevron_left" if not state.sidebar_collapsed else "chevron_right"
            # 折叠：只更新 state + JS 切换，不重渲染 sidebar（避免 DOM 重建覆盖 JS 动画）
            ui.button(icon=collapse_icon, on_click=_toggle_sidebar_collapse).props("flat dense").classes("sidebar-collapse-btn")


def _toggle_sidebar_group(gkey):
    """切换分组折叠状态并重新渲染 sidebar"""
    if state.sidebar_group_expanded is None:
        state.sidebar_group_expanded = {}
    current = state.sidebar_group_expanded.get(gkey, True)
    state.sidebar_group_expanded[gkey] = not current
    _refresh_sidebar()


def _toggle_sidebar_collapse():
    """切换 sidebar 整体折叠状态并重新渲染 sidebar"""
    state.sidebar_collapsed = not state.sidebar_collapsed
    _refresh_sidebar()


def _refresh_sidebar():
    """重新渲染 sidebar（不重建主内容）"""
    # 直接调用 render_sidebar，它会 clear() 容器并重新填充内容
    # 容器引用保持不变，确保 DOM 位置正确
    render_sidebar()
