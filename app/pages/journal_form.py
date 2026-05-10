"""凭证表单 — 新增/编辑凭证对话框"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from database_v3 import get_conn, get_ledgers
from app.services import AccountService, VoucherService


def _generate_voucher_no(lid, voucher_type="记"):
    """自动生成凭证编号：类型+年月+序号，如 记-202604-001"""
    from datetime import datetime as _dt
    prefix = f"{voucher_type}-{_dt.now().strftime('%Y%m')}-"
    try:
        existing = VoucherService.get_all(lid, _dt.now().year, _dt.now().month, limit=200)
        max_seq = 0
        for v in existing:
            vn = v.get("voucher_no", "")
            if vn.startswith(prefix):
                try:
                    seq = int(vn.split("-")[-1])
                    if seq > max_seq:
                        max_seq = seq
                except (ValueError, IndexError):
                    pass
        return f"{prefix}{max_seq + 1:03d}"
    except Exception:
        return f"{prefix}001"


def show_new_voucher_dialog():
    """新增凭证对话框"""
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
        else:
            show_toast("❌ 请先创建账套", "error")
            return
    _render_voucher_form_dialog()


def show_edit_voucher_dialog(detail):
    """编辑凭证对话框"""
    _render_voucher_form_dialog(detail=detail)


def _render_voucher_form_dialog(detail=None):
    """凭证表单对话框（新增/编辑通用）"""
    d = ui.dialog()
    row_refs = []
    is_edit = detail is not None

    with d, ui.card().classes("w-[750px] max-w-[95vw]"):
        with ui.card_section():
            label = f"✏️ 编辑凭证 {detail['voucher_no']}" if is_edit else "📝 新增记账凭证"
            ui.label(label).classes("text-xl font-bold")

        # 凭证模板快捷选择
        if not is_edit:
            try:
                _templates = VoucherService.get_templates(state.selected_ledger_id) if state.selected_ledger_id else []
            except Exception:
                _templates = []
            if _templates:
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("description").style("color:var(--c-primary)")
                        ui.label("凭证模板").classes("text-xs font-semibold uppercase tracking-wide").style("color:var(--c-text-secondary)")
                        template_opts = {t["id"]: t["name"] for t in _templates}
                        template_select = ui.select(
                            options=template_opts, value=None, label="选择模板（可选）"
                        ).props("outlined dense clearable").classes("w-52")

                        def _on_template_apply():
                            tpl_id = template_select.value
                            if not tpl_id:
                                show_toast("请先选择一个模板", "warning")
                                return
                            tpl = next((t for t in _templates if t["id"] == tpl_id), None)
                            if not tpl:
                                show_toast("模板不存在", "error")
                                return
                            entries_col.clear()
                            desc_input.value = tpl.get("description", "")
                            for entry in tpl.get("entries", []):
                                _add_row(
                                    entries_col, row_refs,
                                    acct_code=entry.get("account_code", ""),
                                    summary=entry.get("summary", ""),
                                    debit=entry.get("debit", 0) if entry.get("direction") == "debit" else 0,
                                    credit=entry.get("credit", 0) if entry.get("direction") == "credit" else 0,
                                )
                            show_toast(f"已应用模板：{tpl['name']}", "success")

                        ui.button("应用", on_click=_on_template_apply).props("dense color=primary").classes("px-3")

        with ui.card_section():
            default_date = detail["date"] if is_edit else f"{state.selected_year}-{state.selected_month:02d}-01"
            default_desc = detail["description"] if is_edit else ""
            date_input = ui.input("日期", value=default_date).props("type=date outlined dense").classes("w-40")
            desc_input = ui.input("凭证摘要", value=default_desc).props("outlined dense").classes("flex-grow")
            if not is_edit:
                save_draft = ui.checkbox("保存为草稿", value=False)

        _acct_data = AccountService.get_all()
        acct_opts = {a["code"]: f"{a['code']} {a['name']}" for a in _acct_data}

        with ui.card_section():
            ui.label("分录明细").classes("text-xs font-semibold uppercase tracking-wide mb-2").style("color:var(--c-text-secondary)")
            entries_col = ui.column().classes("w-full gap-1")

            # 获取币种选项
            _ccy_conn = get_conn()
            _ccys = _ccy_conn.execute("SELECT code FROM currencies WHERE is_active=1 ORDER BY code").fetchall()
            _ccy_conn.close()
            _ccy_opts = {c["code"]: c["code"] for c in _ccys} if _ccys else {"CNY": "CNY"}
            _default_ccy = state.selected_ledger_currency if hasattr(state, 'selected_ledger_currency') else "CNY"

            # 编辑模式：填充已有分录
            if is_edit and detail:
                for entry in detail.get("entries", []):
                    _add_row(
                        entries_col, row_refs, acct_opts, _acct_data,
                        acct_code=entry.get("account_code", ""),
                        summary=entry.get("summary", ""),
                        debit=float(entry.get("debit", 0) or 0),
                        credit=float(entry.get("credit", 0) or 0),
                    )
            else:
                for _ in range(4):
                    _add_row(entries_col, row_refs, acct_opts, _acct_data)

            ui.button("➕ 添加行", on_click=lambda: _add_row(entries_col, row_refs, acct_opts, _acct_data), color="blue").props("dense flat")

        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                if is_edit:
                    ui.button("💾 保存", color="primary",
                              on_click=lambda: _do_edit(d, detail["voucher_no"], date_input.value, desc_input.value, row_refs))
                else:
                    ui.button("💾 保存", color="primary",
                              on_click=lambda: _do_save(d, lid=state.selected_ledger_id,
                                                         date_input=date_input, desc_input=desc_input,
                                                         save_draft=save_draft, row_refs=row_refs))
    d.open()


def _add_row(entries_col, row_refs, acct_opts, acct_list=None, acct_code="1002", summary="", debit=0, credit=0, foreign_ccy="", foreign_amount=0, exchange_rate=1):
    """创建一行分录，带智能联想功能"""
    from app.components.state import state
    from app.services import AccountService
    from app.components.ui_helpers import show_toast

    if acct_list is None:
        acct_list = AccountService.get_all()
    _acct_map = {a["code"]: a for a in acct_list}

    suggest_label = ui.label("").classes("text-xs text-blue-600 mt-0.5 mb-0 w-full").style("min-height:16px;transition:all 0.2s")
    avg_label = ui.label("").classes("text-xs text-green-600 mt-0 mb-0 w-full").style("min-height:16px")
    acct_suggest_items = ui.column().classes("w-full gap-0 mt-0 mb-1").style("display:none")
    history_items = ui.column().classes("w-full gap-0 mt-0 mb-1").style("display:none")

    with entries_col:
        with ui.column().classes("w-full gap-0 mb-1") as row_col:
            with ui.column().classes("w-full gap-0 px-1 py-0.5 rounded bg-blue-50/50 border border-blue-100 mb-1").style("display:none") as suggest_box:
                with ui.row().classes("items-center gap-1 w-full"):
                    auto_debit = ui.radio({True: "借方", False: "贷方"}, value=True, label="方向").props("dense inline color=primary")
                    suggest_info = ui.label("").classes("text-xs flex-grow")
                    ui.button("填充", color="primary", on_click=None).props("dense size=sm").classes("px-2")

            with ui.row().classes("items-center gap-2 w-full") as row_el:
                sel = ui.select(options=acct_opts, value=acct_code, label="科目").props("outlined dense").classes("w-56")
                summ = ui.input("摘要", value=summary).props("outlined dense").classes("flex-grow")
                dr = ui.number("借方", value=debit, precision=2).props("outlined dense").classes("w-28")
                cr = ui.number("贷方", value=credit, precision=2).props("outlined dense").classes("w-28")

                _ccy_conn = get_conn()
                _ccys = _ccy_conn.execute("SELECT code FROM currencies WHERE is_active=1 ORDER BY code").fetchall()
                _ccy_conn.close()
                _ccy_opts = {c["code"]: c["code"] for c in _ccys} if _ccys else {"CNY": "CNY"}
                _default_ccy = state.selected_ledger_currency if hasattr(state, 'selected_ledger_currency') else "CNY"

                ccy_sel = ui.select(options=_ccy_opts, value=foreign_ccy or _default_ccy, label="币种").props("outlined dense").classes("w-20")
                famt = ui.number("外币金额", value=foreign_amount, precision=2).props("outlined dense").classes("w-28")
                xr = ui.number("汇率", value=exchange_rate if exchange_rate != 1 else 1, precision=6).props("outlined dense").classes("w-24")

                r = {"acct": sel, "summary": summ, "debit": dr, "credit": cr,
                     "foreign_ccy": ccy_sel, "foreign_amount": famt, "exchange_rate": xr,
                     "suggest_box": suggest_box, "suggest_info": suggest_info,
                     "auto_debit": auto_debit, "row_col": row_col}
                row_refs.append(r)

                ui.button(icon="close", color="grey", on_click=lambda _r=r, _el=row_col: (_el.delete(), row_refs.remove(_r) if _r in row_refs else None)).props("flat dense")

            # 摘要输入 → 历史凭证联想
            def _on_summary_change(row_ref=r):
                kw = row_ref["summary"].value or ""
                if len(kw) < 2:
                    row_ref["suggest_box"].style("display:none")
                    return
                lid = state.selected_ledger_id
                if not lid:
                    return
                results = VoucherService.search_history(lid, keyword=kw, limit=5)
                if not results:
                    row_ref["suggest_box"].style("display:none")
                    return
                row_ref["suggest_box"].style("display:flex")
                first = results[0]
                acct_display = f"{first['account_code']} {first['account_name']}" if first.get('account_code') else ""
                avg_amt = f"¥{first['avg_amount']:,.2f}" if first.get('avg_amount') else ""
                row_ref["suggest_info"].text = f"💡 {acct_display}  {avg_amt}"

                def _fill_from_history(_r=row_ref, _res=first):
                    if _res.get("account_code"):
                        _r["acct"].value = _res["account_code"]
                    amt = _res.get("avg_amount", 0)
                    if _r["auto_debit"].value:
                        _r["debit"].value = round(amt, 2)
                        _r["credit"].value = 0
                    else:
                        _r["credit"].value = round(amt, 2)
                        _r["debit"].value = 0
                    show_toast("已填充", "success")
                row_ref["suggest_box"].children[-1].on_click = _fill_from_history

            summ.on_value_change(_on_summary_change)

            # 科目选择 → 金额推荐 + 借贷方向判断
            def _on_account_change(row_ref=r, _acct_map=_acct_map):
                code = row_ref["acct"].value
                if not code:
                    return
                lid = state.selected_ledger_id
                if not lid:
                    return
                avg = AccountService.get_avg_amount(lid, code)
                if avg and avg > 0:
                    row_ref["suggest_box"].style("display:flex")
                    row_ref["suggest_info"].text = f"💰 近3月平均: ¥{avg:,.2f}"
                    acct_info = _acct_map.get(code, {})
                    if acct_info:
                        cat = acct_info.get("category", "")
                        if cat in ("资产", "费用", "成本"):
                            row_ref["auto_debit"].value = True
                        elif cat in ("负债", "权益", "收入"):
                            row_ref["auto_debit"].value = False

                    def _fill_avg(_r=row_ref, _avg=avg):
                        if _r["auto_debit"].value:
                            _r["debit"].value = round(_avg, 2)
                            _r["credit"].value = 0
                        else:
                            _r["credit"].value = round(_avg, 2)
                            _r["debit"].value = 0
                        show_toast("已填充平均金额", "success")
                    row_ref["suggest_box"].children[-1].on_click = _fill_avg

            sel.on_value_change(_on_account_change)


def _do_save(d, lid, date_input, desc_input, save_draft, row_entries):
    """保存新凭证"""
    from app.services import VoucherService, BudgetService, AccountService
    from app.components.state import state
    from app.components.ui_helpers import show_toast, refresh_main

    acct_list = AccountService.get_all()
    voucher_entries = _collect_entries(row_entries, acct_list)
    if not voucher_entries:
        show_toast("请至少填写一条分录", "warning")
        return

    # 超预算检查（仅非草稿状态）
    if not save_draft.value:
        date_str = date_input.value or f"{state.selected_year}-{state.selected_month:02d}-01"
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            chk_year, chk_month = dt.year, dt.month
        except Exception:
            chk_year, chk_month = state.selected_year, state.selected_month

        over_budget_items = []
        for entry in voucher_entries:
            if entry["debit"] > 0:
                result = BudgetService.check_exceeded(lid, entry["account_code"], chk_year, chk_month, entry["debit"])
                if result["has_budget"] and result["exceeded"]:
                    over_budget_items.append({
                        "account": f"{entry['account_code']} {entry['account_name']}",
                        "budget": result["budget_amount"],
                        "actual": result["actual_amount"],
                        "projected": result["projected"],
                        "remaining": result["remaining"],
                    })

        if over_budget_items:
            msg_lines = ["⚠️ 超预算预警：以下科目将超预算\n"]
            for item in over_budget_items:
                msg_lines.append(f"• {item['account']}：预算 ¥{item['budget']:,.2f}，已用 ¥{item['actual']:,.2f}，本笔后 ¥{item['projected']:,.2f}（超 ¥{abs(item['remaining']):,.2f}）")
            msg_lines.append("\n仍要保存吗？")

            with ui.dialog() as confirm_d, ui.card().classes("w-[520px]"):
                with ui.card_section():
                    ui.label("\n".join(msg_lines)).classes("text-sm whitespace-pre-wrap")
                with ui.card_section():
                    with ui.row().classes("justify-end gap-2"):
                        ui.button("取消", on_click=confirm_d.close)
                        ui.button("⚠️ 强制保存", color="danger", on_click=lambda: _force_save(d, confirm_d, lid, date_input, desc_input, voucher_entries))
            confirm_d.open()
            return

    try:
        status = "draft" if save_draft.value else "posted"
        vn = VoucherService.create(lid, date_input.value or f"{state.selected_year}-{state.selected_month:02d}-01",
                                   desc_input.value or "无摘要", voucher_entries, status=status)
        show_toast(f"✅ 凭证 {vn} 保存成功" + ("（草稿）" if status == "draft" else ""), "success")
        d.close()
        state.selected_voucher_no = vn
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _force_save(d, confirm_d, lid, date_input, desc_input, voucher_entries):
    """强制保存（忽略预算预警）"""
    from app.services import VoucherService
    from app.components.state import state
    from app.components.ui_helpers import show_toast, refresh_main
    try:
        vn = VoucherService.create(lid, date_input.value or f"{state.selected_year}-{state.selected_month:02d}-01",
                                   desc_input.value or "无摘要", voucher_entries, status="posted")
        show_toast(f"✅ 凭证 {vn} 已强制保存", "warning")
        confirm_d.close()
        d.close()
        state.selected_voucher_no = vn
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _do_edit(d, voucher_no, date_str, desc, entry_rows):
    """保存编辑后的凭证"""
    from app.services import VoucherService
    from app.components.ui_helpers import show_toast, refresh_main
    entries = _collect_entries(entry_rows)
    try:
        VoucherService.update(voucher_no, date_str=date_str, description=desc, entries=entries)
        show_toast("✅ 凭证已更新", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _collect_entries(row_refs, acct_list=None):
    """从行引用中收集凭证分录"""
    if acct_list is None:
        from app.services import AccountService
        acct_list = AccountService.get_all()
    acct_map = {a["code"]: a["name"] for a in acct_list}
    voucher_entries = []
    for r in row_refs:
        dr = r["debit"].value or 0
        cr = r["credit"].value or 0
        if dr == 0 and cr == 0:
            continue
        code = r["acct"].value
        if not code:
            continue
        name = acct_map.get(code, code)
        entry = {"account_code": code, "account_name": name, "debit": dr, "credit": cr, "summary": r["summary"].value or ""}
        fcc = r.get("foreign_ccy")
        famt = r.get("foreign_amount")
        xr = r.get("exchange_rate")
        if fcc and famt:
            entry["foreign_currency"] = fcc.value or ""
            entry["foreign_amount"] = float(famt.value or 0)
            entry["exchange_rate"] = float(xr.value or 1) if xr else 1
        voucher_entries.append(entry)
    return voucher_entries
