"""增值税管理 P2-2"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from database_v3 import (
    get_tax_config, set_tax_config, get_tax_rates, add_tax_rate,
    get_tax_summary, get_tax_detail, get_accounts,
)


def render_tax():
    """增值税管理主页面"""
    if not state.selected_ledger_id:
        from database_v3 import get_ledgers
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    year, month = state.selected_year, state.selected_month

    # ── 顶部：纳税人信息 + 税率配置 ──
    with ui.row().classes("w-full gap-3"):
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center justify-between"):
                    ui.label("🧾 纳税人信息").classes("text-sm font-semibold")
                    ui.button("保存", color="primary", on_click=lambda: _save_tax_config(lid, tp_type.value, tp_rate.value)).props("dense")
            with ui.card_section().classes("py-2 px-3"):
                config = get_tax_config(lid)
                with ui.row().classes("gap-3"):
                    tp_type = ui.select(
                        options=[("general","一般纳税人"),("small","小规模纳税人")],
                        label="纳税人类型", value=config.get("taxpayer_type","general") if config else "general"
                    ).props("outlined dense").classes("w-48")
                    tp_rate = ui.number(
                        label="默认税率", value=config.get("default_tax_rate",0.13) if config else 0.13,
                        format="%.2f", step=0.01
                    ).props("outlined dense").classes("w-32")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center justify-between"):
                    ui.label("📊 税率设置").classes("text-sm font-semibold")
                    ui.button("➕ 添加", color="blue", on_click=lambda: _show_add_rate_dialog(lid)).props("dense")
            with ui.card_section().classes("py-2 px-3"):
                rates = get_tax_rates(lid)
                if rates:
                    with ui.row().classes("gap-2 flex-wrap"):
                        for r in rates:
                            ui.chip(
                                f"{r['name']} ({r['rate']*100:.0f}%)",
                                color="blue" if r.get("is_default") else "grey",
                                outline=True
                            ).props("dense")
                else:
                    ui.label("暂无税率，点击「添加」设置常用税率").classes("text-xs").style("color:var(--c-text-muted)")

    # ── 中部：增值税汇总 + 申报表 ──
    summary = get_tax_summary(lid, year, month)

    with ui.row().classes("w-full gap-3 mt-1"):
        # 进项/销项/应纳税额 卡片
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("进项税额").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"¥{summary['input_tax']:,.2f}").classes("text-xl font-bold").style("color:var(--c-primary)")
                    ui.label(f"{year}年{month}月").classes("text-xs").style("color:var(--c-text-muted)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("销项税额").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"¥{summary['output_tax']:,.2f}").classes("text-xl font-bold").style("color:var(--c-danger)")
                    ui.label(f"{year}年{month}月").classes("text-xs").style("color:var(--c-text-muted)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    payable = summary['tax_payable']
                    ui.label("应纳税额").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"¥{payable:,.2f}").classes("text-xl font-bold").style(
                        f"color:{'var(--c-danger)' if payable > 0 else 'var(--c-success)'}"
                    )
                    ui.label("销项 - 进项").classes("text-xs").style("color:var(--c-text-muted)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("纳税人类型").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label("一般纳税人" if summary['taxpayer_type'] == 'general' else "小规模纳税人").classes("text-xl font-bold").style("color:var(--c-text-primary)")
                    ui.label(f"默认税率 {summary['default_rate']*100:.0f}%").classes("text-xs").style("color:var(--c-text-muted)")

    # ── 下部：进项/销项明细 Tab ──
    with ui.card().classes("w-full mt-1"):
        with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
            ui.label("📋 税额明细").classes("text-sm font-semibold")

        with ui.tabs().classes("w-full") as tabs:
            ui.tab("进项税额明细")
            ui.tab("销项税额明细")

        with ui.tab_panels(tabs, value="进项税额明细"):
            with ui.tab_panel("进项税额明细"):
                _render_tax_detail(lid, year, month, "input")
            with ui.tab_panel("销项税额明细"):
                _render_tax_detail(lid, year, month, "output")


def _render_tax_detail(ledger_id: int, year: int, month: int, tax_type: str):
    """渲染税额明细表格"""
    details = get_tax_detail(ledger_id, year, month, tax_type)
    if not details:
        with ui.card_section():
            ui.label("暂无数据").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")
        return

    cols = [
        {"name":"voucher_no","label":"凭证号","field":"voucher_no","align":"left","headerClasses":"table-header-cell text-uppercase","style":"width:120px"},
        {"name":"date","label":"日期","field":"date","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:90px"},
        {"name":"account","label":"科目","field":"account_name","align":"left","headerClasses":"table-header-cell text-uppercase"},
        {"name":"description","label":"摘要","field":"description","align":"left","headerClasses":"table-header-cell text-uppercase"},
        {"name":"tax_rate","label":"税率","field":"tax_rate","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:70px"},
        {"name":"tax_amount","label":"税额","field":"tax_amount","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:110px"},
    ]
    rows = [{**d,
             "tax_rate": f"{d['tax_rate']*100:.0f}%" if d.get("tax_rate") else "—",
             "tax_amount": f"¥{d['tax_amount']:,.2f}" if d.get("tax_amount") else "—",
             "account": f"{d['account_code']} {d['account_name']}"
    } for d in details]

    ui.table(columns=cols, rows=rows, row_key="voucher_no",
             pagination={"rowsPerPage": 10}).classes("w-full text-sm")

    # 合计行
    total = sum(d.get("tax_amount", 0) for d in details)
    with ui.card_section().classes("py-1 px-3"):
        ui.label(f"合计：¥{total:,.2f}").classes("text-sm font-semibold").style("color:var(--c-primary)")


def _save_tax_config(ledger_id, taxpayer_type, default_rate):
    try:
        set_tax_config(ledger_id, taxpayer_type, float(default_rate or 0.13))
        show_toast("✅ 增值税配置已保存", "success")
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _show_add_rate_dialog(ledger_id):
    """添加税率对话框"""
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label("➕ 添加税率").classes("text-lg font-bold")
        with ui.card_section().classes("gap-2"):
            rate_name = ui.input("税率名称", placeholder="如：13%税率").props("outlined dense").classes("w-full")
            rate_val = ui.number(label="税率", value=0.13, format="%.4f", step=0.01).props("outlined dense").classes("w-full")
            rate_desc = ui.input("说明", placeholder="选填").props("outlined dense").classes("w-full")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("✅ 添加", color="primary", on_click=lambda: _do_add_rate(d, ledger_id, rate_name.value, rate_val.value, rate_desc.value or ""))
    d.open()


def _do_add_rate(d, ledger_id, name, rate, desc):
    if not name:
        show_toast("请输入税率名称", "warning")
        return
    try:
        add_tax_rate(ledger_id, float(rate or 0), name, desc)
        show_toast(f"✅ 税率 {name} 添加成功", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
