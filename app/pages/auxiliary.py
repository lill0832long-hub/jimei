"""辅助核算"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from database_v3 import (
    get_ledgers, create_auxiliary, get_auxiliaries, update_auxiliary, delete_auxiliary,
    query_db,
)

# 辅助核算类型
_AUX_TYPES = ["客户", "供应商", "产品线", "地区", "部门", "项目"]


def _do_add_dimension(aux_type):
    """新增维度项目"""
    with ui.dialog() as dlg, ui.card().classes("w-[400px]"):
        ui.label(f"新增{aux_type}").classes("text-base font-bold mb-3")
        code_input = ui.input("编码", placeholder="如：C001").props("outlined dense").classes("w-full")
        name_input = ui.input("名称", placeholder="如：客户A").props("outlined dense").classes("w-full mt-2")
        with ui.row().classes("mt-4 gap-2 justify-end"):
            ui.button("取消", on_click=dlg.close).props("flat")
            def _save():
                code = (code_input.value or "").strip()
                name = (name_input.value or "").strip()
                if not code or not name:
                    show_toast("请填写编码和名称", "warning")
                    return
                lid = state.selected_ledger_id
                if not lid:
                    show_toast("请先选择账套", "warning")
                    return
                try:
                    create_auxiliary(lid, aux_type, code, name)
                    show_toast(f"✅ {aux_type}「{name}」已添加", "success")
                    dlg.close()
                    refresh_main()
                except Exception as e:
                    show_toast(f"❌ 添加失败: {e}", "error")
            ui.button("保存", color="green", on_click=_save)
    dlg.open()


def _do_edit_dimension(aux):
    """编辑维度项目"""
    with ui.dialog() as dlg, ui.card().classes("w-[400px]"):
        ui.label(f"编辑 {aux['name']}").classes("text-base font-bold mb-3")
        code_input = ui.input("编码", value=aux.get("code", "")).props("outlined dense").classes("w-full")
        name_input = ui.input("名称", value=aux.get("name", "")).props("outlined dense").classes("w-full mt-2")
        with ui.row().classes("mt-4 gap-2 justify-end"):
            ui.button("取消", on_click=dlg.close).props("flat")
            def _save():
                code = (code_input.value or "").strip()
                name = (name_input.value or "").strip()
                if not code or not name:
                    show_toast("请填写编码和名称", "warning")
                    return
                try:
                    update_auxiliary(aux["id"], code=code, name=name)
                    show_toast(f"✅ 已更新为「{name}」", "success")
                    dlg.close()
                    refresh_main()
                except Exception as e:
                    show_toast(f"❌ 更新失败: {e}", "error")
            ui.button("保存", color="blue", on_click=_save)
    dlg.open()


def _do_delete_dimension(aux):
    """删除维度项目"""
    with ui.dialog() as dlg, ui.card().classes("w-[360px]"):
        ui.label("⚠️ 确认删除").classes("text-base font-bold mb-2")
        ui.label(f'确定删除「{aux.get("name", "")}」吗？此操作不可撤销。').classes("text-sm").style("color:var(--c-text-secondary)")
        with ui.row().classes("mt-4 gap-2 justify-end"):
            ui.button("取消", on_click=dlg.close).props("flat")
            def _confirm():
                try:
                    delete_auxiliary(aux["id"])
                    show_toast(f"✅ 已删除「{aux.get('name', '')}」", "success")
                    dlg.close()
                    refresh_main()
                except Exception as e:
                    show_toast(f"❌ 删除失败: {e}", "error")
            ui.button("删除", color="red", on_click=_confirm)
    dlg.open()


def _do_query_multi_dim(cust_sel, prod_sel, region_sel, result_table):
    """多维度组合查询"""
    lid = state.selected_ledger_id
    if not lid:
        show_toast("请先选择账套", "warning")
        return
    conditions = []
    params = [lid]
    if cust_sel.value and cust_sel.value != "全部":
        conditions.append("AND aux_customer.name = ?")
        params.append(cust_sel.value)
    if prod_sel.value and prod_sel.value != "全部":
        conditions.append("AND aux_product.name = ?")
        params.append(prod_sel.value)
    if region_sel.value and region_sel.value != "全部":
        conditions.append("AND aux_region.name = ?")
        params.append(region_sel.value)
    where = " ".join(conditions) if conditions else ""
    sql = f"""
        SELECT v.voucher_no, v.date, v.summary,
               a.code as acct_code, a.name as acct_name,
               e.debit, e.credit,
               aux_c.name as customer, aux_p.name as product, aux_r.name as region
        FROM vouchers v
        JOIN entries e ON e.voucher_id = v.id
        JOIN accounts a ON a.id = e.account_id
        LEFT JOIN entry_auxiliary ea_c ON ea_c.entry_id = e.id AND ea_c.aux_type = '客户'
        LEFT JOIN auxiliaries aux_c ON aux_c.id = ea_c.aux_id
        LEFT JOIN entry_auxiliary ea_p ON ea_p.entry_id = e.id AND ea_p.aux_type = '产品线'
        LEFT JOIN auxiliaries aux_p ON aux_p.id = ea_p.aux_id
        LEFT JOIN entry_auxiliary ea_r ON ea_r.entry_id = e.id AND ea_r.aux_type = '地区'
        LEFT JOIN auxiliaries aux_r ON aux_r.id = ea_r.aux_id
        WHERE v.ledger_id = ? {where}
        ORDER BY v.date DESC, v.id DESC
        LIMIT 100
    """
    try:
        rows = query_db(sql, tuple(params))
        result_table.rows = rows
        result_table.update()
        show_toast(f"查询完成，共 {len(rows)} 条", "success")
    except Exception as e:
        show_toast(f"查询失败: {e}", "error")


def render_auxiliary():
    """辅助核算 — 自定义维度+多维度组合查询+维度余额表"""
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id

    # 加载辅助核算数据
    aux_data = {}
    if lid:
        for atype in _AUX_TYPES:
            aux_data[atype] = get_auxiliaries(lid, atype)

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            ui.label("📎 辅助核算").classes("text-base font-bold")

        with ui.row().classes("w-full gap-3"):
            # 左侧：维度管理
            with ui.column().classes("w-1/3 gap-2"):
                with ui.card().classes("w-full"):
                    with ui.card_section().classes("py-2 px-3").style("border-bottom:1px solid var(--c-border)"):
                        with ui.row().classes("items-center justify-between"):
                            ui.label("维度管理").classes("text-sm font-semibold")
                    for atype in _AUX_TYPES:
                        with ui.card_section().classes("py-1.5 px-3").style("border-bottom:1px solid var(--c-border)"):
                            with ui.row().classes("items-center justify-between"):
                                with ui.row().classes("items-center gap-1"):
                                    ui.label("📌").classes("text-sm")
                                    ui.label(atype).classes("text-sm font-semibold").style("color:var(--c-primary)")
                                    ui.label(f"({len(aux_data.get(atype, []))})").classes("text-xs").style("color:var(--c-text-muted)")
                                with ui.row().classes("gap-1"):
                                    ui.button(icon="add", color="green",
                                              on_click=lambda t=atype: _do_add_dimension(t)).props("dense flat").classes("text-xs")
                        for aux in aux_data.get(atype, []):
                            with ui.card_section().classes("py-1 px-3 pl-6").style("border-bottom:1px solid var(--c-border)"):
                                with ui.row().classes("items-center justify-between"):
                                    with ui.row().classes("items-center gap-1"):
                                        ui.label(aux.get("code", "")).classes("text-xs font-mono").style("color:var(--c-text-muted)")
                                        ui.label(aux.get("name", "")).classes("text-sm")
                                    with ui.row().classes("gap-0.5"):
                                        ui.button(icon="edit", color="blue",
                                                  on_click=lambda a=aux: _do_edit_dimension(a)).props("dense flat").classes("text-xs")
                                        ui.button(icon="delete", color="red",
                                                  on_click=lambda a=aux: _do_delete_dimension(a)).props("dense flat").classes("text-xs")

            # 右侧：多维度查询 + 维度余额表
            with ui.column().classes("w-2/3 gap-2"):
                with ui.card().classes("w-full"):
                    with ui.card_section().classes("py-2 px-3").style("border-bottom:1px solid var(--c-border)"):
                        ui.label("🔍 多维度组合查询").classes("text-sm font-semibold").style("color:var(--c-success)")
                    with ui.card_section().classes("py-2 px-3"):
                        with ui.row().classes("gap-2"):
                            cust_opts = ["全部"] + [a["name"] for a in aux_data.get("客户", [])]
                            prod_opts = ["全部"] + [a["name"] for a in aux_data.get("产品线", [])]
                            region_opts = ["全部"] + [a["name"] for a in aux_data.get("地区", [])]
                            cust_sel = ui.select(options=cust_opts, value="全部", label="客户").props("dense outlined").classes("w-32")
                            prod_sel = ui.select(options=prod_opts, value="全部", label="产品线").props("dense outlined").classes("w-32")
                            region_sel = ui.select(options=region_opts, value="全部", label="地区").props("dense outlined").classes("w-32")
                            ui.button("查询", color="green",
                                      on_click=lambda: _do_query_multi_dim(cust_sel, prod_sel, region_sel, result_table)).props("dense")

                    with ui.card_section().classes("py-2 px-3"):
                        result_cols = [
                            {"name":"voucher_no","label":"凭证号","field":"voucher_no","align":"left"},
                            {"name":"date","label":"日期","field":"date","align":"center"},
                            {"name":"summary","label":"摘要","field":"summary","align":"left"},
                            {"name":"acct_code","label":"科目","field":"acct_code","align":"center"},
                            {"name":"debit","label":"借方","field":"debit","align":"right","classes":"tabular-nums"},
                            {"name":"credit","label":"贷方","field":"credit","align":"right","classes":"tabular-nums"},
                        ]
                        result_table = ui.table(columns=result_cols, rows=[], row_key="voucher_no",
                                                pagination={"rowsPerPage": 10}).classes("w-full text-sm")

                with ui.card().classes("w-full"):
                    with ui.card_section().classes("py-2 px-3").style("border-bottom:1px solid var(--c-border)"):
                        ui.label("📊 维度余额表").classes("text-sm font-semibold").style("color:var(--c-warning)")
                    with ui.card_section().classes("py-2 px-3"):
                        dim_cols = [
                            {"name":"dimension","label":"维度","field":"dimension","align":"left","headerClasses":"table-header-cell"},
                            {"name":"debit","label":"借方","field":"debit","align":"right","classes":"tabular-nums","headerClasses":"table-header-cell"},
                            {"name":"credit","label":"贷方","field":"credit","align":"right","classes":"tabular-nums","headerClasses":"table-header-cell"},
                            {"name":"balance","label":"余额","field":"balance","align":"right","classes":"tabular-nums","headerClasses":"table-header-cell"},
                        ]
                        dim_rows = []
                        if lid:
                            for atype in _AUX_TYPES:
                                for aux in aux_data.get(atype, []):
                                    # 查询每个维度的余额
                                    try:
                                        bal = query_db("""
                                            SELECT COALESCE(SUM(e.debit),0) as total_dr,
                                                   COALESCE(SUM(e.credit),0) as total_cr
                                            FROM entry_auxiliary ea
                                            JOIN entries e ON e.id = ea.entry_id
                                            WHERE ea.aux_id = ? AND ea.aux_type = ?
                                        """, (aux["id"], atype))
                                        if bal:
                                            dr = bal[0]["total_dr"]
                                            cr = bal[0]["total_cr"]
                                            dim_rows.append({
                                                "dimension": f"{atype}/{aux['name']}",
                                                "debit": f"¥{dr:,.2f}",
                                                "credit": f"¥{cr:,.2f}",
                                                "balance": f"¥{dr-cr:,.2f}",
                                            })
                                    except Exception:
                                        pass
                        ui.table(columns=dim_cols, rows=dim_rows, row_key="dimension", pagination=False).classes("w-full text-sm")
