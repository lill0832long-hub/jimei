"""审计日志 — 独立页面"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast
from database_v3 import get_audit_logs


def render_audit_log():
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("w-full"):
            with ui.card_section():
                ui.label("⚠️ 请先选择账套").classes("text-warning")
        return

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            ui.label("📋 审计日志").classes("text-base font-bold")

        # ── 筛选区 ──
        with ui.card_section().classes("py-2 px-4 border-b border-grey-1"):
            with ui.row().classes("gap-2 items-end"):
                module_sel = ui.select(
                    options={
                        "": "全部模块",
                        "voucher": "凭证管理",
                        "account": "科目管理",
                        "period": "期末处理",
                        "system": "系统管理",
                        "settings": "系统设置",
                        "tax": "税务管理",
                        "cash": "出纳管理",
                        "asset": "固定资产",
                        "budget": "预算管理",
                    },
                    label="模块筛选", value=""
                ).props("outlined dense").classes("w-44")
                action_in = ui.input("操作类型", placeholder="create/post/delete/...").props("outlined dense").classes("w-48")
                date_start = ui.input("开始日期", placeholder="2026-01-01").props("outlined dense").classes("w-40")
                date_end = ui.input("结束日期", placeholder="2026-12-31").props("outlined dense").classes("w-40")
                ui.button("🔍 查询", color="primary",
                          on_click=_make_query_handler(lid, module_sel, action_in, date_start, date_end)
                          ).props("dense")
                ui.button("🔄 重置",
                          on_click=_make_reset_handler(lid, module_sel, action_in, date_start, date_end)
                          ).props("dense outline")

        # ── 表格区 ──
        with ui.card_section().classes("p-0"):
            cols = [
                {"name": "id", "label": "ID", "field": "id", "align": "right",
                 "headerClasses": "table-header-cell"},
                {"name": "created_at", "label": "时间", "field": "created_at", "align": "center",
                 "headerClasses": "table-header-cell"},
                {"name": "operator_name", "label": "操作人", "field": "operator_name", "align": "center",
                 "headerClasses": "table-header-cell"},
                {"name": "user_id", "label": "用户ID", "field": "user_id", "align": "right",
                 "headerClasses": "table-header-cell"},
                {"name": "module", "label": "模块", "field": "module", "align": "center",
                 "headerClasses": "table-header-cell"},
                {"name": "action", "label": "操作", "field": "action", "align": "center",
                 "headerClasses": "table-header-cell"},
                {"name": "detail", "label": "详情", "field": "detail", "align": "left",
                 "headerClasses": "table-header-cell"},
                {"name": "target_table", "label": "目标表", "field": "target_table", "align": "center",
                 "headerClasses": "table-header-cell"},
                {"name": "target_id", "label": "目标ID", "field": "target_id", "align": "right",
                 "headerClasses": "table-header-cell"},
                {"name": "ip_address", "label": "IP地址", "field": "ip_address", "align": "center",
                 "headerClasses": "table-header-cell"},
                {"name": "remark", "label": "备注", "field": "remark", "align": "left",
                 "headerClasses": "table-header-cell"},
            ]
            rows = _do_query(lid, "", "", "", "")
            table = ui.table(columns=cols, rows=rows, row_key="id",
                             pagination={"rowsPerPage": 20}).classes("w-full text-sm")

    # 保存 table 引用供闭包使用
    _audit_tables[lid] = table


# 用字典保存各账套的表格引用（避免闭包陷阱）
_audit_tables = {}


def _do_query(ledger_id, module, action, start_date, end_date):
    """执行查询，返回行数据"""
    if not ledger_id:
        return []
    try:
        return get_audit_logs(
            ledger_id, limit=500,
            module=module or None,
            action=action.strip() or None,
            start_date=start_date.strip() or None,
            end_date=end_date.strip() or None,
        )
    except Exception as e:
        show_toast(f"查询失败: {e}", "error")
        return []


def _make_query_handler(lid, module_sel, action_in, date_start, date_end):
    """生成查询按钮的 handler（闭包捕获 element 引用）"""
    def handler():
        new_rows = _do_query(
            lid,
            module_sel.value,
            action_in.value,
            date_start.value,
            date_end.value,
        )
        table = _audit_tables.get(lid)
        if table is not None:
            table.rows = new_rows
            table.update()
        show_toast(f"查询完成，共 {len(new_rows)} 条", "success")
    return handler


def _make_reset_handler(lid, module_sel, action_in, date_start, date_end):
    """生成重置按钮的 handler"""
    def handler():
        module_sel.value = ""
        action_in.value = ""
        date_start.value = ""
        date_end.value = ""
        new_rows = _do_query(lid, "", "", "", "")
        table = _audit_tables.get(lid)
        if table is not None:
            table.rows = new_rows
            table.update()
        show_toast(f"已重置，共 {new_rows} 条", "success")
    return handler
