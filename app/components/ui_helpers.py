"""UI辅助函数 — Sidebar v2 重做版"""
from nicegui import ui
from app.components.state import state
from app.services import LedgerService, VoucherService, AccountService


def get_ledgers():
    return LedgerService.get_all()

def search_vouchers(keyword, limit=10):
    return VoucherService.search(state.selected_ledger_id, keyword=keyword, limit=limit)

def search_accounts_by_kw(keyword, limit=10):
    return AccountService.search(keyword, limit)
# show_voucher_detail imported locally in open_global_search to avoid circular import

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
    except Exception:
        pass
    return table

def get_table_classes():
    return "w-full text-sm bordered"

def get_table_header_classes():
    return "table-header-cell"

def show_toast(message, msg_type="info", duration=4000, icon=None, close_button=False):
    colors = {
        "success": ("positive", "✓"),
        "error": ("negative", "✗"),
        "warning": ("warning", "⚠"),
        "info": ("info", "ℹ"),
    }
    default_color, default_icon = colors.get(msg_type, ("info", "ℹ"))
    display_icon = icon if icon is not None else default_icon
    kwargs = dict(color=default_color, position="top", timeout=duration)
    if close_button:
        kwargs["close_button"] = close_button if isinstance(close_button, str) else "close"
    ui.notify(f"{display_icon} {message}", **kwargs)

def show_field_error(input_elem, message):
    try:
        input_elem.props("error")
        input_elem.props(f'title="{message}"')
    except Exception:
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

# 导航到这些页面时需要保留 selected_voucher_no
_PAGES_KEEPING_VOUCHER = {"voucher_detail", "journal"}

def navigate(page):
    """页面导航 — Tab 架构

    Python 是唯一导航逻辑源。
    导航时：若页面已在 tabs 中则切换到该 tab，否则新建 tab。
    sidebar 本身不重渲染（避免 NiceGUI DOM diff 导致的容器重复问题）。
    """
    if page == state.current_page and state.tabs and state.active_tab_idx < len(state.tabs):
        # 检查当前 tab 是否已经是目标页面（避免重复点击当前 tab 时重建）
        if state.tabs[state.active_tab_idx]["key"] == page:
            return

    # 查找是否已有该页面的 tab
    existing_idx = None
    for i, tab in enumerate(state.tabs):
        if tab["key"] == page:
            existing_idx = i
            break

    if existing_idx is not None:
        # 切换到已有 tab
        state.active_tab_idx = existing_tab_idx = existing_idx
    else:
        # 新建 tab
        label = state.get_tab_label(page)
        state.tabs.append({"key": page, "label": label})
        state.active_tab_idx = len(state.tabs) - 1

    state.current_page = page

    # 仅在导航到与凭证无关的页面时清理选中凭证
    if page not in _PAGES_KEEPING_VOUCHER:
        state.selected_voucher_no = None

    # 使用 timer 延迟执行，避免在 click handler 中直接 clear() 导致 RuntimeError
    ui.timer(0.05, _rebuild_tabs, once=True)

    # 同步 sidebar active 类（纯视觉，不触发导航）
    ui.run_javascript(f"window.sidebarCtrl&&window.sidebarCtrl.setActiveItem('{page}')")


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
                                .on_click(lambda vno=v['voucher_no']: (
                                    search_dialog.close(),
                                    setattr(state, 'selected_voucher_no', vno),
                                    navigate('journal'),
                                )):
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
    # 延迟执行，避免在 click handler 中直接 clear() 导致 RuntimeError
    ui.timer(0.05, _rebuild_content, once=True)


def _rebuild_content():
    """重渲染主内容区（sidebar 由 JS 接管，不重渲染）"""
    if state.main_content is None:
        return
    # 检查 main_content client 是否存活
    try:
        _ = state.main_content.client
    except RuntimeError:
        state.main_content = None
        return
    from app.config import get_page_render
    state.main_content.clear()
    with state.main_content:
        render_fn = get_page_render(state.current_page)
        if render_fn:
            render_fn()
        else:
            from app.pages.dashboard import render_dashboard
            render_dashboard()


def _rebuild_tabs():
    """重渲染 tab 栏 + 当前 tab 内容"""
    _rebuild_tab_bar()
    _rebuild_tab_content()


