"""统一 UI 组件库 — 财务系统标准化视觉组件

提供高复用、精致美观的 UI 组件：
- SectionHeader: 分组标题栏（带图标 + 可选操作按钮）
- KpiCard: KPI 指标卡片（大数字 + 趋势 + 点击跳转）
- EmptyState: 空状态展示
- StatusBadge: 状态标签
- DataTable: 标准化数据表格
- MoneyCell: 金额单元格
- FormSection: 表单分组容器
- PageHeader: 页面标题区
- MetricRow: 指标行（标签 + 值 + 趋势）
- TimelineItem: 时间线条目
"""
from nicegui import ui


# ─── 颜色映射 ───────────────────────────────────────────────────

_KPI_COLORS = {
    "blue":   ("var(--c-primary)",    "var(--c-primary-light)"),
    "red":    ("var(--c-danger)",     "var(--c-danger-light)"),
    "green":  ("var(--c-success)",    "var(--c-success-light)"),
    "purple": ("#7b1fa2",            "#f3e5f5"),
    "orange": ("var(--c-warning)",   "var(--c-warning-light)"),
    "indigo": ("#3949ab",            "#e8eaf6"),
    "cyan":   ("#00838d",            "#e0f7fa"),
    "teal":   ("#00695c",            "#e0f2f1"),
}

_STATUS_COLORS = {
    "success":  ("var(--c-success)",   "var(--c-success-light)",  "✓"),
    "error":    ("var(--c-danger)",    "var(--c-danger-light)",   "✗"),
    "warning":  ("var(--c-warning)",   "var(--c-warning-light)",  "⚠"),
    "info":     ("var(--c-primary)",   "var(--c-primary-light)",  "ℹ"),
    "draft":    ("var(--c-text-muted)","var(--c-border-light)",   "📝"),
    "pending":  ("#ea580c",           "#fff7ed",                 "⏳"),
    "approved": ("var(--c-success)",   "var(--c-success-light)",  "✓"),
    "rejected": ("var(--c-danger)",    "var(--c-danger-light)",   "✗"),
    "posted":   ("var(--c-success)",   "var(--c-success-light)",  "✓"),
    "reversed": ("var(--c-text-muted)","var(--c-border-light)",   "↩"),
}


# ─── SectionHeader ───────────────────────────────────────────────

def SectionHeader(title, icon=None, action=None, action_icon="add", action_color="primary"):
    """分组标题栏 — 精致的分区头，带图标和可选操作按钮

    用法:
        SectionHeader("凭证列表", icon="receipt", action=on_add, action_icon="add")
    """
    with ui.row().classes("w-full items-center justify-between mb-2"):
        with ui.row().classes("items-center gap-2"):
            if icon:
                ui.icon(icon).classes("text-base").style("color:var(--c-primary)")
            ui.label(title).classes("text-sm font-semibold").style("color:var(--c-text-primary)")
        if action:
            ui.button(action_icon, on_click=action).props(f"flat dense no-caps color={action_color}").classes("text-xs")


# ─── KpiCard ─────────────────────────────────────────────────────

def KpiCard(title, value, icon="analytics", color="blue", trend=None, trend_label=None,
            subtitle=None, on_click=None, col_classes="flex-1 min-w-0"):
    """KPI 指标卡片 — 大数字 + 图标 + 趋势标签 + 可点击跳转

    用法:
        KpiCard("资产总计", "¥1,234,567", "account_balance", "blue", trend="↑ 2.3%")
        KpiCard("本月收入", "¥89,000", "trending_up", "purple", trend="↑ 12.5%", on_click=go_income)
    """
    hex_c, bg_c = _KPI_COLORS.get(color, _KPI_COLORS["blue"])
    if trend:
        trend_color = ("var(--c-success)", "var(--c-success-light)") if "↑" in trend else \
                      ("var(--c-danger)", "var(--c-danger-light)") if "↓" in trend else \
                      ("var(--c-text-muted)", "var(--c-border-light)")
    else:
        trend_color = None

    card = ui.card().classes(f"kpi-card {col_classes}").props(f"data-color={color}")
    if on_click:
        card.style("cursor:pointer;")
        card.on("click", on_click)
    with card:
        with ui.card_section().classes("py-3 px-4"):
            with ui.row().classes("items-center gap-3"):
                with ui.element("div").style(
                    f"width:40px; height:40px; border-radius:10px; background:{bg_c}; "
                    f"display:flex; align-items:center; justify-content:center; flex-shrink:0;"
                ):
                    ui.icon(icon).classes("kpi-icon").style(f"color:{hex_c}")
                with ui.column().classes("gap-0.5 flex-1 min-w-0"):
                    ui.label(title).classes("text-xs font-medium truncate").style("color:var(--c-text-muted)")
                    ui.label(str(value)).classes("kpi-value").style(f"color:{hex_c} !important")
                    if subtitle:
                        ui.label(subtitle).classes("text-xs").style("color:var(--c-text-muted)")
            if trend and trend_color:
                tc, tb = trend_color
                with ui.row().classes("mt-1.5 ml-[52px]"):
                    ui.label(trend + (f" {trend_label}" if trend_label else "")).classes("kpi-trend").style(
                        f"color:{tc}; background:{tb};"
                    )


