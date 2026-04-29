"""系统设置"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from database_v3 import (
    get_ledgers, create_ledger, set_opening_balance, add_account,
    get_users, create_user, update_user, delete_user, change_password, get_accounts,
    get_audit_logs,
)

def render_settings():
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return
    lid = state.selected_ledger_id
    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            ui.label("⚙️ 系统设置").classes("text-base font-bold")

        with ui.card_section().classes("py-3 px-4"):
            with ui.row().classes("gap-3"):
                # 账套管理
                with ui.card().classes("flex-1"):
                    with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                        ui.label("📁 账套管理").classes("text-sm font-semibold")
                    with ui.card_section().classes("py-2 px-3"):
                        ledgers = get_ledgers()
                        if ledgers:
                            for lg in ledgers:
                                with ui.row().classes("items-center justify-between py-1 border-b border-grey-1"):
                                    with ui.column().classes("gap-0"):
                                        ui.label(lg.get("name","")).classes("text-sm font-medium")
                                        ui.label(lg.get("company","")).classes("text-xs").style("color:var(--c-text-muted)")
                                    ui.label(f"ID: {lg['id']}").classes("text-xs font-mono").style("color:var(--c-text-muted)")
                        else:
                            ui.label("暂无账套").classes("text-sm").style("color:var(--c-text-muted)")
                        ui.button("➕ 新建账套", color="primary", on_click=show_new_ledger_dialog).props("dense").classes("w-full mt-2")

                # 期初余额
                with ui.card().classes("flex-1"):
                    with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                        ui.label("💰 期初余额").classes("text-sm font-semibold")
                    with ui.card_section().classes("py-2 px-3"):
                        ui.label("设置科目期初余额").classes("text-xs").style("color:var(--c-text-muted)")
                        with ui.column().classes("gap-1 mt-1"):
                            ob_code = ui.input("科目代码", placeholder="1002").props("outlined dense").classes("w-full")
                            ob_year = ui.number("年份", value=state.selected_year, precision=0).props("outlined dense").classes("w-full")
                            ob_month = ui.number("月份", value=state.selected_month, precision=0).props("outlined dense").classes("w-full")
                            ob_balance = ui.number("期初余额", value=0, precision=2).props("outlined dense").classes("w-full")
                            ui.button("💾 保存", color="green",
                                      on_click=lambda: do_set_opening_balance(lid, ob_code.value, int(ob_year.value or 2026), int(ob_month.value or 1), ob_balance.value or 0)).props("dense").classes("w-full")

                # 科目管理
                with ui.card().classes("flex-1"):
                    with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                        ui.label("📚 科目管理").classes("text-sm font-semibold")
                    with ui.card_section().classes("py-2 px-3"):
                        ui.label("添加新科目").classes("text-xs").style("color:var(--c-text-muted)")
                        with ui.column().classes("gap-1 mt-1"):
                            ac_code = ui.input("科目代码", placeholder="100201").props("outlined dense").classes("w-full")
                            ac_name = ui.input("科目名称", placeholder="中国银行").props("outlined dense").classes("w-full")
                            ac_cat = ui.select(options=["资产","负债","权益","成本","损益"], label="类别", value="资产").props("outlined dense").classes("w-full")
                            ui.button("➕ 添加科目", color="blue",
                                      on_click=lambda: do_add_account(ac_code.value, ac_name.value, ac_cat.value)).props("dense").classes("w-full")

        # ── P1-11 新增：公司信息 + 凭证字 + 操作日志 ──
        with ui.card_section().classes("py-3 px-4 border-t border-grey-2"):
            ui.label("🏢 公司信息").classes("text-sm font-semibold mb-2")
            with ui.row().classes("gap-2"):
                ui.input("公司名称", value="示例公司").props("dense outlined").classes("flex-1")
                ui.input("税号", value="91110000000000000X").props("dense outlined").classes("flex-1")
            with ui.row().classes("gap-2 mt-1"):
                ui.input("地址", value="").props("dense outlined").classes("flex-1")
                ui.input("电话", value="").props("dense outlined").classes("flex-1")
            ui.button("💾 保存公司信息", color="blue", on_click=lambda: show_toast("公司信息已保存", "success")).props("dense").classes("mt-1")

        with ui.card_section().classes("py-3 px-4 border-t border-grey-2"):
            ui.label("📝 凭证字设置").classes("text-sm font-semibold mb-2")
            cols_vt = [
                {"name":"vt","label":"凭证字","field":"vt","align":"center","headerClasses":"table-header-cell"},
                {"name":"prefix","label":"前缀","field":"prefix","align":"center","headerClasses":"table-header-cell"},
                {"name":"no","label":"当前编号","field":"no","align":"right","classes":"tabular-nums","headerClasses":"table-header-cell"},
            ]
            rows_vt = [
                {"vt": "收款凭证", "prefix": "收", "no": "0001"},
                {"vt": "付款凭证", "prefix": "付", "no": "0001"},
                {"vt": "转账凭证", "prefix": "转", "no": "0001"},
            ]
            ui.table(columns=cols_vt, rows=rows_vt, row_key="vt", pagination=False).classes("w-full text-sm")
        with ui.card_section().classes("py-3 px-4 border-t border-grey-2"):
            ui.label("📋 最近操作日志").classes("text-sm font-semibold mb-2")
            with ui.row().classes("gap-2 mb-2"):
                audit_mod_filter = ui.select(
                    options={"":"全部","voucher":"凭证","account":"科目","period":"期末","system":"系统","settings":"设置","tax":"税务","cash":"出纳","asset":"固定资产","budget":"预算"},
                    label="模块", value=""
                ).props("outlined dense").classes("w-32")
                ui.button("🔍 筛选", color="primary",
                          on_click=lambda: _refresh_settings_audit(lid, audit_mod_filter.value)
                          ).props("dense")
                ui.button("🔄 刷新", on_click=lambda: _refresh_settings_audit(lid, "")).props("dense")
            logs = get_audit_logs(lid, limit=15)
            if not logs:
                ui.label("暂无操作记录").classes("text-sm").style("color:var(--c-text-muted)")
            else:
                log_cols = [
                    {"name": "created_at", "label": "时间", "field": "created_at", "align": "center",
                     "headerClasses": "table-header-cell"},
                    {"name": "operator_name", "label": "操作人", "field": "operator_name", "align": "center",
                     "headerClasses": "table-header-cell"},
                    {"name": "module", "label": "模块", "field": "module", "align": "center",
                     "headerClasses": "table-header-cell"},
                    {"name": "action", "label": "操作", "field": "action", "align": "center",
                     "headerClasses": "table-header-cell"},
                    {"name": "detail", "label": "详情", "field": "detail", "align": "left",
                     "headerClasses": "table-header-cell"},
                ]
                ui.table(columns=log_cols, rows=logs, row_key="id",
                         pagination=False).classes("w-full text-sm")

        # ── P2-1: 用户与权限管理 ──
        with ui.card_section().classes("py-3 px-4 border-t border-grey-2"):
            ui.label("👥 用户与权限").classes("text-sm font-semibold mb-2")
            role_labels = {"admin":"管理员","accountant":"制单人","reviewer":"审核人","poster":"过账人","viewer":"查看者"}
            users = get_users()
            user_cols = [
                {"name":"username","label":"用户名","field":"username","align":"left","headerClasses":"table-header-cell text-uppercase"},
                {"name":"role","label":"角色","field":"role","align":"center","headerClasses":"table-header-cell text-uppercase"},
                {"name":"status","label":"状态","field":"is_active","align":"center","headerClasses":"table-header-cell text-uppercase"},
                {"name":"created","label":"创建时间","field":"created_at","align":"center","headerClasses":"table-header-cell text-uppercase"},
            ]
            user_rows = [{**u, "role": role_labels.get(u["role"], u["role"]),
                          "status": "启用" if u["is_active"] else "禁用"} for u in users]
            ui.table(columns=user_cols, rows=user_rows, row_key="id", pagination=False).classes("w-full text-sm")
            # 操作按钮
            with ui.row().classes("gap-1 mt-2"):
                ui.button("➕ 添加用户", color="primary", on_click=lambda: show_add_user_dialog(lid)).props("dense")
                ui.button("🔄 刷新", on_click=refresh_main).props("dense outline")


def show_add_user_dialog(ledger_id):
    """添加用户对话框"""
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label("➕ 添加用户").classes("text-lg font-bold")
        with ui.card_section().classes("gap-2"):
            username = ui.input("用户名").props("outlined dense").classes("w-full")
            password = ui.input("密码", password=True).props("outlined dense").classes("w-full")
            role_sel = ui.select(
                options=[("admin","管理员"),("accountant","制单人"),("reviewer","审核人"),("poster","过账人"),("viewer","查看者")],
                label="角色", value="accountant"
            ).props("outlined dense").classes("w-full")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("✅ 创建", color="primary", on_click=lambda: _do_add_user(d, username.value, password.value, role_sel.value, ledger_id))
    d.open()


def _do_add_user(d, username, password, role, ledger_id):
    if not username or not password:
        show_toast("请填写用户名和密码", "warning")
        return
    try:
        create_user(username, password, role=role, ledger_id=ledger_id)
        show_toast(f"✅ 用户 {username} 创建成功", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def show_new_ledger_dialog():
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label("📁 新建账套").classes("text-lg font-bold")
        with ui.card_section():
            name_input = ui.input("账套名称", placeholder="例：2026年度账套").props("outlined").classes("w-full")
            company_input = ui.input("公司名称", placeholder="例：XX科技有限公司").props("outlined").classes("w-full")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("创建", color="primary", on_click=lambda: do_create_ledger(d, name_input.value, company_input.value))
    d.open()


def do_create_ledger(d, name, company):
    if not name:
        show_toast("请输入账套名称", "warning")
        return
    lid = create_ledger(name, company or "默认公司")
    state.selected_ledger_id = lid
    show_toast(f"✅ 账套 {name} 创建成功", "success")
    d.close()
    refresh_main()


def do_set_opening_balance(lid, code, year, month, balance):
    set_opening_balance(lid, code, year, month, balance or 0)
    acct_name = next((a["name"] for a in get_accounts() if a["code"] == code), code)
    show_toast(f"✅ {acct_name} 期初余额已设置：¥{(balance or 0):,.2f}", "success")
    refresh_main()


def do_add_account(code, name, category):
    if not code or not name:
        show_toast("请填写科目代码和名称", "warning")
        return
    try:
        add_account(code, name, category)
        show_toast(f"✅ 科目 {code} {name} 添加成功", "success")
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
