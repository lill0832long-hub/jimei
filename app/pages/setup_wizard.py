from datetime import datetime
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount, navigate
from database_v3 import (
    create_ledger, get_default_accounts,
    import_accounts_from_template, get_ledgers,
)

def render_setup_wizard():
    """首次使用引导向导 — 全屏对话框，5步完成账套初始化"""
    wizard_state = {
        "step": 0,
        "ledger_name": "",
        "system_type": "small_business",
        "enable_year": datetime.now().year,
        "enable_month": datetime.now().month,
        "opening_balances": {},
        "imported_accounts": [],
    }

    dialog_ref = [None]
    content_ref = [None]

    def _refresh_wizard():
        if content_ref[0] is None:
            return
        content_ref[0].clear()
        _render_step_content()

    def _render_step_content():
        step = wizard_state["step"]

        if step == 0:
            with content_ref[0]:
                with ui.column().classes("items-center justify-center py-12 gap-6"):
                    with ui.element("div").style(
                        "width:80px; height:80px; border-radius:50%; background:#e3f2fd; "
                        "display:flex; align-items:center; justify-content:center;"
                    ):
                        ui.icon("account_balance").style("font-size:40px; color:#1976d2;")
                    ui.label("欢迎使用 AI 财务系统").classes("text-2xl font-bold text-grey-8")
                    ui.label("只需几步，即可完成账套初始化").classes("text-base text-grey-5")
                    with ui.column().classes("gap-2 mt-4"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", color="green").classes("text-sm")
                            ui.label("创建账套，选择会计制度").classes("text-sm text-grey-6")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", color="green").classes("text-sm")
                            ui.label("一键导入预设会计科目").classes("text-sm text-grey-6")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", color="green").classes("text-sm")
                            ui.label("录入期初余额，开始记账").classes("text-sm text-grey-6")
                    ui.button("开始设置", color="primary", on_click=lambda: _go_step(1)).props("rounded").classes("mt-6 px-8").style("height:44px; font-size:16px;")

        elif step == 1:
            with content_ref[0]:
                with ui.column().classes("gap-5 py-6 px-8"):
                    ui.label("第一步：创建账套").classes("text-xl font-bold")
                    ui.label("账套是独立核算单位的数据容器").classes("text-sm text-grey-5 -mt-3")

                    ui.label("账套名称").classes("text-sm font-semibold text-grey-7")
                    name_input = ui.input(
                        "例如：XX科技有限公司",
                        value=wizard_state.get("ledger_name", "")
                    ).props("outlined").classes("w-full")

                    ui.label("会计制度").classes("text-sm font-semibold text-grey-7 mt-2")
                    system_select = ui.select(
                        options={
                            "small_business": "小企业会计准则（2013）",
                            "enterprise": "企业会计准则（2006）",
                        },
                        value=wizard_state.get("system_type", "small_business"),
                        label="选择会计制度"
                    ).props("outlined").classes("w-full")

                    ui.label("启用期间").classes("text-sm font-semibold text-grey-7 mt-2")
                    with ui.row().classes("gap-3"):
                        year_select = ui.select(
                            options={y: str(y) for y in range(2020, 2031)},
                            value=wizard_state.get("enable_year", datetime.now().year),
                            label="年"
                        ).props("outlined").classes("w-32")
                        month_select = ui.select(
                            options={m: f"{m}月" for m in range(1, 13)},
                            value=wizard_state.get("enable_month", datetime.now().month),
                            label="月"
                        ).props("outlined").classes("w-32")

                    def _next_step_1():
                        if not name_input.value or not name_input.value.strip():
                            show_toast("请输入账套名称", "warning")
                            return
                        wizard_state["ledger_name"] = name_input.value.strip()
                        wizard_state["system_type"] = system_select.value
                        wizard_state["enable_year"] = year_select.value
                        wizard_state["enable_month"] = month_select.value
                        _go_step(2)

                    with ui.row().classes("justify-end gap-3 mt-6"):
                        ui.button("上一步", on_click=lambda: _go_step(0))
                        ui.button("下一步", color="primary", on_click=_next_step_1)

        elif step == 2:
            with content_ref[0]:
                with ui.column().classes("gap-4 py-6 px-8"):
                    ui.label("第二步：导入会计科目").classes("text-xl font-bold")
                    ui.label("系统已根据所选会计制度准备了预设科目").classes("text-sm text-grey-5 -mt-3")

                    default_accounts = get_default_accounts(wizard_state["system_type"])

                    with ui.row().classes("items-center gap-2"):
                        ui.icon("info", color="blue").classes("text-sm")
                        ui.label(f"共 {len(default_accounts)} 个预设科目").classes("text-sm text-grey-6")

                    with ui.element("div").style("max-height:300px; overflow-y:auto; border:1px solid #e0e0e0; border-radius:8px;"):
                        cols = [
                            {"name": "code", "label": "科目编码", "field": "code", "align": "left"},
                            {"name": "name", "label": "科目名称", "field": "name", "align": "left"},
                            {"name": "category", "label": "类别", "field": "category", "align": "center"},
                        ]
                        rows = [{"code": a[0], "name": a[1], "category": a[2]} for a in default_accounts]
                        ui.table(columns=cols, rows=rows, row_key="code",
                                pagination={"rowsPerPage": 20}).classes("w-full text-sm")

                    with ui.row().classes("justify-end gap-3 mt-4"):
                        ui.button("上一步", on_click=lambda: _go_step(1))
                        ui.button("一键导入", color="primary", on_click=lambda: _import_accounts(default_accounts))

        elif step == 3:
            with content_ref[0]:
                with ui.column().classes("gap-4 py-6 px-8"):
                    ui.label("第三步：录入期初余额").classes("text-xl font-bold")
                    ui.label("输入各科目在启用期间的期初余额").classes("text-sm text-grey-5 -mt-3")

                    accounts = wizard_state.get("imported_accounts") or get_default_accounts(wizard_state["system_type"])
                    top_accounts = [a for a in accounts if not a[4]]

                    balance_rows = []

                    with ui.element("div").style("max-height:320px; overflow-y:auto; border:1px solid #e0e0e0; border-radius:8px;"):
                        with ui.row().classes("gap-2 px-3 py-2 bg-grey-1 border-b border-grey-2").style("font-weight:600; font-size:13px;"):
                            ui.label("科目编码").classes("w-28")
                            ui.label("科目名称").classes("flex-1")
                            ui.label("借方期初").classes("w-32 text-right")
                            ui.label("贷方期初").classes("w-32 text-right")

                        for acc in top_accounts:
                            code, name = acc[0], acc[1]
                            existing = wizard_state["opening_balances"].get(code, {"debit": 0, "credit": 0})
                            with ui.row().classes("gap-2 px-3 py-1.5 items-center border-b border-grey-1"):
                                ui.label(code).classes("w-28 text-sm text-grey-6")
                                ui.label(name).classes("flex-1 text-sm")
                                dr_input = ui.number(
                                    "", value=existing["debit"] if existing["debit"] else None,
                                    precision=2
                                ).props("outlined dense").classes("w-32")
                                cr_input = ui.number(
                                    "", value=existing["credit"] if existing["credit"] else None,
                                    precision=2
                                ).props("outlined dense").classes("w-32")
                                balance_rows.append({
                                    "code": code, "name": name,
                                    "debit_input": dr_input, "credit_input": cr_input,
                                })

                    def _recalc_balance():
                        td = sum(r["debit_input"].value or 0 for r in balance_rows)
                        tc = sum(r["credit_input"].value or 0 for r in balance_rows)
                        return td, tc

                    td, tc = _recalc_balance()
                    diff = abs(td - tc)

                    with ui.row().classes("items-center gap-4 mt-2"):
                        ui.label(f"借方合计：¥{td:,.2f}").classes("text-sm tabular-nums")
                        ui.label(f"贷方合计：¥{tc:,.2f}").classes("text-sm tabular-nums")
                        if diff < 0.01:
                            ui.label("✅ 试算平衡").classes("text-sm font-semibold").style("color:#4caf50;")
                        else:
                            ui.label(f"❌ 差额：¥{diff:,.2f}").classes("text-sm font-semibold").style("color:#f44336;")

                    def _next_step_3():
                        for r in balance_rows:
                            dr = r["debit_input"].value or 0
                            cr = r["credit_input"].value or 0
                            if dr != 0 or cr != 0:
                                wizard_state["opening_balances"][r["code"]] = {"debit": dr, "credit": cr}

                        td = sum(v["debit"] for v in wizard_state["opening_balances"].values())
                        tc = sum(v["credit"] for v in wizard_state["opening_balances"].values())
                        if abs(td - tc) > 0.01:
                            show_toast("⚠️ 借贷不平衡，但允许继续", "warning")
                        _go_step(4)

                    with ui.row().classes("justify-end gap-3 mt-4"):
                        ui.button("上一步", on_click=lambda: _go_step(2))
                        ui.button("下一步", color="primary", on_click=_next_step_3)

        elif step == 4:
            with content_ref[0]:
                with ui.column().classes("items-center justify-center py-12 gap-6"):
                    with ui.element("div").style(
                        "width:80px; height:80px; border-radius:50%; background:#e8f5e9; "
                        "display:flex; align-items:center; justify-content:center;"
                    ):
                        ui.icon("check_circle").style("font-size:40px; color:#43a047;")
                    ui.label("账套初始化完成！").classes("text-2xl font-bold text-grey-8")
                    with ui.column().classes("gap-2 mt-2 items-center"):
                        ui.label(f"账套名称：{wizard_state['ledger_name']}").classes("text-sm text-grey-6")
                        ui.label(f"会计制度：{'小企业会计准则' if wizard_state['system_type'] == 'small_business' else '企业会计准则'}").classes("text-sm text-grey-6")
                        ui.label(f"启用期间：{wizard_state['enable_year']}年{wizard_state['enable_month']}月").classes("text-sm text-grey-6")
                        ui.label(f"导入科目：{len(wizard_state.get('imported_accounts', []))} 个").classes("text-sm text-grey-6")
                    ui.button("进入系统", color="primary", on_click=_finish_wizard).props("rounded").classes("mt-6 px-8").style("height:44px; font-size:16px;")

    def _go_step(n):
        wizard_state["step"] = n
        _refresh_wizard()

    def _import_accounts(accounts):
        try:
            ledger_id = create_ledger(
                name=wizard_state["ledger_name"],
                company=wizard_state["ledger_name"],
                currency="CNY",
                fiscal_start=f"{wizard_state['enable_year']}-01-01",
                fiscal_end=f"{wizard_state['enable_year']}-12-31",
            )
            wizard_state["ledger_id"] = ledger_id
            count = import_accounts_from_template(ledger_id, wizard_state["system_type"])
            wizard_state["imported_accounts"] = accounts
            show_toast(f"✅ 成功导入 {count} 个科目", "success")
            _go_step(3)
        except Exception as e:
            show_toast(f"❌ 导入失败：{e}", "error")

    def _finish_wizard():
        try:
            lid = wizard_state.get("ledger_id")
            if lid and wizard_state["opening_balances"]:
                for code, bal in wizard_state["opening_balances"].items():
                    if bal["debit"] != 0 or bal["credit"] != 0:
                        set_opening_balance(lid, code, wizard_state["enable_year"], wizard_state["enable_month"], bal["debit"] - bal["credit"])

            state.selected_ledger_id = wizard_state.get("ledger_id")
            state.current_page = "dashboard"
            state.show_onboarding = False
            if dialog_ref[0]:
                dialog_ref[0].close()
            show_toast("🎉 欢迎开始使用 AI 财务系统！", "success")
            refresh_main()
        except Exception as e:
            show_toast(f"❌ 初始化失败：{e}", "error")

    d = ui.dialog().props("maximized")
    dialog_ref[0] = d

    with d, ui.card().classes("w-full h-full flex flex-col"):
        with ui.row().classes("items-center justify-center gap-2 py-4 border-b border-grey-2"):
            step_labels = ["欢迎", "创建账套", "导入科目", "期初余额", "完成"]
            for i, label in enumerate(step_labels):
                is_active = i == wizard_state["step"]
                is_done = i < wizard_state["step"]
                with ui.row().classes("items-center gap-1"):
                    with ui.element("div").style(
                        f"width:28px; height:28px; border-radius:50%; "
                        f"background:{'#1976d2' if is_active else ('#4caf50' if is_done else '#e0e0e0')}; "
                        f"color:{'#fff' if (is_active or is_done) else '#999'}; "
                        f"display:flex; align-items:center; justify-content:center; "
                        f"font-size:13px; font-weight:600;"
                    ):
                        if is_done:
                            ui.label("✓").classes("text-xs")
                        else:
                            ui.label(str(i))
                    ui.label(label).classes("text-sm font-medium").style(
                        f"color:{'#1976d2' if is_active else ('#4caf50' if is_done else '#999')};"
                    )
                if i < len(step_labels) - 1:
                    ui.element("div").style(
                        f"width:32px; height:2px; background:{'#4caf50' if is_done else '#e0e0e0'};"
                    )

        content_wrapper = ui.column().classes("flex-1 overflow-auto")
        content_ref[0] = content_wrapper

    _refresh_wizard()
    d.open()