# ─── EmptyState ─────────────────────────────────────────────────

def EmptyState(icon="inbox", message="暂无数据", hint=None, action=None, action_label="去添加"):
    """标准空状态 — 居中图标 + 提示文字 + 可选操作按钮

    用法:
        EmptyState(message="暂无凭证", hint="点击下方按钮创建第一张凭证", action=on_add, action_label="创建凭证")
    """
    with ui.column().classes("items-center justify-center py-10 gap-2"):
        ui.icon(icon).classes("text-4xl").style("color:var(--c-text-muted)")
        ui.label(message).classes("text-sm font-medium").style("color:var(--c-text-secondary)")
        if hint:
            ui.label(hint).classes("text-xs").style("color:var(--c-text-muted)")
        if action:
            ui.button(action_label, on_click=action).props("flat dense no-caps color=primary").classes("mt-1 text-xs")


# ─── StatusBadge ────────────────────────────────────────────────

def StatusBadge(text, status="info"):
    """标准状态标签 — 统一颜色语义 + 图标

    用法:
        StatusBadge("已审核", "approved")
        StatusBadge("草稿", "draft")
    """
    color, bg, icon = _STATUS_COLORS.get(status, _STATUS_COLORS["info"])
    with ui.element("div").classes("inline-flex items-center gap-1 px-2 py-0.5 rounded"):
        ui.label(icon).classes("text-xs")
        ui.label(text).classes("text-xs font-medium")


# ─── DataTable ──────────────────────────────────────────────────

def DataTable(columns, rows, table_classes="w-full text-sm", row_key=None, on_row_click=None):
    """标准化数据表格 — 统一样式 + 自动空状态 + 可选行点击

    用法:
        DataTable(
            columns=[{"name":"no","label":"凭证号","field":"voucher_no"}, {"name":"amt","label":"金额","field":"amount","align":"right"}],
            rows=[{"voucher_no":"PZ001","amount":"¥1,000"}],
            on_row_click=lambda e: show_detail(e.args["row"]["voucher_no"])
        )
    """
    if not rows:
        EmptyState(message="暂无数据")
        return None

    cols = [{"name": c["name"], "label": c["label"],
             "field": c.get("field", c["name"]),
             "align": c.get("align", "left"),
             "headerClasses": c.get("headerClasses", ""),
             "classes": c.get("classes", "")}
            for c in columns]

    rk = row_key or (columns[0]["name"] if columns else "id")
    table = ui.table(columns=cols, rows=rows, row_key=rk).classes(table_classes)
    table.props("separator=cell")
    if on_row_click:
        table.on("rowClick", on_row_click)
    return table


# ─── MoneyCell ───────────────────────────────────────────────────

def MoneyCell(value, color_positive=True, prefix="", classes=""):
    """金额单元格 — 统一格式化 + 正负颜色

    用法:
        MoneyCell(1234.5)       → 绿色 ¥1,234.50
        MoneyCell(-500)         → 红色 -¥500.00
        MoneyCell(0)            → 灰色 ¥0.00
    """
    from app.components.ui_helpers import format_amount
    text = prefix + format_amount(value)
    if value is None or value == 0:
        ui.label(text).classes(f"tabular-nums {classes}").style("color:var(--c-text-secondary)")
    elif value > 0:
        color = "var(--c-success)" if color_positive else "var(--c-text-primary)"
        ui.label(text).classes(f"tabular-nums font-medium {classes}").style(f"color:{color}")
    else:
        ui.label(text).classes(f"tabular-nums font-medium {classes}").style("color:var(--c-danger)")


