"""多币种支持 P2-6"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from database_v3 import get_conn, get_ledgers


def _get_base_currency(ledger_id: int) -> str:
    conn = get_conn()
    row = conn.execute("SELECT currency FROM ledgers WHERE id=?", (ledger_id,)).fetchone()
    conn.close()
    return row["currency"] if row else "CNY"


def render_multi_currency():
    """多币种管理主页面"""
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
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
                    ui.label("💱 币种管理").classes("text-sm font-semibold")
                    ui.label(f"本位币: {base_ccy}").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.button("➕ 添加币种", color="primary", on_click=lambda: _show_add_currency_dialog()).props("dense")

            conn = get_conn()
            currencies = conn.execute("SELECT * FROM currencies ORDER BY sort_order, code").fetchall()
            conn.close()

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
                        "id": c["id"],
                        "code": c["code"],
                        "name": c["name"],
                        "symbol": c["symbol"] or c["code"],
                        "is_base": "✅" if c["is_base"] else "",
                        "active": "✅" if c["is_active"] else "❌",
                    })
                ui.table(columns=cols, rows=rows, row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full text-sm")
            else:
                with ui.card_section():
                    ui.label("暂无币种数据，系统已默认创建CNY/USD/EUR").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")

        # ── 右侧：汇率管理 ──
        with ui.card().classes("w-1/2"):
            with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                with ui.row().classes("items-center justify-between"):
                    ui.label("📈 汇率管理").classes("text-sm font-semibold")
                    ui.button("➕ 录入汇率", color="blue", on_click=lambda: _show_add_rate_dialog(lid)).props("dense")

            conn = get_conn()
            rates = conn.execute(
                "SELECT er.*, fc.code as from_code, tc.code as to_code "
                "FROM exchange_rates er "
                "JOIN currencies fc ON er.from_currency = fc.code "
                "JOIN currencies tc ON er.to_currency = tc.code "
                "ORDER BY er.date DESC, fc.code, tc.code "
                "LIMIT 50"
            ).fetchall()
            conn.close()

            if rates:
                cols = [
                    {"name":"pair","label":"币种对","field":"pair","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
                    {"name":"rate","label":"汇率","field":"rate","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:120px"},
                    {"name":"date","label":"日期","field":"date","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
                ]
                rows = [{**r, "pair": f"{r['from_code']}/{r['to_code']}", "rate": f"{r['rate']:.6f}"} for r in rates]
                ui.table(columns=cols, rows=rows, row_key="id",
                         pagination={"rowsPerPage": 10}).classes("w-full text-sm")
            else:
                with ui.card_section():
                    ui.label("暂无汇率数据").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")

    # ── 外币报表说明 ──
    with ui.card().classes("w-full mt-1"):
        with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
            ui.label("📊 外币报表").classes("text-sm font-semibold")
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
        conn = get_conn()
        conn.execute("INSERT OR IGNORE INTO currencies (code, name, symbol) VALUES (?,?,?)",
                     (code.upper(), name, symbol))
        conn.commit()
        conn.close()
        show_toast(f"✅ 币种 {code.upper()} 添加成功", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _show_add_rate_dialog(ledger_id: int):
    """录入汇率对话框"""
    d = ui.dialog()
    conn = get_conn()
    currencies = conn.execute("SELECT code FROM currencies WHERE is_active=1 ORDER BY code").fetchall()
    conn.close()
    ccy_options = [c["code"] for c in currencies]
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
        conn = get_conn()
        conn.execute(
            "INSERT INTO exchange_rates (from_currency, to_currency, rate, date) VALUES (?,?,?,date('now'))",
            (from_ccy, to_ccy, rate)
        )
        conn.commit()
        conn.close()
        show_toast(f"✅ 汇率 {from_ccy}/{to_ccy} = {rate} 已保存", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
