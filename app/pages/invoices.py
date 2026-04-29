"""发票管理 P2-3"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from database_v3 import (
    get_invoices, add_invoice, link_invoice_voucher, get_invoice_vouchers,
    get_invoice_summary, ocr_recognize_invoice,
)


def render_invoices():
    """发票管理主页面"""
    if not state.selected_ledger_id:
        from database_v3 import get_ledgers
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    summary = get_invoice_summary(lid)

    # ── 顶部：发票汇总卡片 ──
    with ui.row().classes("w-full gap-3"):
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("进项发票").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"{summary['input_count']} 张").classes("text-xl font-bold").style("color:var(--c-primary)")
                    ui.label(f"¥{summary['input_total']:,.2f}").classes("text-xs").style("color:var(--c-text-muted)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("销项发票").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"{summary['output_count']} 张").classes("text-xl font-bold").style("color:var(--c-success)")
                    ui.label(f"¥{summary['output_total']:,.2f}").classes("text-xs").style("color:var(--c-text-muted)")

        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4"):
                with ui.column().classes("items-center gap-1"):
                    ui.label("未核验").classes("text-xs").style("color:var(--c-text-muted)")
                    ui.label(f"{summary['unverified_count']} 张").classes("text-xl font-bold").style(
                        f"color:{'var(--c-warning)' if summary['unverified_count'] > 0 else 'var(--c-text-primary)'}"
                    )
                    ui.label("待处理").classes("text-xs").style("color:var(--c-text-muted)")

    # ── 发票台账 + 操作 ──
    with ui.card().classes("w-full mt-1"):
        with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
            with ui.row().classes("items-center justify-between"):
                ui.label("📄 发票台账").classes("text-sm font-semibold")
                with ui.row().classes("gap-2"):
                    ui.button("📷 OCR识别", color="blue", on_click=lambda: _show_ocr_dialog(lid)).props("dense outline")
                    ui.button("➕ 手动录入", color="primary", on_click=lambda: _show_add_invoice_dialog(lid)).props("dense")

        # 筛选 tabs
        with ui.tabs().classes("w-full") as tabs:
            ui.tab("全部")
            ui.tab("进项发票")
            ui.tab("销项发票")
            ui.tab("未核验")

        with ui.tab_panels(tabs, value="全部"):
            for tab_label, filter_type in [("全部", None), ("进项发票", "input"), ("销项发票", "output"), ("未核验", "unverified")]:
                with ui.tab_panel(tab_label):
                    _render_invoice_table(lid, invoice_type=filter_type if filter_type in ("input","output") else None,
                                          status=filter_type if filter_type == "unverified" else None)


def _render_invoice_table(ledger_id: int, invoice_type: str = None, status: str = None):
    """渲染发票表格"""
    invoices = get_invoices(ledger_id, invoice_type=invoice_type, status=status)
    if not invoices:
        with ui.card_section():
            ui.label("暂无发票数据").classes("text-sm py-4 text-center").style("color:var(--c-text-muted)")
        return

    cols = [
        {"name":"invoice_no","label":"发票号码","field":"invoice_no","align":"left","headerClasses":"table-header-cell text-uppercase","style":"width:140px"},
        {"name":"date","label":"开票日期","field":"invoice_date","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
        {"name":"type","label":"类型","field":"invoice_type","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:80px"},
        {"name":"seller","label":"销售方","field":"seller_name","align":"left","headerClasses":"table-header-cell text-uppercase"},
        {"name":"amount","label":"金额","field":"total_amount","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:110px"},
        {"name":"tax","label":"税额","field":"tax_amount","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:100px"},
        {"name":"total","label":"价税合计","field":"total_with_tax","align":"right","headerClasses":"table-header-cell text-uppercase","style":"width:120px"},
        {"name":"status","label":"状态","field":"status","align":"center","headerClasses":"table-header-cell text-uppercase","style":"width:80px"},
    ]
    rows = []
    for inv in invoices:
        rows.append({
            "id": inv["id"],
            "invoice_no": inv.get("invoice_no","—"),
            "date": inv.get("invoice_date","—"),
            "type": "进项" if inv.get("invoice_type") == "input" else "销项",
            "seller": inv.get("seller_name","—"),
            "amount": f"¥{inv.get('total_amount',0):,.2f}",
            "tax": f"¥{inv.get('tax_amount',0):,.2f}",
            "total": f"¥{inv.get('total_with_tax',0):,.2f}",
            "status": {"unverified":"待核验","verified":"已核验","cancelled":"已作废"}.get(inv.get("status",""),"—"),
        })
    ui.table(columns=cols, rows=rows, row_key="id",
             pagination={"rowsPerPage": 10}).classes("w-full text-sm")


def _show_add_invoice_dialog(ledger_id: int):
    """手动录入发票对话框"""
    d = ui.dialog()
    with d, ui.card().classes("w-[520px]"):
        with ui.card_section():
            ui.label("➕ 录入发票").classes("text-lg font-bold")
        with ui.card_section().classes("gap-2"):
            with ui.row().classes("gap-2"):
                inv_type = ui.select(options=[("input","进项发票"),("output","销项发票")], value="input", label="发票类型").props("outlined dense").classes("w-40")
                inv_no = ui.input("发票号码", placeholder="请输入发票号码").props("outlined dense").classes("flex-1")
            inv_date = ui.input("开票日期", placeholder="YYYY-MM-DD").props("outlined dense").classes("w-full")
            seller = ui.input("销售方名称").props("outlined dense").classes("w-full")
            seller_tax = ui.input("销售方税号").props("outlined dense").classes("w-full")
            with ui.row().classes("gap-2"):
                amount = ui.number(label="金额", value=0, format="%.2f").props("outlined dense").classes("flex-1")
                tax_amount = ui.number(label="税额", value=0, format="%.2f").props("outlined dense").classes("flex-1")
                total = ui.number(label="价税合计", value=0, format="%.2f").props("outlined dense").classes("flex-1")
            remark = ui.input("备注", placeholder="选填").props("outlined dense").classes("w-full")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("✅ 保存", color="primary", on_click=lambda: _do_add_invoice(
                    d, ledger_id, inv_type.value, inv_no.value,
                    inv_date.value, seller.value, seller_tax.value,
                    float(amount.value or 0), float(tax_amount.value or 0), float(total.value or 0),
                    remark.value or ""
                ))
    d.open()


def _do_add_invoice(d, ledger_id, inv_type, inv_no, inv_date, seller, seller_tax, amount, tax, total, remark):
    if not inv_no:
        show_toast("请输入发票号码", "warning")
        return
    try:
        add_invoice(ledger_id, inv_type, inv_no,
                    invoice_date=inv_date or None, seller_name=seller or "",
                    seller_tax_no=seller_tax or "", total_amount=amount,
                    tax_amount=tax, total_with_tax=total, remark=remark)
        show_toast(f"✅ 发票 {inv_no} 录入成功", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _show_ocr_dialog(ledger_id: int):
    """OCR识别发票对话框（预留接口）"""
    d = ui.dialog()
    with d, ui.card().classes("w-[480px]"):
        with ui.card_section():
            ui.label("📷 OCR识别发票").classes("text-lg font-bold")
        with ui.card_section().classes("gap-3"):
            ui.label("上传发票图片或PDF，系统自动识别发票信息").classes("text-sm").style("color:var(--c-text-secondary)")
            ui.upload(label="选择文件", on_upload=lambda e: _do_ocr_upload(d, ledger_id, e)).props("accept=.jpg,.jpeg,.png,.pdf").classes("w-full")
            ui.separator()
            ui.label("💡 支持的发票类型").classes("text-sm font-semibold")
            with ui.column().classes("gap-1"):
                ui.label("• 增值税专用发票").classes("text-xs").style("color:var(--c-text-muted)")
                ui.label("• 增值税普通发票").classes("text-xs").style("color:var(--c-text-muted)")
                ui.label("• 电子发票").classes("text-xs").style("color:var(--c-text-muted)")
                ui.label("• 机动车销售统一发票").classes("text-xs").style("color:var(--c-text-muted)")
        with ui.card_section():
            with ui.row().classes("justify-end"):
                ui.button("关闭", on_click=d.close)
    d.open()


def _do_ocr_upload(d, ledger_id, upload_event):
    """处理OCR上传（预留）"""
    result = ocr_recognize_invoice(upload_event.name)
    if result.get("status") == "mock":
        show_toast(f"📷 {result['message']}", "info")
    else:
        show_toast("✅ OCR识别成功", "success")
    d.close()
    refresh_main()
