"""多币种支持 P2-6"""
from nicegui import ui
from app.components.ui_components import SectionHeader, EmptyState
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from app.services import LedgerService, CurrencyService


def _get_base_currency(ledger_id: int) -> str:
    ledger = LedgerService.get_by_id(ledger_id)
    return ledger.get("currency", "CNY") if ledger else "CNY"


def render_multi_currency():
    """多币种管理主页面"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    base_ccy = _get_base_currency(lid)

    with ui.row().classes("w-full gap-3"):
        # ── 左侧：币种管理 ──
        with ui.card().classes("w-1/2"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center justify-between"):
                    SectionHeader("币种管理", icon="currency_exchange", action=lambda: _show_add_currency_dialog())
                    ui.label(f"本位币: {base_ccy}").classes("text-xs").style("color:var(--c-text-muted)")

            currencies = CurrencyService.get_all(active_only=False)

            if currencies:
                cols = [
                    {"name":"code","label":"币种代码","field":"code","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:80px"},
                    {"name":"name","label":"名称","field":"name","align":"left","headerClasses":"table-header-cell text-uppercase"},
                    {"name":"symbol","label":"符号","field":"symbol","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:60px"},
                    {"name":"is_base","label":"本位币","field":"is_base","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:70px"},
                    {"name":"active","label":"启用","field":"is_active","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:60px"},
                ]
                rows = []
                for c in currencies:
                    rows.append({
                        "id": c.get("id", ""),
                        "code": c.get("code", ""),
                        "name": c.get("name", ""),
                        "symbol": c.get("symbol") or c.get("code", ""),
                        "is_base": "✅" if c.get("is_base") else "",
                        "active": "✅" if c.get("is_active") else "❌",
                    })
                ui.table(columns=cols, rows=rows, row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full text-sm")
            else:
                with ui.card_section():
                    ui.label("暂无币种数据，系统已默认创建CNY/USD/EUR").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")

        # ── 右侧：汇率管理 ──
        with ui.card().classes("w-1/2"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                SectionHeader("汇率管理", icon="show_chart", action=lambda: _show_add_rate_dialog(lid), action_color="blue")

            rate_results = CurrencyService.get_all_rates_with_currency(limit=50)

            if rate_results:
                cols = [
                    {"name":"pair","label":"币种对","field":"pair","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
                    {"name":"rate","label":"汇率","field":"rate","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:120px"},
                    {"name":"date","label":"日期","field":"date","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
                ]
                rows = []
                for er, _fc in rate_results:
                    er_dict = er if isinstance(er, dict) else {"id": getattr(er, "id", ""), "from_currency": getattr(er, "from_currency", ""), "to_currency": getattr(er, "to_currency", ""), "rate": getattr(er, "rate", 0), "date": getattr(er, "date", "")}
                    rows.append({
                        "id": er_dict.get("id", ""),
                        "pair": f"{er_dict.get('from_currency', '')}/{er_dict.get('to_currency', '')}",
                        "rate": f"{er_dict.get('rate', 0):.6f}",
                        "date": er_dict.get("date", ""),
                    })
                ui.table(columns=cols, rows=rows, row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full text-sm")
            else:
                with ui.card_section():
                    ui.label("暂无汇率数据").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")

    # ── 外币报表说明 ──
    with ui.card().classes("w-full mt-1"):
        with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
            SectionHeader("外币报表", icon="assessment")
        with ui.card_section().classes("py-2 px-3"):
            with ui.row().classes("gap-4"):
                ui.label(f"• 本位币：{base_ccy}（所有报表默认以本位币展示）").classes("text-xs").style("color:var(--c-text-secondary)")
                ui.label("• 凭证录入时可选择外币，系统自动按汇率折算本位币").classes("text-xs").style("color:var(--c-text-secondary)")
                ui.label("• 期末可生成汇兑损益凭证").classes("text-xs").style("color:var(--c-text-secondary)")


def _show_add_currency_dialog():
    """添加币种对话框"""
    d = ui.dialog()
    with d, ui.card().classes("w-[400px]"):
        with ui.card_section():
            ui.label("💱 添加币种").classes("text-lg font-bold")
        with ui.card_section().classes("gap-2"):
            code = ui.input("币种代码", placeholder="如：GBP").props("outlined dense").classes("w-full")
            name = ui.input("币种名称", placeholder="如：英镑").props("outlined dense").classes("w-full")
            symbol = ui.input("货币符号", placeholder="如：£").props("outlined dense").classes("w-full")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("✅ 添加", color="primary", on_click=lambda: _do_add_currency(d, code.value, name.value, symbol.value))
    d.open()


def _do_add_currency(d, code, name, symbol):
    if not code or not name:
        show_toast("请填写币种代码和名称", "warning")
        return
    try:
        CurrencyService.create_currency(code, name, symbol)
        show_toast(f"✅ 币种 {code.upper()} 添加成功", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _show_add_rate_dialog(ledger_id: int):
    """录入汇率对话框"""
    d = ui.dialog()
    ccy_options = CurrencyService.get_active_codes()
    base = _get_base_currency(ledger_id)

    with d, ui.card().classes("w-[400px]"):
        with ui.card_section():
            ui.label("📈 录入汇率").classes("text-lg font-bold")
        with ui.card_section().classes("gap-2"):
            from_ccy = ui.select(options=ccy_options, value=ccy_options[0] if ccy_options else None, label="源币种").props("outlined dense").classes("w-full")
            to_ccy = ui.select(options=ccy_options, value=base, label="目标币种").props("outlined dense").classes("w-full")
            rate = ui.number(label="汇率", value=1.0, format="%.6f", step=0.0001).props("outlined dense").classes("w-full")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("✅ 保存", color="primary", on_click=lambda: _do_add_rate(d, from_ccy.value, to_ccy.value, float(rate.value or 0)))
    d.open()


def _do_add_rate(d, from_ccy, to_ccy, rate):
    if not from_ccy or not to_ccy or rate <= 0:
        show_toast("请填写完整汇率信息", "warning")
        return
    try:
        CurrencyService.add_rate(from_ccy, to_ccy, rate)
        show_toast(f"✅ 汇率 {from_ccy}/{to_ccy} = {rate} 已保存", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
