"""定时自动凭证 P2-7"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from database_v3 import (
    get_voucher_templates, save_voucher_template,
    get_scheduled_vouchers, add_scheduled_voucher, run_scheduled_voucher,
    get_accounts,
)


def render_scheduled_vouchers():
    """定时自动凭证主页面"""
    if not state.selected_ledger_id:
        from database_v3 import get_ledgers
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # ── 凭证模板区域 ──
    with ui.row().classes("w-full gap-3"):
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center justify-between"):
                    ui.label("📋 凭证模板").classes("text-sm font-semibold")
                    ui.button("➕ 新建模板", color="primary", on_click=lambda: _show_template_dialog(lid)).props("dense")

            templates = get_voucher_templates(lid)
            if templates:
                cols = [
                    {"name":"name","label":"模板名称","field":"name","align":"left","headerClasses":"table-header-cell text-uppercase"},
                    {"name":"type","label":"凭证类型","field":"voucher_type","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:80px"},
                    {"name":"desc","label":"说明","field":"description","align":"left","headerClasses":"table-header-cell text-uppercase"},
                ]
                rows = [{**t, "desc": t.get("description","") or "—"} for t in templates]
                ui.table(columns=cols, rows=rows, row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full text-sm")
            else:
                with ui.card_section():
                    ui.label("暂无凭证模板，点击「新建模板」创建").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")

        # ── 定时任务区域 ──
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center justify-between"):
                    ui.label("⏰ 定时任务").classes("text-sm font-semibold")
                    ui.button("➕ 新建任务", color="blue", on_click=lambda: _show_schedule_dialog(lid)).props("dense")

            schedules = get_scheduled_vouchers(lid)
            if schedules:
                cols = [
                    {"name":"name","label":"任务名称","field":"name","align":"left","headerClasses":"table-header-cell text-uppercase"},
                    {"name":"template","label":"关联模板","field":"template_name","align":"left","headerClasses":"table-header-cell text-uppercase"},
                    {"name":"cron","label":"Cron表达式","field":"cron_expression","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:140px"},
                    {"name":"next_run","label":"下次执行","field":"next_run_at","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:140px"},
                    {"name":"last_run","label":"上次执行","field":"last_run_at","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:140px"},
                ]
                rows = []
                for s in schedules:
                    rows.append({
                        "id": s["id"],
                        "name": s["name"],
                        "template": s.get("template_name","—") or "—",
                        "cron": s["cron_expression"],
                        "next_run": s.get("next_run_at","—") or "—",
                        "last_run": s.get("last_run_at","—") or "—",
                    })
                ui.table(columns=cols, rows=rows, row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full text-sm")
            else:
                with ui.card_section():
                    ui.label("暂无定时任务，点击「新建任务」创建").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")

    # ── 快速模板：租金摊销/工资计提 ──
    with ui.card().classes("w-full mt-1"):
        with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
            ui.label("⚡ 快速创建常用模板").classes("text-sm font-semibold")
        with ui.card_section().classes("py-2 px-3"):
            with ui.row().classes("gap-2"):
                ui.button("🏠 租金摊销", on_click=lambda: _quick_template(lid, "rent")).props("outline dense")
                ui.button("💰 工资计提", on_click=lambda: _quick_template(lid, "salary")).props("outline dense")
                ui.button("📦 折旧计提", on_click=lambda: _quick_template(lid, "depreciation")).props("outline dense")


def _show_template_dialog(ledger_id: int):
    """新建凭证模板对话框"""
    d = ui.dialog()
    accounts = get_accounts()
    acct_options = {f"{a['code']} {a['name']}": a for a in accounts}
    entry_rows = []

    with d, ui.card().classes("w-[600px]"):
        with ui.card_section():
            ui.label("📋 新建凭证模板").classes("text-lg font-bold")
        with ui.card_section().classes("gap-2"):
            name_input = ui.input("模板名称", placeholder="如：每月租金摊销").props("outlined dense").classes("w-full")
            type_select = ui.select(options=["记","收","付"], value="记", label="凭证类型").props("outlined dense").classes("w-full")
            desc_input = ui.input("说明", placeholder="选填").props("outlined dense").classes("w-full")

            ui.label("分录模板").classes("text-sm font-semibold mt-2")
            entries_container = ui.column().classes("gap-2 w-full")

            def _add_entry_row():
                with entries_container:
                    with ui.row().classes("gap-2 items-center"):
                        acct_sel = ui.select(options=list(acct_options.keys()), label="科目").props("outlined dense").classes("flex-1")
                        debit_input = ui.number(label="借方", value=0, format="%.2f").props("outlined dense").classes("w-32")
                        credit_input = ui.number(label="贷方", value=0, format="%.2f").props("outlined dense").classes("w-32")
                        summary_input = ui.input("摘要").props("outlined dense").classes("flex-1")
                        entry_rows.append({"acct": acct_sel, "debit": debit_input, "credit": credit_input, "summary": summary_input})

            ui.button("➕ 添加分录行", on_click=_add_entry_row).props("outline dense")
            _add_entry_row()
            _add_entry_row()

        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("✅ 保存", color="primary", on_click=lambda: _do_save_template(
                    d, ledger_id, name_input.value, type_select.value,
                    desc_input.value or "", entry_rows, acct_options
                ))
    d.open()


def _do_save_template(d, ledger_id, name, vtype, desc, rows, acct_options):
    if not name:
        show_toast("请输入模板名称", "warning")
        return
    entries = []
    for r in rows:
        if not r["acct"].value:
            continue
        acct = acct_options.get(r["acct"].value, {})
        dr = float(r["debit"].value or 0)
        cr = float(r["credit"].value or 0)
        if dr == 0 and cr == 0:
            continue
        entries.append({
            "account_code": acct.get("code",""),
            "account_name": acct.get("name",""),
            "debit": dr, "credit": cr,
            "summary": r["summary"].value or "",
        })
    if not entries:
        show_toast("请至少填写一条有效分录", "warning")
        return
    try:
        save_voucher_template(ledger_id, name, entries, desc, vtype)
        show_toast(f"✅ 模板「{name}」保存成功", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _show_schedule_dialog(ledger_id: int):
    """新建定时任务对话框"""
    d = ui.dialog()
    templates = get_voucher_templates(lid=ledger_id)
    tpl_options = {t["id"]: t["name"] for t in templates}

    with d, ui.card().classes("w-[480px]"):
        with ui.card_section():
            ui.label("⏰ 新建定时任务").classes("text-lg font-bold")
        with ui.card_section().classes("gap-2"):
            name_input = ui.input("任务名称", placeholder="如：每月租金摊销").props("outlined dense").classes("w-full")
            tpl_select = ui.select(options=tpl_options, label="关联凭证模板").props("outlined dense").classes("w-full")
            cron_input = ui.input("Cron表达式", value="0 0 1 * *", placeholder="分 时 日 月 周").props("outlined dense").classes("w-full")
            ui.label("常用：每月1日=0 0 1 * * | 每月15日=0 0 15 * * | 每周一=0 0 * * 1").classes("text-xs").style("color:var(--c-text-muted)")
            next_run = ui.input("下次执行时间", placeholder="YYYY-MM-DD HH:MM（留空自动计算）").props("outlined dense").classes("w-full")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("✅ 创建", color="primary", on_click=lambda: _do_add_schedule(
                    d, ledger_id, name_input.value,
                    int(tpl_select.value) if tpl_select.value else None,
                    cron_input.value or "0 0 1 * *",
                    next_run.value or None,
                ))
    d.open()


def _do_add_schedule(d, ledger_id, name, template_id, cron, next_run):
    if not name:
        show_toast("请输入任务名称", "warning")
        return
    if not template_id:
        show_toast("请选择凭证模板", "warning")
        return
    try:
        add_scheduled_voucher(ledger_id, name, cron, template_id, next_run)
        show_toast(f"✅ 定时任务「{name}」创建成功", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _quick_template(ledger_id: int, template_type: str):
    """快速创建常用模板"""
    templates = {
        "rent": {
            "name": "每月租金摊销",
            "description": "房租/办公室租金按月摊销",
            "entries": [
                {"account_code":"6602","account_name":"管理费用-租金","debit":0,"credit":0,"summary":"租金摊销"},
                {"account_code":"1123","account_name":"预付账款","debit":0,"credit":0,"summary":"租金摊销"},
            ],
        },
        "salary": {
            "name": "每月工资计提",
            "description": "月度工资计提",
            "entries": [
                {"account_code":"6601","account_name":"管理费用-工资","debit":0,"credit":0,"summary":"工资计提"},
                {"account_code":"2211","account_name":"应付职工薪酬","debit":0,"credit":0,"summary":"工资计提"},
            ],
        },
        "depreciation": {
            "name": "每月折旧计提",
            "description": "固定资产折旧计提",
            "entries": [
                {"account_code":"6602","account_name":"管理费用-折旧","debit":0,"credit":0,"summary":"折旧计提"},
                {"account_code":"1602","account_name":"累计折旧","debit":0,"credit":0,"summary":"折旧计提"},
            ],
        },
    }
    t = templates.get(template_type)
    if not t:
        return
    try:
        save_voucher_template(ledger_id, t["name"], t["entries"], t["description"])
        show_toast(f"✅ 模板「{t['name']}」创建成功", "success")
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