# ─── FormSection ────────────────────────────────────────────────

def FormSection(title, icon=None):
    """表单分组容器 — 带标题的分组区域

    用法:
        with FormSection("基本信息", icon="info"):
            ui.input("名称")
    """
    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2 px-4 border-b border-grey-1"):
            with ui.row().classes("items-center gap-2"):
                if icon:
                    ui.icon(icon).classes("text-sm").style("color:var(--c-primary)")
                ui.label(title).classes("text-sm font-semibold").style("color:var(--c-text-primary)")
        container = ui.card_section().classes("p-4")
        return container


# ─── PageHeader ─────────────────────────────────────────────────

def PageHeader(title, subtitle=None, icon=None):
    """标准页面标题区 — 大标题 + 副标题 + 图标

    用法:
        PageHeader("凭证管理", subtitle="共 128 张凭证", icon="receipt_long")
    """
    with ui.row().classes("items-center gap-3 mb-4"):
        if icon:
            ui.icon(icon).classes("text-2xl").style("color:var(--c-primary)")
        with ui.column().classes("gap-0"):
            ui.label(title).classes("text-lg font-bold").style("color:var(--c-text-primary)")
            if subtitle:
                ui.label(subtitle).classes("text-sm").style("color:var(--c-text-secondary)")


# ─── MetricRow ──────────────────────────────────────────────────

def MetricRow(label, value, trend=None, icon=None, value_color=None):
    """指标行 — 标签 + 值 + 可选趋势，用于详情页指标展示

    用法:
        MetricRow("营业收入", "¥123,456", trend="↑ 12%", icon="trending_up")
    """
    with ui.row().classes("items-center justify-between py-1.5"):
        with ui.row().classes("items-center gap-2"):
            if icon:
                ui.icon(icon).classes("text-sm").style("color:var(--c-text-muted)")
            ui.label(label).classes("text-sm").style("color:var(--c-text-secondary)")
        with ui.row().classes("items-center gap-2"):
            ui.label(str(value)).classes("text-sm font-semibold").style(
                f"color:{value_color or 'var(--c-text-primary)'}"
            )
            if trend:
                tc = "var(--c-success)" if "↑" in trend else "var(--c-danger)" if "↓" in trend else "var(--c-text-muted)"
                ui.label(trend).classes("text-xs").style(f"color:{tc}")


# ─── TimelineItem ───────────────────────────────────────────────

def TimelineItem(title, subtitle, time, icon="circle", color="var(--c-primary)", is_last=False):
    """时间线条目 — 用于审计日志、操作记录等

    用法:
        TimelineItem("创建凭证", "PZ-001 办公用品采购", "2025-01-15 14:30", icon="receipt")
    """
    with ui.row().classes("gap-3"):
        with ui.column().classes("items-center"):
            ui.icon(icon).classes("text-sm").style(f"color:{color}")
            if not is_last:
                ui.element("div").classes("w-px flex-1 mt-1").style("background:var(--c-border)")
        with ui.column().classes("gap-0.5 pb-3"):
            ui.label(title).classes("text-sm font-medium").style("color:var(--c-text-primary)")
            ui.label(subtitle).classes("text-xs").style("color:var(--c-text-secondary)")
            ui.label(time).classes("text-xs").style("color:var(--c-text-muted)")


# LoadingSpinner
def LoadingSpinner(message="加载中..."):
    """标准加载状态"""
    with ui.column().classes("items-center justify-center py-8 gap-2"):
        ui.spinner(size="md")
        ui.label(message).classes("text-sm").style("color:var(--c-text-muted)")


# ConfirmDialog
def ConfirmDialog(title, message, on_confirm, on_cancel=None):
    """标准确认对话框"""
    with ui.dialog() as dialog, ui.card():
        ui.label(title).classes("text-lg font-semibold mb-2")
        ui.label(message).classes("text-sm mb-4").style("color:var(--c-text-secondary)")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("取消", on_click=lambda: (dialog.close(), on_cancel() if on_cancel else None)).props("flat")
            ui.button("确认", color="primary", on_click=lambda: (dialog.close(), on_confirm())).props("unelevated")
    dialog.open()
    return dialog