def _rebuild_tab_bar():
    """重渲染 tab 栏（仅 tab 标签部分）"""
    if state.tab_bar_container is None:
        return
    try:
        _ = state.tab_bar_container.client
    except RuntimeError:
        state.tab_bar_container = None
        return
    state.tab_bar_container.clear()
    with state.tab_bar_container:
        tabs = state.tabs
        active_idx = state.active_tab_idx
        for i, tab in enumerate(tabs):
            is_active = (i == active_idx)
            tab_label = tab["label"]
            # tab 样式
            if is_active:
                tab_classes = "tab-item tab-item--active"
            else:
                tab_classes = "tab-item tab-item--inactive"

            with ui.row().classes(tab_classes).on_click(lambda _i=i: switch_tab(_i)):
                ui.label(tab_label).classes("tab-label")
                ui.button(icon="close", on_click=lambda _i=i: close_tab(_i)).props(
                    "flat dense round size=xs"
                ).classes("tab-close-btn").style("min-width:24px;min-height:24px;")


def _rebuild_tab_content():
    """重渲染当前 tab 的内容区"""
    if state.tab_contents is None:
        # 兼容旧模式：使用 main_content
        _rebuild_content()
        return
    try:
        _ = state.tab_contents.client
    except RuntimeError:
        state.tab_contents = None
        _rebuild_content()
        return
    from app.config import get_page_render
    state.tab_contents.clear()
    with state.tab_contents:
        render_fn = get_page_render(state.current_page)
        if render_fn:
            render_fn()
        else:
            from app.pages.dashboard import render_dashboard
            render_dashboard()


def switch_tab(idx):
    """切换到指定索引的 tab"""
    if idx < 0 or idx >= len(state.tabs):
        return
    if idx == state.active_tab_idx:
        return
    state.active_tab_idx = idx
    state.current_page = state.tabs[idx]["key"]
    ui.timer(0.05, _rebuild_tabs, once=True)
    # 同步 sidebar active 类
    ui.run_javascript(f"window.sidebarCtrl&&window.sidebarCtrl.setActiveItem('{state.current_page}')")


