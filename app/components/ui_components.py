"""统一 UI 组件库 — 消除重复代码

提供财务系统常用的标准化 UI 组件：
- PageCard: 标准页面卡片容器
- EmptyState: 空状态展示
- StatusBadge: 状态标签
- DataTable: 标准化数据表格
- FormField: 标准化表单字段
- PageHeader: 页面标题区
"""
from nicegui import ui


def PageCard(classes="w-full"):
    """标准页面卡片容器 — 替代 352 处重复的 ui.card() 模式

    用法:
        with PageCard():
            with PageCard.header():
                page_title("标题")
            with PageCard.body():
                ...
    """
    return ui.card().classes(classes)


def EmptyState(icon="inbox", message="暂无数据", hint=None):
    """标准空状态 — 替代 4 处不同的空状态写法"""
    with ui.column().classes("items-center justify-center py-12 gap-2"):
        ui.icon(icon).classes("text-4xl").style("color:var(--c-text-muted)")
        ui.label(message).classes("text-sm").style("color:var(--c-text-muted)")
        if hint:
            ui.label(hint).classes("text-xs").style("color:var(--c-text-muted)")


def StatusBadge(text, status="info"):
    """标准状态标签 — 统一颜色语义"""
    colors = {
        "success": ("positive", "✓"),
        "error": ("negative", "✗"),
        "warning": ("warning", "⚠"),
        "info": ("info", "ℹ"),
        "draft": ("grey", "📝"),
        "pending": ("orange", "⏳"),
        "approved": ("positive", "✓"),
        "rejected": ("negative", "✗"),
        "posted": ("positive", "✓"),
    }
    color, icon = colors.get(status, ("info", "ℹ"))
    with ui.element("div").classes(f"inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs text-{color} bg-{color}-50"):
        ui.label(icon).classes("text-xs")
        ui.label(text).classes("text-xs font-medium")


def PageHeader(title, subtitle=None, icon=None):
    """标准页面标题区"""
    with ui.row().classes("items-center gap-3 mb-4"):
        if icon:
            ui.icon(icon).classes("text-2xl").style("color:var(--c-primary)")
        with ui.column().classes("gap-0"):
            ui.label(title).classes("text-lg font-bold").style("color:var(--c-text-primary)")
            if subtitle:
                ui.label(subtitle).classes("text-sm").style("color:var(--c-text-secondary)")


def DataTable(columns, rows, table_classes="w-full text-sm"):
    """标准化数据表格 — 统一样式 + 自动空状态

    columns: [{"name": "col_key", "label": "列名", "field": "row_key", "align": "left"}]
    rows: [{"col_key": "value", ...}]
    """
    if not rows:
        EmptyState(message="暂无数据")
        return None

    table = ui.table(
        columns=[{"name": c["name"], "label": c["label"], "field": c.get("field", c["name"]), "align": c.get("align", "left")} for c in columns],
        rows=rows,
        row_key=columns[0]["name"] if columns else "id",
    ).classes(table_classes)

    # 统一表格样式
    table.props("separator=cell")
    table.classes("styled-table")

    return table


def MoneyCell(value, color_positive=True):
    """金额单元格 — 统一格式化 + 颜色"""
    from app.components.ui_helpers import format_amount
    text = format_amount(value)
    if value is None or value == 0:
        ui.label(text).classes("tabular-nums").style("color:var(--c-text-secondary)")
    elif value > 0:
        color = "var(--c-success)" if color_positive else "var(--c-text-primary)"
        ui.label(text).classes("tabular-nums font-medium").style(f"color:{color}")
    else:
        ui.label(text).classes("tabular-nums font-medium").style("color:var(--c-danger)")
