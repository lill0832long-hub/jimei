from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount, navigate
from database_v3 import (
    get_ledgers, get_bank_accounts, get_bank_reconciliation,
    get_bank_statements_list, get_unmatched_items,
    import_bank_statement,
)

def render_bank_reconciliation():
    """银行对账 — 银行账号选择+CSV导入+自动匹配+手动匹配+余额调节表+未达账项"""
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # 获取银行账户列表
    try:
        bank_accounts = get_bank_accounts(lid)
    except Exception:
        bank_accounts = []

    # 内部函数
    def _do_import_csv(bank_id):
        def _on_upload(e):
            import csv, io
            try:
                text = e.content.read().decode("utf-8")
                reader = csv.DictReader(io.StringIO(text))
                rows = []
                for r in reader:
                    rows.append({
                        "statement_date": r.get("日期", r.get("date", "")),
                        "transaction_date": r.get("交易日期", r.get("transaction_date", r.get("日期", r.get("date", "")))),
                        "summary": r.get("摘要", r.get("summary", r.get("备注", ""))),
                        "debit": int(float(r.get("借方", r.get("debit", r.get("收入", 0))) or 0) * 100),
                        "credit": int(float(r.get("贷方", r.get("credit", r.get("支出", 0))) or 0) * 100),
                        "reference_no": r.get("参考号", r.get("reference_no", "")),
                    })
                if rows:
                    count = import_bank_statement(bank_id, rows)
                    show_toast(f"✅ 成功导入 {count} 条银行对账单", "success")
                    refresh_main()
                else:
                    show_toast("CSV 文件为空或格式不正确", "warning")
            except Exception as ex:
                show_toast(f"导入失败: {ex}", "error")
        return _on_upload

    def _do_auto_match(bank_id):
        try:
            matched = auto_match_bank_statement(bank_id)
            show_toast(f"✅ 自动匹配完成，匹配 {matched} 笔", "success")
            refresh_main()
        except Exception as e:
            show_toast(f"❌ {e}", "error")

    def _do_match(stmt_id, bank_id):
        try:
            match_bank_statement(stmt_id, None)
            show_toast("✅ 已匹配", "success")
            refresh_main()
        except Exception as e:
            show_toast(f"❌ {e}", "error")

    def _do_unmatch(stmt_id):
        try:
            unmatch_bank_statement(stmt_id)
            show_toast("✅ 已取消匹配", "success")
            refresh_main()
        except Exception as e:
            show_toast(f"❌ {e}", "error")

    # ===== 页面主体 =====

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            with ui.row().classes("items-center justify-between"):
                ui.label("🏦 银行对账").classes("text-base font-bold")
                with ui.row().classes("gap-3 items-center"):
                    if bank_accounts:
                        ba_opts = {ba["id"]: f"{ba.get('bank_name','')} - {ba.get('account_no','')}" for ba in bank_accounts}
                        ba_select = ui.select(options=ba_opts, value=bank_accounts[0]["id"],
                                             label="银行账户").props("outlined dense").classes("w-64")
                    else:
                        ba_select = None
                        ui.label("请先添加银行账户").classes("text-sm text-grey-5")
                    ui.separator().props("vertical")
                    br_year_sel = ui.select(options=list(range(2020, 2031)), value=state.selected_year, label="年度").props("dense outlined").classes("w-28")
                    br_month_sel = ui.select(options=list(range(1, 13)), value=state.selected_month, label="月份").props("dense outlined").classes("w-24")

                    def _on_br_period():
                        state.selected_year = br_year_sel.value
                        state.selected_month = br_month_sel.value
                        refresh_main()

                    br_year_sel.on("update:value", lambda e: _on_br_period())
                    br_month_sel.on("update:value", lambda e: _on_br_period())

    if not bank_accounts:
        with ui.card().classes("w-full"):
            with ui.card_section().classes("py-12 text-center"):
                ui.icon("account_balance").style("font-size: 48px; color: var(--gray-300)")
                ui.label("暂无银行账户").classes("text-lg font-semibold text-grey-4 mt-4")
                ui.label("请先在出纳管理中添加银行账户").classes("text-sm text-grey-3 mt-2")
        return

    selected_ba_id = ba_select.value if ba_select else None
    if not selected_ba_id:
        return

    # 获取对账数据
    period_str = f"{state.selected_year}-{state.selected_month:02d}"
    try:
        recon_data = get_bank_reconciliation(selected_ba_id, period_str)
    except Exception:
        recon_data = None

    try:
        stmt_list = get_bank_statements_list(selected_ba_id)
    except Exception:
        stmt_list = []

    try:
        unmatched = get_unmatched_items(selected_ba_id)
    except Exception:
        unmatched = []

    with ui.row().classes("w-full gap-3"):
        # 左侧：导入 + 对账单列表
        with ui.column().classes("w-1/2 gap-2"):
            # CSV 导入
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3"):
                    ui.label("📥 导入银行对账单").classes("text-sm font-semibold")
                with ui.card_section().classes("py-1 px-3"):
                    ui.label("支持 CSV 格式").classes("text-xs text-grey-5")
                    ui.upload(
                        on_upload=_do_import_csv(selected_ba_id),
                        auto_upload=True,
                        label="点击或拖拽上传 CSV",
                        max_file_size=5*1024*1024,
                    ).props("accept=.csv,.txt").classes("w-full mt-2")

            # 自动勾对
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3"):
                    with ui.row().classes("items-center justify-between"):
                        ui.label("🔄 自动勾对").classes("text-sm font-semibold")
                        ui.button("开始勾对", color="blue",
                                  on_click=lambda: _do_auto_match(selected_ba_id)).props("dense")
                with ui.card_section().classes("py-1 px-3"):
                    ui.label("按金额+日期自动匹配凭证").classes("text-xs text-grey-5")

            # 对账单列表
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3"):
                    ui.label("📋 银行对账单").classes("text-sm font-semibold")
                if stmt_list:
                    stmt_cols = [
                        {"name": "date", "label": "日期", "field": "date", "align": "left",
                         "headerClasses": "text-xs font-semibold text-grey-6", "style": "width:90px"},
                        {"name": "summary", "label": "摘要", "field": "summary", "align": "left",
                         "headerClasses": "text-xs font-semibold text-grey-6"},
                        {"name": "amount", "label": "金额", "field": "amount", "align": "right",
                         "headerClasses": "text-xs font-semibold text-grey-6", "classes": "tabular-nums text-sm", "style": "width:100px"},
                        {"name": "matched", "label": "状态", "field": "is_matched", "align": "center",
                         "headerClasses": "text-xs font-semibold text-grey-6", "style": "width:72px"},
                        {"name": "action", "label": "操作", "field": "id", "align": "center",
                         "headerClasses": "text-xs font-semibold text-grey-6", "style": "width:90px"},
                    ]
                    stmt_rows = []
                    for s in stmt_list[:50]:
                        amount = (s.get("debit", 0) or 0) - (s.get("credit", 0) or 0)
                        stmt_rows.append({
                            "id": s["id"],
                            "date": s.get("transaction_date", "") or s.get("statement_date", ""),
                            "summary": s.get("summary", "")[:30],
                            "amount": amount,
                            "is_matched": "已匹配" if s.get("is_matched") else "未匹配",
                            "matched_color": "green" if s.get("is_matched") else "orange",
                        })
                    stmt_tbl = ui.table(columns=stmt_cols, rows=stmt_rows, row_key="id",
                                        pagination={"rowsPerPage": 15}).classes("w-full text-sm")
                    stmt_tbl.add_slot("body-cell-matched", r"""
                        <q-td key="matched" :props="props">
                            <q-badge :color="props.row.matched_color" :label="props.row.is_matched" size="sm" />
                        </q-td>
                    """)
                    stmt_tbl.add_slot("body-cell-action", r"""
                        <q-td key="action" :props="props">
                            <q-btn v-if="!props.row.is_matched" flat dense no-caps color="green" label="匹配"
                                   @click="$parent.$emit('stmt_match', props.row.id)" size="sm" />
                            <q-btn v-else flat dense no-caps color="orange" label="取消"
                                   @click="$parent.$emit('stmt_unmatch', props.row.id)" size="sm" />
                        </q-td>
                    """)
                    stmt_tbl.on("stmt_match", lambda e: _do_match(e.args, selected_ba_id))
                    stmt_tbl.on("stmt_unmatch", lambda e: _do_unmatch(e.args))
                else:
                    with ui.card_section().classes("py-6 text-center"):
                        ui.label("暂无对账单数据").classes("text-grey-5 text-sm")

        # 右侧：余额调节表 + 未达账项
        with ui.column().classes("w-1/2 gap-2"):
            # 余额调节表
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3"):
                    ui.label("📋 银行存款余额调节表").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    ui.label(f"期间：{state.selected_year}年{state.selected_month}月").classes("text-xs text-grey-5 mb-2")
                    HC = "text-xs font-semibold text-grey-6"
                    recon_cols = [
                        {"name": "item", "label": "项目", "field": "item", "align": "left",
                         "headerClasses": HC, "style": "min-width:180px"},
                        {"name": "amount", "label": "金额", "field": "amount", "align": "right",
                         "headerClasses": HC, "classes": "tabular-nums text-sm", "style": "width:130px"},
                    ]
                    if recon_data:
                        recon_rows = [
                            {"item": "银行对账单余额", "amount": f"¥{(recon_data.get('bank_balance',0) or 0)/100:,.2f}"},
                            {"item": "加：企业已收银行未收", "amount": f"¥{(recon_data.get('bank_recv_not_book',0) or 0)/100:,.2f}"},
                            {"item": "减：企业已付银行未付", "amount": f"¥{(recon_data.get('bank_pay_not_book',0) or 0)/100:,.2f}"},
                            {"item": "调整后银行余额", "amount": f"¥{(recon_data.get('adjusted_bank_balance',0) or 0)/100:,.2f}"},
                            {"item": "— — — — — — — —", "amount": ""},
                            {"item": "企业账面余额", "amount": f"¥{(recon_data.get('book_balance',0) or 0)/100:,.2f}"},
                            {"item": "加：银行已收企业未收", "amount": "¥0.00"},
                            {"item": "减：银行已付企业未付", "amount": "¥0.00"},
                            {"item": "调整后企业余额", "amount": f"¥{(recon_data.get('book_balance',0) or 0)/100:,.2f}"},
                        ]
                    else:
                        recon_rows = [
                            {"item": "银行对账单余额", "amount": "¥0.00"},
                            {"item": "加：企业已收银行未收", "amount": "¥0.00"},
                            {"item": "减：企业已付银行未付", "amount": "¥0.00"},
                            {"item": "调整后银行余额", "amount": "¥0.00"},
                            {"item": "— — — — — — — —", "amount": ""},
                            {"item": "企业账面余额", "amount": "¥0.00"},
                            {"item": "加：银行已收企业未收", "amount": "¥0.00"},
                            {"item": "减：银行已付企业未付", "amount": "¥0.00"},
                            {"item": "调整后企业余额", "amount": "¥0.00"},
                        ]
                    ui.table(columns=recon_cols, rows=recon_rows, row_key="item", pagination=False).classes("w-full text-sm")

            # 未达账项
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3"):
                    ui.label("⚠️ 未达账项").classes("text-sm font-semibold")
                if unmatched:
                    un_cols = [
                        {"name": "date", "label": "日期", "field": "date", "align": "left",
                         "headerClasses": "text-xs font-semibold text-grey-6", "style": "width:90px"},
                        {"name": "summary", "label": "摘要", "field": "summary", "align": "left",
                         "headerClasses": "text-xs font-semibold text-grey-6"},
                        {"name": "amount", "label": "金额", "field": "amount", "align": "right",
                         "headerClasses": "text-xs font-semibold text-grey-6", "classes": "tabular-nums text-sm", "style": "width:110px"},
                    ]
                    un_rows = []
                    for u_item in unmatched[:30]:
                        d = dict(u_item) if not isinstance(u_item, dict) else u_item
                        amount = (d.get("debit", 0) or 0) - (d.get("credit", 0) or 0)
                        un_rows.append({
                            "date": d.get("transaction_date", d.get("date", "")),
                            "summary": (d.get("summary", "") or "")[:30],
                            "amount": f"¥{abs(amount)/100:,.2f}",
                        })
                    ui.table(columns=un_cols, rows=un_rows, row_key="date",
                             pagination={"rowsPerPage": 10}).classes("w-full text-sm")
                else:
                    with ui.card_section().classes("py-4 text-center"):
                        ui.label("✅ 无未达账项").classes("text-green-6 text-sm")