def close_tab(idx):
    """关闭指定索引的 tab"""
    tabs = state.tabs
    if idx < 0 or idx >= len(tabs):
        return
    # 删除 tab
    tabs.pop(idx)
    if len(tabs) == 0:
        # 没有 tab 了，创建默认 dashboard tab
        state.tabs = [{"key": "dashboard", "label": state.get_tab_label("dashboard")}]
        state.active_tab_idx = 0
        state.current_page = "dashboard"
    else:
        # 关闭的是当前激活 tab
        if idx == state.active_tab_idx:
            # 切换到前一个 tab（如果关闭的是第一个，则切到新的第一个）
            new_idx = max(0, idx - 1)
            state.active_tab_idx = new_idx
            state.current_page = tabs[new_idx]["key"]
        elif idx < state.active_tab_idx:
            # 关闭的是当前 tab 前面的 tab，索引前移
            state.active_tab_idx -= 1
        # 关闭的是后面的 tab，不需要调整 active_tab_idx
    ui.timer(0.05, _rebuild_tabs, once=True)
    # 同步 sidebar active 类
    ui.run_javascript(f"window.sidebarCtrl&&window.sidebarCtrl.setActiveItem('{state.current_page}')")


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
            font-family: var(--font-stack) !important;
        }
        </style>
        ''')
        state._header_css_added = True

    with ui.header().props("elevated").classes("header-bar"):
        with ui.element("div").classes("header-grid"):
            with ui.row().classes("header-left items-center") \
                    .style("gap: 16px;"):
                # 汉堡菜单按钮（手机端显示）
                ui.button(icon="menu", on_click=lambda: ui.run_javascript("window.sidebarCtrl&&window.sidebarCtrl.toggleDrawer()"))                     .props("flat dense").classes("hamburger-btn")
                ui.icon("account_balance").classes("header-logo-icon")
                ui.label("AI财务系统").classes("header-title")
                ui.label("v5.1").classes("header-version")
                with ui.element("div").classes("header-divider"):
                    pass
                ledgers = get_ledgers()
                ledger_options = {l["id"]: l['name'] for l in ledgers}
                if ledger_options:
                    with ui.row().classes("items-center").style("gap: 6px;"):
                        ui.icon("business").classes("header-ledger-icon")
                        ui.select(
                            options=ledger_options,
                            value=state.selected_ledger_id or (ledgers[0]["id"] if ledgers else None),
                            on_change=lambda e: [setattr(state,'selected_ledger_id',e.value), refresh_main()]
                        ).props("dense").classes("header-select")

            with ui.row().classes("header-center items-center gap-2").style("justify-content: center"):
                ui.select(
                    list(range(2024,2031)), value=state.selected_year,
                    on_change=lambda e: [setattr(state,'selected_year',e.value), refresh_main()]
                ).props("dense input-style=\"text-align: center; font-family: var(--font-stack); font-size: 14px; font-weight: 700; color: var(--c-text-primary);\"").classes("header-year-select")
                ui.label("年").classes("header-period-label")
                ui.select(
                    list(range(1,13)), value=state.selected_month,
                    on_change=lambda e: [setattr(state,'selected_month',e.value), refresh_main()]
                ).props("dense input-style=\"text-align: center; font-family: var(--font-stack); font-size: 14px; font-weight: 700; color: var(--c-text-primary);\"").classes("header-month-select")
                ui.label("月").classes("header-period-label")

            with ui.row().classes("header-right items-center") \
                    .style("gap: 12px;"):
                ui.button(icon="search", on_click=open_global_search) \
                    .props("flat round dense").classes("header-search-btn")
                if state.current_user:
                    with ui.element("div").classes("header-notif-wrapper"):
                        ui.icon("notifications").classes("header-notif-icon")
                        with ui.element("div").classes("header-notif-dot"):
                            pass
                    with ui.row().classes("items-center").style("gap: 8px;"):
                        _username = state.current_user.get('username', '') if state.current_user else ''
                        first_letter = _username[0].upper() if _username else "U"
                        with ui.element("div").classes("header-avatar"):
                            ui.label(first_letter)
                        with ui.column().classes("gap-0 leading-tight"):
                            ui.label(_username).classes("header-username")
                            role_text = "管理员" if (state.current_user or {}).get('role') == 'admin' else "操作员"
                            ui.label(role_text).classes("header-role")
                    ui.button(icon="edit_note", on_click=lambda: ui.run_javascript("window._annot&&window._annot.toggle()")) \
                        .props("flat dense round").classes("header-icon-btn").tooltip("标注页面")
                    ui.button(icon="dark_mode", on_click=lambda: ui.run_javascript("toggleDarkTheme()")) \
                        .props("flat dense round").classes("header-icon-btn")

                    def _logout():
                        state.current_user = None
                        state.current_page = "dashboard"
                        ui.navigate.to("/")
                    ui.button(icon="logout", on_click=_logout).props("flat dense round").classes("header-icon-btn")


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
            ("import", "批量导入", "cloud_upload"),
            ("invoices", "发票管理", "receipt_long"),
        ],
    },
    {
        "key": "reports",
        "label": "报表中心",
        "icon": "assessment",
        "items": [
            ("trial_balance", "科目余额表", "grid_on"),
            ("balance_sheet", "资产负债表", "account_balance"),
            ("income_statement", "利润表", "trending_up"),
            ("cash_flow_statement", "现金流量表", "waterfall_chart"),
            ("account_ledger", "科目明细账", "table_chart"),
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
    ("about", "关于", "info"),
]


def _build_sidebar_content(sidebar_el):
    """向 sidebar 容器中填充内容（不创建新容器）"""
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
            "padding: 0 16px; gap: 8px; width: 100%; "
            "border-radius: 0; margin: 6px 0 2px 0; justify-content: flex-start; "
            "background: transparent;"
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
                with ui.button(on_click=lambda k=key: navigate(k)).props(_p).classes(btn_classes) \
                        .style("margin: 2px 8px;"):
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
        with ui.button(on_click=lambda k=key: navigate(k)).props(_p).classes(btn_classes) \
                .style("margin: 2px 8px;"):
            ui.icon(item_icon).classes("sidebar-menu-icon")
            ui.label(label).classes("sidebar-menu-label")

    # ── 折叠按钮 ──
    with ui.element("div").classes("sidebar-collapse-row"):
        collapse_icon = "chevron_left" if not state.sidebar_collapsed else "chevron_right"
        ui.button(icon=collapse_icon, on_click=_toggle_sidebar_collapse).props("flat dense").classes("sidebar-collapse-btn")


def render_sidebar():
    """左侧导航菜单 — 创建 sidebar 容器并填充内容"""
    _init_sidebar_state()
    sidebar_classes = "sidebar-nav h-full"
    if state.sidebar_collapsed:
        sidebar_classes += " sidebar-collapsed"
    state._sidebar_container = ui.column().classes(sidebar_classes)
    sidebar_el = state._sidebar_container
    with sidebar_el:
        _build_sidebar_content(sidebar_el)


def _init_sidebar_state():
    """初始化分组折叠状态（首次渲染）"""
    if state.sidebar_group_expanded is None:
        state.sidebar_group_expanded = {
            "work": True,
            "operations": True,
            "reports": True,
            "finance": True,
        }


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
    if state._sidebar_container is None:
        return
    try:
        _ = state._sidebar_container.client
    except RuntimeError:
        state._sidebar_container = None
        return
    # 更新 CSS 类
    if state.sidebar_collapsed:
        state._sidebar_container.classes("sidebar-collapsed")
    else:
        state._sidebar_container.classes(remove="sidebar-collapsed")
    # 清空旧内容，重建
    state._sidebar_container.clear()
    with state._sidebar_container:
        _build_sidebar_content(state._sidebar_container)
