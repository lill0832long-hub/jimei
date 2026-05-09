from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount, navigate
from database_v3 import (
    get_ledgers, get_voucher_templates,
    create_voucher_template, update_voucher_template,
    delete_voucher_template, get_accounts, get_vouchers,
)

def render_voucher_template():
    """凭证模板管理 — 列表+新增/编辑/删除/启用禁用/从模板生成凭证"""
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    CATEGORY_LABELS = {
        "daily": "日常报销",
        "salary": "工资发放",
        "depreciation": "折旧计提",
        "revenue": "收入确认",
        "general": "其他",
    }

    # ===== 内部函数定义 =====

    def _show_template_dialog(existing_tpl, ledger_id, category_labels):
        """新增/编辑模板对话框"""
        d = ui.dialog()
        is_edit = existing_tpl is not None
        tpl_data = existing_tpl if existing_tpl else {}

        with d, ui.card().classes("w-[750px] max-w-[95vw]"):
            with ui.card_section():
                ui.label("✏️ " + ("编辑凭证模板" if is_edit else "新增凭证模板")).classes("text-xl font-bold")

            with ui.card_section().classes("gap-2"):
                name_input = ui.input("模板名称", value=tpl_data.get("name", ""),
                                     placeholder="如：收款-客户回款").props("outlined dense").classes("w-full")
                desc_input = ui.input("描述", value=tpl_data.get("description", ""),
                                     placeholder="模板用途说明").props("outlined dense").classes("w-full")
                cat_opts = {k: v for k, v in category_labels.items()}
                cat_select = ui.select(options=cat_opts, value=tpl_data.get("category", "general"),
                                       label="模板分类").props("outlined dense").classes("w-48")
                is_active_val = True if not is_edit else bool(tpl_data.get("is_active", 1))
                is_active_check = ui.checkbox("启用模板", value=is_active_val)

            # 模板分录编辑
            with ui.card_section():
                ui.label("模板分录").classes("text-xs font-semibold text-grey-6 uppercase tracking-wide mb-2")
                entries_col = ui.column().classes("w-full gap-1")
                acct_opts = {a["code"]: f"{a['code']} {a['name']}" for a in get_accounts()}
                entry_rows = []

                def add_entry_row(entry=None):
                    with entries_col:
                        with ui.row().classes("items-center gap-1 w-full"):
                            acct_sel = ui.select(options=acct_opts,
                                                 value=(entry.get("account_code", "1001") if entry else "1001"),
                                                 label="科目").props("outlined dense").classes("w-52")
                            summ_in = ui.input("摘要",
                                               value=(entry.get("summary", "") if entry else "")).props("outlined dense").classes("flex-grow")
                            dr_in = ui.number("借方",
                                              value=(float(entry.get("debit", 0)) if entry else 0),
                                              precision=2).props("outlined dense").classes("w-24")
                            cr_in = ui.number("贷方",
                                              value=(float(entry.get("credit", 0)) if entry else 0),
                                              precision=2).props("outlined dense").classes("w-24")
                            dir_sel = ui.select(
                                options={"debit": "借方", "credit": "贷方"},
                                value=(entry.get("direction", "debit") if entry else "debit"),
                                label="方向"
                            ).props("outlined dense").classes("w-20")
                            entry_rows.append({
                                "acct": acct_sel, "summary": summ_in,
                                "debit": dr_in, "credit": cr_in, "direction": dir_sel,
                            })
                            def _remove_row(r):
                                if len(entry_rows) > 1:
                                    entry_rows.remove(r)
                            ui.button(icon="close", color="grey",
                                      on_click=lambda r=entry_rows[-1] if entry_rows else None: _remove_row(r) if r else None).props("flat dense")

                # 加载已有分录或默认2行
                existing_entries = tpl_data.get("entries", [])
                if existing_entries:
                    for entry in existing_entries:
                        add_entry_row(entry)
                else:
                    for _ in range(2):
                        add_entry_row()

                ui.button("➕ 添加行", on_click=lambda: add_entry_row(), color="blue").props("dense flat")

            with ui.card_section():
                with ui.row().classes("justify-end gap-2"):
                    ui.button("取消", on_click=d.close)
                    ui.button("💾 保存", color="primary", on_click=lambda: _do_save_template(
                        d, ledger_id, name_input, desc_input, cat_select, is_active_check,
                        entry_rows, existing_tpl.get("id") if existing_tpl else None
                    ))
        d.open()

    def _do_save_template(d, ledger_id, name_in, desc_in, cat_sel, active_chk, entry_rows, tpl_id):
        name = name_in.value
        if not name:
            show_toast("请输入模板名称", "warning")
            return
        entries = []
        for r in entry_rows:
            code = r["acct"].value
            if not code:
                continue
            name_acct = next((a["name"] for a in get_accounts() if a["code"] == code), code)
            direction = r["direction"].value
            debit_val = r["debit"].value or 0
            credit_val = r["credit"].value or 0
            if direction == "debit" and debit_val == 0 and credit_val > 0:
                debit_val = credit_val
                credit_val = 0
            elif direction == "credit" and credit_val == 0 and debit_val > 0:
                credit_val = debit_val
                debit_val = 0
            entries.append({
                "account_code": code,
                "account_name": name_acct,
                "direction": direction,
                "debit": debit_val,
                "credit": credit_val,
                "summary": r["summary"].value or "",
            })
        if not entries:
            show_toast("请至少添加一条分录", "warning")
            return
        try:
            if tpl_id:
                update_voucher_template(
                    tpl_id, ledger_id,
                    name=name, description=desc_in.value,
                    entries=entries, category=cat_sel.value,
                    is_active=active_chk.value
                )
                show_toast(f"✅ 模板「{name}」已更新", "success")
            else:
                create_voucher_template(
                    ledger_id, name, desc_in.value,
                    entries, category=cat_sel.value
                )
                show_toast(f"✅ 模板「{name}」已创建", "success")
            d.close()
            refresh_main()
        except Exception as e:
            show_toast(f"❌ {e}", "error")

    def _do_edit(tpl_id):
        tpl = next((t for t in get_voucher_templates(lid, include_inactive=True) if t["id"] == tpl_id), None)
        if not tpl:
            show_toast("模板不存在", "error")
            return
        _show_template_dialog(tpl, lid, CATEGORY_LABELS)

    def _do_toggle(tpl_id):
        try:
            tpl = next((t for t in get_voucher_templates(lid, include_inactive=True) if t["id"] == tpl_id), None)
            if not tpl:
                show_toast("模板不存在", "error")
                return
            new_active = not tpl.get("is_active", 1)
            update_voucher_template(tpl_id, lid, is_active=new_active)
            show_toast(f"模板已{'启用' if new_active else '禁用'}", "success")
            refresh_main()
        except Exception as e:
            show_toast(f"❌ {e}", "error")

    def _do_delete(tpl_id):
        d = ui.dialog()
        with d, ui.card().classes("w-80"):
            with ui.card_section():
                ui.label("⚠️ 确认删除").classes("text-lg font-bold text-orange-7")
                ui.label("删除后无法恢复，确定要删除此模板吗？").classes("text-sm text-grey-6 mt-2")
            with ui.card_section():
                with ui.row().classes("justify-end gap-2"):
                    ui.button("取消", on_click=d.close)
                    ui.button("确认删除", color="red", on_click=lambda: _confirm_delete(d, tpl_id))
        d.open()

    def _confirm_delete(d, tpl_id):
        try:
            delete_voucher_template(tpl_id, lid)
            show_toast("✅ 模板已删除", "success")
            d.close()
            refresh_main()
        except Exception as e:
            show_toast(f"❌ {e}", "error")

    def _do_generate(tpl_id):
        tpl = next((t for t in get_voucher_templates(lid) if t["id"] == tpl_id), None)
        if not tpl:
            show_toast("模板不存在", "error")
            return
        state.current_page = "journal"
        state._pending_template_id = tpl_id
        refresh_main()
        show_toast(f"已选择模板「{tpl['name']}」，请在凭证录入页面点击「应用模板」", "info")

    # ===== 页面主体 =====

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            with ui.row().classes("items-center justify-between"):
                ui.label("📄 凭证模板管理").classes("text-base font-bold")
                ui.button("➕ 新增模板", color="primary",
                          on_click=lambda: _show_template_dialog(None, lid, CATEGORY_LABELS)).props("dense")

        # 加载模板列表
        try:
            templates = get_voucher_templates(lid, include_inactive=True)
        except Exception:
            templates = []

        if not templates:
            with ui.card_section().classes("py-12 text-center"):
                ui.icon("description").style("font-size: 48px; color: var(--gray-300)")
                ui.label("暂无凭证模板").classes("text-lg font-semibold text-grey-4 mt-4")
                ui.label("点击「新增模板」创建第一个模板").classes("text-sm text-grey-3 mt-2")
        else:
            cols = [
                {"name": "name", "label": "模板名称", "field": "name", "align": "left",
                 "headerClasses": "text-xs font-semibold uppercase text-grey-6"},
                {"name": "category", "label": "分类", "field": "category", "align": "center",
                 "headerClasses": "text-xs font-semibold uppercase text-grey-6"},
                {"name": "description", "label": "描述", "field": "description", "align": "left",
                 "headerClasses": "text-xs font-semibold uppercase text-grey-6"},
                {"name": "status", "label": "状态", "field": "status_label", "align": "center",
                 "headerClasses": "text-xs font-semibold uppercase text-grey-6"},
                {"name": "entries_count", "label": "分录数", "field": "entries_count", "align": "center",
                 "headerClasses": "text-xs font-semibold uppercase text-grey-6"},
                {"name": "actions", "label": "操作", "field": "id", "align": "center",
                 "headerClasses": "text-xs font-semibold uppercase text-grey-6", "style": "width:220px"},
            ]
            rows = []
            for t in templates:
                rows.append({
                    "id": t["id"],
                    "name": t["name"],
                    "category": CATEGORY_LABELS.get(t.get("category", "general"), "其他"),
                    "description": t.get("description", "") or "",
                    "status_label": "启用" if t.get("is_active", 1) else "禁用",
                    "status_color": "green" if t.get("is_active", 1) else "grey",
                    "entries_count": len(t.get("entries", [])),
                    "is_system": t.get("is_system", 0),
                    "_raw": t,
                })

            tbl = ui.table(columns=cols, rows=rows, row_key="id",
                           pagination={"rowsPerPage": 15}).classes("w-full text-sm")

            tbl.add_slot("body-cell-status", r"""
                <q-td key="status" :props="props">
                    <q-badge :color="props.row.status_color" :label="props.row.status_label" size="sm" />
                </q-td>
            """)

            tbl.add_slot("body-cell-actions", r"""
                <q-td key="actions" :props="props">
                    <div class="row items-center gap-1 justify-center">
                        <q-btn flat dense no-caps color="primary" icon="edit" label="编辑"
                               @click="$parent.$emit('edit', props.row.id)" size="sm" />
                        <q-btn flat dense no-caps :color="props.row.status_color === 'green' ? 'orange' : 'green'"
                               :icon="props.row.status_color === 'green' ? 'pause' : 'play_arrow'"
                               :label="props.row.status_color === 'green' ? '禁用' : '启用'"
                               @click="$parent.$emit('toggle', props.row.id)" size="sm" />
                        <q-btn flat dense no-caps color="blue" icon="receipt_long" label="生成凭证"
                               @click="$parent.$emit('generate', props.row.id)" size="sm" />
                        <q-btn flat dense no-caps color="red" icon="delete" label="删除"
                               @click="$parent.$emit('delete', props.row.id)"
                               :disable="props.row.is_system === 1" size="sm" />
                    </div>
                </q-td>
            """)

            tbl.on("edit", lambda e: _do_edit(e.args))
            tbl.on("toggle", lambda e: _do_toggle(e.args))
            tbl.on("delete", lambda e: _do_delete(e.args))
            tbl.on("generate", lambda e: _do_generate(e.args))



