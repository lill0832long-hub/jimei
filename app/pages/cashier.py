"""出纳管理"""
import tempfile, os
from nicegui import ui
from app.components.ui_components import SectionHeader, EmptyState
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from app.services import LedgerService, AccountService


def _do_import_bank_statement(upload_event, bank_sel, result_label):
    """导入银行对账单"""
    if not bank_sel.value:
        show_toast("请先选择银行账户", "warning")
        return
    try:
        content_bytes = upload_event.content.read()
        text = content_bytes.decode("utf-8-sig")
        rows = AccountService.parse_bank_csv(text)
        if not rows:
            show_toast("未能解析出有效数据，请检查CSV格式", "warning")
            return
        bank_id = bank_sel.value
        count = AccountService.import_bank_statement(bank_id, rows)
        result_label.text = f"✅ 成功导入 {count} 条银行流水"
        show_toast(f"✅ 成功导入 {count} 条银行流水", "success")
    except Exception as e:
        show_toast(f"❌ 导入失败: {e}", "error")


def _do_auto_match(bank_sel, result_label):
    """自动勾对"""
    if not bank_sel.value:
        show_toast("请先选择银行账户", "warning")
        return
    try:
        bank_id = bank_sel.value
        matched = AccountService.auto_match(bank_id)
        result_label.text = f"✅ 自动勾对完成，匹配 {matched} 笔"
        show_toast(f"✅ 自动勾对完成，匹配 {matched} 笔", "success")
    except Exception as e:
        show_toast(f"❌ 勾对失败: {e}", "error")


def _do_show_unmatched(bank_sel, result_label):
    """显示未达账项"""
    if not bank_sel.value:
        show_toast("请先选择银行账户", "warning")
        return
    try:
        bank_id = bank_sel.value
        rows = AccountService.get_unmatched(state.selected_ledger_id, bank_id)
        if not rows:
            result_label.text = "✅ 无未达账项，所有流水已匹配"
            show_toast("无未达账项", "success")
            return
        lines = [f"⚠️ 未达账项：{len(rows)} 笔", "─" * 40]
        for r in rows:
            dr = getattr(r, "debit", None) or 0
            cr = getattr(r, "credit", None) or 0
            amt = dr if dr else cr
            side = "收" if dr else "付"
            tx_date = getattr(r, "transaction_date", "") or r.get("transaction_date", "")
            summary = getattr(r, "summary", "") or r.get("summary", "")
            lines.append(f"  {tx_date}  [{side}] ¥{amt:,.2f}  {summary}")
        result_label.text = "\n".join(lines)
    except Exception as e:
        show_toast(f"❌ 查询失败: {e}", "error")


def _do_generate_reconciliation(bank_sel, result_table):
    """生成银行存款余额调节表"""
    if not bank_sel.value:
        show_toast("请先选择银行账户", "warning")
        return
    try:
        bank_id = bank_sel.value
        period = f"{state.selected_year}-{state.selected_month:02d}"
        data = AccountService.get_bank_reconciliation(bank_id, period)
        if data:
            result_table.rows = data
            result_table.update()
            show_toast("✅ 余额调节表已生成", "success")
        else:
            # 无数据时显示空表
            result_table.rows = [
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
            result_table.update()
            show_toast("暂无对账数据", "warning")
    except Exception as e:
        show_toast(f"❌ 生成失败: {e}", "error")


def render_cashier():
    """出纳管理 — 银行对账单导入+自动勾对+未达账项+余额调节表"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id

    # 加载银行账户
    bank_accounts = AccountService.get_bank_accounts(lid) if lid else []
    bank_opts = {ba["id"]: f"{ba['bank_name']} {ba['account_no']}" for ba in bank_accounts}

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            SectionHeader("出纳管理", icon="account_balance_wallet")

        with ui.row().classes("w-full gap-3"):
            # 左侧：银行对账单导入 + 自动勾对
            with ui.column().classes("w-1/2 gap-2"):
                # 银行账户选择
                with ui.card().classes("w-full"):
                    with ui.card_section().classes("py-2 px-3").style("border-bottom:1px solid var(--c-border)"):
                        SectionHeader("银行账户", icon="account_balance")
                    with ui.card_section().classes("py-2 px-3"):
                        bank_sel = ui.select(
                            options=bank_opts,
                            value=list(bank_opts.keys())[0] if bank_opts else None,
                            label="选择账户"
                        ).props("outlined dense").classes("w-full")
                        if not bank_accounts:
                            EmptyState(icon="account_balance", message="暂无银行账户", hint="请先在科目中添加银行存款科目")

                with ui.card().classes("w-full"):
                    with ui.card_section().classes("py-2 px-3").style("border-bottom:1px solid var(--c-border)"):
                        SectionHeader("导入银行对账单", icon="file_upload")
                    with ui.card_section().classes("py-1 px-3"):
                        ui.label("支持 CSV 格式（日期,摘要,借方,贷方,参考号）").classes("text-xs").style("color:var(--c-text-muted)")
                        import_result = ui.label("").classes("text-sm mt-1").style("color:var(--c-text-secondary)")
                        ui.upload(
                            on_upload=lambda e: _do_import_bank_statement(e, bank_sel, import_result),
                            auto_upload=True,
                            label="点击或拖拽上传 .csv",
                            max_file_size=5*1024*1024,
                        ).props("accept=.csv,.txt").classes("w-full mt-2")

                with ui.card().classes("w-full"):
                    with ui.card_section().classes("py-2 px-3").style("border-bottom:1px solid var(--c-border)"):
                        SectionHeader("自动勾对", icon="sync_alt")
                    with ui.card_section().classes("py-1 px-3"):
                        ui.label("按金额+日期匹配银行流水与凭证分录").classes("text-xs").style("color:var(--c-text-muted)")
                        match_result = ui.label("").classes("text-sm mt-1").style("color:var(--c-text-secondary)")
                        with ui.row().classes("gap-2 mt-2"):
                            ui.button("开始勾对", color="blue",
                                      on_click=lambda: _do_auto_match(bank_sel, match_result)).props("dense")
                            ui.button("未达账项", color="orange",
                                      on_click=lambda: _do_show_unmatched(bank_sel, match_result)).props("dense")

            # 右侧：银行存款余额调节表
            with ui.column().classes("w-1/2"):
                with ui.card().classes("w-full"):
                    with ui.card_section().classes("py-2 px-3").style("border-bottom:1px solid var(--c-border)"):
                        SectionHeader("银行存款余额调节表", icon="table_chart")
                    with ui.card_section().classes("py-2 px-3"):
                        ui.label(f"期间：{state.selected_year}年{state.selected_month}月").classes("text-xs mb-2").style("color:var(--c-text-muted)")
                        recon_cols = [
                            {"name":"item","label":"项目","field":"item","align":"left","headerClasses":"table-header-cell"},
                            {"name":"amount","label":"金额","field":"amount","align":"right","classes":"tabular-nums text-sm","headerClasses":"table-header-cell"},
                        ]
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
                        result_table = ui.table(columns=recon_cols, rows=recon_rows, row_key="item", pagination=False).classes("w-full text-sm")
                        ui.button("📄 生成调节表", color="green",
                                  on_click=lambda: _do_generate_reconciliation(bank_sel, result_table)).props("dense").classes("mt-2")

