"""凭证管理"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, show_modal_error, navigate, format_amount, refresh_main
from database_v3 import (
    get_conn, get_ledgers, get_vouchers, get_voucher_detail, create_voucher,
    update_voucher, post_voucher, reverse_voucher, delete_voucher,
    submit_for_review, approve_voucher, reject_voucher, get_accounts,
    search_voucher_history_v2, get_account_suggestions, get_avg_amount_for_account,
)

def _generate_voucher_no(lid, voucher_type="记"):
    """自动生成凭证编号：类型+年月+序号，如 记-202604-001"""
    from datetime import datetime as _dt
    prefix = f"{voucher_type}-{_dt.now().strftime('%Y%m')}-"
    try:
        existing = get_vouchers(lid, _dt.now().year, _dt.now().month, limit=200)
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


def _get_account_search_options():
    """获取科目搜索选项列表，返回 [(code, display_text), ...]"""
    accounts = get_accounts()
    return [(a["code"], f"{a['code']} {a['name']}") for a in accounts]


def _find_account_by_keyword(keyword):
    """根据关键词模糊搜索科目，返回匹配的 (code, display_text) 列表"""
    if not keyword:
        return _get_account_search_options()
    kw = keyword.strip().lower()
    results = []
    for code, display in _get_account_search_options():
        if kw in code.lower() or kw in display.lower():
            results.append((code, display))
    return results



def render_journal():
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # 权限检查
    user = state.current_user
    can_create  = user and user.get("role") in ("admin", "accountant")
    can_approve = user and user.get("role") in ("admin", "reviewer")
    can_post    = user and user.get("role") in ("admin", "poster")

    with ui.row().classes("w-full gap-3"):
        # ── 左侧：凭证列表（2/3）──
        with ui.column().classes("w-2/3 gap-2"):
            with ui.card().classes("w-full"):
                # 标题行 + 状态筛选
                with ui.card_section().classes("py-2 px-3"):
                    with ui.row().classes("items-center justify-between"):
                        ui.label("📋 凭证列表").classes("text-base font-bold")
                        with ui.row().classes("items-center gap-2"):
                            # 状态筛选 chips
                            ALL_STATUS = [("all","全部"),("draft","草稿"),("pending_review","待审核"),("posted","已过账"),("reversed","已冲销")]
                            for skey, slabel in ALL_STATUS:
                                is_active = state.voucher_status_filter == skey
                                ui.chip(slabel, on_click=lambda k=skey: (
                                    setattr(state, 'voucher_status_filter', k),
                                    refresh_main()
                                )).props("outline dense").style(
                                    f"background:{'var(--c-primary-light)' if is_active else 'transparent'};"
                                    f"color:{'var(--c-primary)' if is_active else 'var(--c-text-secondary)'};"
                                    f"border-color:{'var(--c-primary)' if is_active else 'var(--c-border)'}"
                                )
                            if can_create:
                                ui.button("➕ 新增凭证", color="primary", on_click=show_new_voucher_dialog).props("dense")

                # 按状态筛选获取凭证
                filter_status = state.voucher_status_filter if state.voucher_status_filter != "all" else None
                vouchers = get_vouchers(lid, state.selected_year, state.selected_month,
                                       status=filter_status, limit=50)
                if not vouchers:
                    with ui.card_section():
                        ui.label("本月暂无凭证").classes("text-sm").style("color:var(--c-text-muted)")

                status_labels = {"draft":"草稿","posted":"已过账","reversed":"已冲销","pending_review":"待审核"}
                status_colors = {"draft":"orange","posted":"green","reversed":"red","pending_review":"blue"}
                rows = [{**v,
                    "status_label": status_labels.get(v["status"], v["status"]),
                    "status_color": status_colors.get(v["status"], "grey"),
                    "total": f'¥{v["total_debit"]:,.2f}',
                } for v in vouchers]

                cols = [
                    {"name":"voucher_no","label":"凭证号","field":"voucher_no","align":"left"},
                    {"name":"date","label":"日期","field":"date"},
                    {"name":"description","label":"摘要","field":"description","align":"left"},
                    {"name":"total","label":"金额","field":"total","align":"right"},
                    {"name":"status","label":"状态","field":"status_label","align":"center"},
                ]
                tbl = ui.table(columns=cols, rows=rows, row_key="voucher_no",
                              pagination={"rowsPerPage":12}).classes("w-full text-sm")
                tbl.add_slot("body-cell-voucher_no", r"""
                    <q-td key="voucher_no" :props="props">
                        <q-btn flat dense no-caps color="primary" :label="props.row.voucher_no"
                               @click="$parent.$emit('show', props.row.voucher_no)" />
                    </q-td>
                """)
                tbl.add_slot("body-cell-status", r"""
                    <q-td key="status" :props="props">
                        <q-badge :color="props.row.status_color" :label="props.row.status_label" size="sm" />
                    </q-td>
                """)
                tbl.on("show", lambda e: show_voucher_detail(e.args))

        # ── 右侧：凭证详情（1/3）──
        with ui.column().classes("w-1/3 gap-2"):
            if state.selected_voucher_no:
                render_voucher_detail(state.selected_voucher_no)
            else:
                with ui.card().classes("w-full"):
                    with ui.card_section().classes("text-center py-8"):
                        ui.icon("receipt_long").classes("text-4xl").style("color:var(--c-text-muted)")
                        ui.label("点击凭证号查看详情").classes("text-sm mt-2").style("color:var(--c-text-muted)")


def show_voucher_detail(voucher_no):
    state.selected_voucher_no = voucher_no
    refresh_main()


def render_voucher_detail(voucher_no):
    detail = get_voucher_detail(voucher_no)
    if not detail:
        return
    user = state.current_user
    role = user.get("role", "viewer") if user else "viewer"
    status = detail["status"]
    status_labels = {"draft":"草稿","posted":"已过账","reversed":"已冲销","pending_review":"待审核"}
    status_colors = {"draft":"orange","posted":"green","reversed":"red","pending_review":"blue"}

    # 流程可视化：草稿 → 待审核 → 已过账
    flow_steps = [
        ("draft",         "草稿",  "edit"),
        ("pending_review", "待审核", "hourglass_empty"),
        ("posted",        "已过账", "check_circle"),
    ]
    with ui.card().classes("w-full"):
        # ── 流程进度条 ──
        with ui.card_section().classes("py-1.5 px-3 border-b").style("border-color:var(--c-border-light)"):
            with ui.row().classes("items-center justify-center gap-0"):
                for i, (skey, slabel, sicon) in enumerate(flow_steps):
                    is_active = status == skey
                    is_passed = (skey == "draft" and status in ("pending_review","posted","reversed")) or \
                                (skey == "pending_review" and status == "posted")
                    if i > 0:
                        ui.element("div").style(
                            f"width:40px;height:2px;background:{'var(--c-success)' if is_passed or is_active else 'var(--c-border)'};flex-shrink:0"
                        )
                    with ui.column().classes("items-center gap-0").style("cursor:default"):
                        ui.icon(sicon).style(
                            f"font-size:20px;color:{'var(--c-success)' if is_passed else 'var(--c-primary)' if is_active else 'var(--c-border)'}"
                        )
                        ui.label(slabel).style(
                            f"font-size:10px;color:{'var(--c-success)' if is_passed else 'var(--c-primary)' if is_active else 'var(--c-text-muted)'}"
                        )

        # ── 头部信息 ──
        with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light);background:var(--c-bg-hover)"):
            with ui.row().classes("items-center justify-between"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(voucher_no).classes("font-bold text-base").style("color:var(--c-text-primary)")
                    ui.badge(status_labels.get(status, status),
                            color=status_colors.get(status, "grey"))
                with ui.row().classes("gap-4 text-xs").style("color:var(--c-text-muted)"):
                    ui.label(f"📅 {detail['date']}")
                    ui.label(f"📝 {detail['description']}")

        # ── 分录明细 ──
        entries = detail.get("entries", [])
        cols = [
            {"name":"account_code","label":"代码","field":"account_code"},
            {"name":"account_name","label":"科目","field":"account_name"},
            {"name":"debit","label":"借方","field":"debit","align":"right"},
            {"name":"credit","label":"贷方","field":"credit","align":"right"},
        ]
        rows = [{**e, "debit": f'{e["debit"]:,.2f}' if e["debit"] else "",
                      "credit": f'{e["credit"]:,.2f}' if e["credit"] else ""} for e in entries]
        ui.table(columns=cols, rows=rows, row_key="id", pagination=False).classes("w-full text-sm")

        # ── 合计行 ──
        with ui.card_section().classes("py-1 px-3"):
            with ui.row().classes("justify-end gap-4 text-sm"):
                ui.label(f"借：¥{detail['total_debit']:,.2f}").style("color:var(--c-danger)")
                ui.label(f"贷：¥{detail['total_credit']:,.2f}").style("color:var(--c-primary)")

        # ── 操作按钮（按权限显示）──
        with ui.card_section().classes("py-1 px-3"):
            with ui.row().classes("justify-end gap-1"):
                if status == "draft":
                    if role in ("admin", "accountant"):
                        ui.button("提交审核", color="blue", on_click=lambda: do_submit_review(voucher_no)).props("dense text-sm")
                        ui.button("直接过账", color="green", on_click=lambda: do_post_voucher(voucher_no)).props("dense text-sm")
                        ui.button("编辑", color="orange", on_click=lambda: show_edit_voucher_dialog(detail)).props("dense text-sm")
                        ui.button("删除", color="red", on_click=lambda: do_delete_voucher(voucher_no)).props("dense text-sm")
                elif status == "pending_review":
                    if role in ("admin", "reviewer"):
                        ui.button("✅ 通过", color="green", on_click=lambda: do_approve_voucher(voucher_no)).props("dense text-sm")
                        ui.button("❌ 驳回", color="red", on_click=lambda: show_reject_dialog(voucher_no)).props("dense text-sm")
                    else:
                        ui.label("等待审核中...").classes("text-sm").style("color:var(--c-text-muted)")
                elif status == "posted":
                    if role in ("admin", "poster"):
                        ui.button("冲销", color="red", on_click=lambda: show_reverse_dialog(voucher_no)).props("dense text-sm")
                elif status == "reversed":
                    ui.label("已冲销").classes("text-sm").style("color:var(--c-danger)")


# ===== 新增凭证 =====
def show_new_voucher_dialog():
    # 确保有选中的账套
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
        else:
            show_toast("❌ 请先创建账套", "error")
            return
    d = ui.dialog()
    row_refs = []

    with d, ui.card().classes("w-[750px] max-w-[95vw]"):
        with ui.card_section():
            ui.label("📝 新增记账凭证").classes("text-xl font-bold")

        # 凭证模板快捷选择
        try:
            _templates = get_voucher_templates(state.selected_ledger_id) if state.selected_ledger_id else []
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
                        # 清空现有分录行并填充模板数据
                        entries_col.clear()
                        desc_input.value = tpl.get("description", "")
                        for entry in tpl.get("entries", []):
                            add_row(
                                acct_code=entry.get("account_code", ""),
                                summary=entry.get("summary", ""),
                                debit=entry.get("debit", 0) if entry.get("direction") == "debit" else 0,
                                credit=entry.get("credit", 0) if entry.get("direction") == "credit" else 0,
                            )
                        show_toast(f"已应用模板：{tpl['name']}", "success")

                    ui.button("应用", on_click=_on_template_apply).props("dense color=primary").classes("px-3")

        with ui.card_section():
            with ui.row().classes("w-full gap-4"):
                date_input = ui.input("日期", value=f"{state.selected_year}-{state.selected_month:02d}-01").props("type=date outlined dense").classes("w-40")
                desc_input = ui.input("凭证摘要").props("outlined dense").classes("flex-grow")
            save_draft = ui.checkbox("保存为草稿", value=False)

        acct_opts = {a["code"]: f"{a['code']} {a['name']}" for a in get_accounts()}

        with ui.card_section():
            ui.label("分录明细").classes("text-xs font-semibold uppercase tracking-wide mb-2").style("color:var(--c-text-secondary)")
            entries_col = ui.column().classes("w-full gap-1")

            # 获取币种选项
            _ccy_conn = get_conn()
            _ccys = _ccy_conn.execute("SELECT code FROM currencies WHERE is_active=1 ORDER BY code").fetchall()
            _ccy_conn.close()
            _ccy_opts = {c["code"]: c["code"] for c in _ccys} if _ccys else {"CNY": "CNY"}
            _default_ccy = state.selected_ledger_currency if hasattr(state, 'selected_ledger_currency') else "CNY"

            def add_row(acct_code="1002", summary="", debit=0, credit=0, foreign_ccy="", foreign_amount=0, exchange_rate=1):
                """创建一行分录，带智能联想功能"""
                # 智能联想数据容器
                suggest_label = ui.label("").classes("text-xs text-blue-600 mt-0.5 mb-0 w-full").style("min-height:16px;transition:all 0.2s")
                avg_label = ui.label("").classes("text-xs text-green-600 mt-0 mb-0 w-full").style("min-height:16px")
                acct_suggest_items = ui.column().classes("w-full gap-0 mt-0 mb-1").style("display:none")
                history_items = ui.column().classes("w-full gap-0 mt-0 mb-1").style("display:none")

                with entries_col:
                    with ui.column().classes("w-full gap-0 mb-1") as row_col:
                        # ── 联想提示区（在输入框上方）──
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
                            # 外币列
                            ccy_sel = ui.select(options=_ccy_opts, value=foreign_ccy or _default_ccy, label="币种").props("outlined dense").classes("w-20")
                            famt = ui.number("外币金额", value=foreign_amount, precision=2).props("outlined dense").classes("w-28")
                            xr = ui.number("汇率", value=exchange_rate if exchange_rate != 1 else 1, precision=6).props("outlined dense").classes("w-24")

                            r = {"acct": sel, "summary": summ, "debit": dr, "credit": cr,
                                 "foreign_ccy": ccy_sel, "foreign_amount": famt, "exchange_rate": xr,
                                 "suggest_box": suggest_box, "suggest_info": suggest_info,
                                 "auto_debit": auto_debit, "row_col": row_col}
                            row_refs.append(r)

                            ui.button(icon="close", color="grey", on_click=lambda _r=r, _el=row_col: (_el.delete(), row_refs.remove(_r) if _r in row_refs else None)).props("flat dense")

                        # ── 摘要输入 → 历史凭证联想 ──
                        def _on_summary_change(row_ref=r):
                            kw = row_ref["summary"].value or ""
                            if len(kw) < 2:
                                row_ref["suggest_box"].style("display:none")
                                return
                            lid = state.selected_ledger_id
                            if not lid:
                                return
                            results = search_voucher_history_v2(lid, kw, limit=5)
                            if not results:
                                row_ref["suggest_box"].style("display:none")
                                return
                            row_ref["suggest_box"].style("display:flex")
                            # 取第一条显示
                            first = results[0]
                            acct_display = f"{first['account_code']} {first['account_name']}" if first.get('account_code') else ""
                            avg_amt = f"¥{first['avg_amount']:,.2f}" if first.get('avg_amount') else ""
                            row_ref["suggest_info"].text = f"💡 {acct_display}  {avg_amt}"
                            # 更新填充按钮
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

                        # ── 科目选择 → 金额推荐 + 借贷方向判断 ──
                        def _on_account_change(row_ref=r):
                            code = row_ref["acct"].value
                            if not code:
                                return
                            lid = state.selected_ledger_id
                            if not lid:
                                return
                            # 获取平均金额
                            avg = get_avg_amount_for_account(lid, code, months=3)
                            if avg and avg > 0:
                                row_ref["suggest_box"].style("display:flex")
                                row_ref["suggest_info"].text = f"💰 近3月平均: ¥{avg:,.2f}"
                                # 根据科目性质判断借贷方向
                                acct_info = next((a for a in get_accounts() if a["code"] == code), None)
                                if acct_info:
                                    cat = acct_info.get("category", "")
                                    # 资产/费用类 → 借方增加；负债/权益/收入类 → 贷方增加
                                    if cat in ("资产", "费用", "成本"):
                                        row_ref["auto_debit"].value = True
                                    elif cat in ("负债", "权益", "收入"):
                                        row_ref["auto_debit"].value = False
                                # 更新填充按钮
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

            for _ in range(4):
                add_row()

            ui.button("➕ 添加行", on_click=add_row, color="blue").props("dense flat")

        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("💾 保存", color="primary",
                          on_click=lambda: _do_save(d, lid=state.selected_ledger_id,
                                                     date_input=date_input, desc_input=desc_input,
                                                     save_draft=save_draft, row_refs=row_refs))
    d.open()


def _do_save(d, lid, date_input, desc_input, save_draft, row_refs):
    from database_v3 import check_budget_exceeded
    voucher_entries = []
    for r in row_refs:
        dr = r["debit"].value or 0
        cr = r["credit"].value or 0
        if dr == 0 and cr == 0:
            continue
        code = r["acct"].value
        if not code:
            continue
        name = next((a["name"] for a in get_accounts() if a["code"] == code), code)
        entry = {"account_code": code, "account_name": name, "debit": dr, "credit": cr, "summary": r["summary"].value or ""}
        # 外币字段
        fcc = r.get("foreign_ccy")
        famt = r.get("foreign_amount")
        xr = r.get("exchange_rate")
        if fcc and famt:
            entry["foreign_currency"] = fcc.value or ""
            entry["foreign_amount"] = float(famt.value or 0)
            entry["exchange_rate"] = float(xr.value or 1) if xr else 1
        voucher_entries.append(entry)
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
                result = check_budget_exceeded(lid, entry["account_code"], chk_year, chk_month, entry["debit"])
                if result["has_budget"] and result["exceeded"]:
                    over_budget_items.append({
                        "account": f"{entry['account_code']} {entry['account_name']}",
                        "budget": result["budget_amount"],
                        "actual": result["actual_amount"],
                        "projected": result["projected"],
                        "remaining": result["remaining"],
                    })

        if over_budget_items:
            msg_lines = [f"⚠️ 超预算预警：以下科目将超预算\n"]
            for item in over_budget_items:
                msg_lines.append(f"• {item['account']}：预算 ¥{item['budget']:,.2f}，已用 ¥{item['actual']:,.2f}，本笔后 ¥{item['projected']:,.2f}（超 ¥{abs(item['remaining']):,.2f}）")
            msg_lines.append("\n仍要保存吗？")

            with ui.dialog() as confirm_d, ui.card().classes("w-[520px]"):
                with ui.card_section():
                    ui.label("\n".join(msg_lines)).classes("text-sm whitespace-pre-wrap")
                with ui.card_section():
                    with ui.row().classes("justify-end gap-2"):
                        ui.button("取消", on_click=confirm_d.close)
                        ui.button("⚠️ 强制保存", color="danger", on_click=lambda: _force_save_voucher(
                            d, confirm_d, lid, date_input, desc_input, voucher_entries
                        ))
            confirm_d.open()
            return

    try:
        status = "draft" if save_draft.value else "posted"
        vn = create_voucher(lid, date_input.value or f"{state.selected_year}-{state.selected_month:02d}-01",
                            desc_input.value or "无摘要", voucher_entries, status=status)
        show_toast(f"✅ 凭证 {vn} 保存成功" + ("（草稿）" if status == "draft" else ""), "success")
        d.close()
        state.selected_voucher_no = vn
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _force_save_voucher(d, confirm_d, lid, date_input, desc_input, voucher_entries):
    """强制保存（忽略预算预警）"""
    from database_v3 import create_voucher
    try:
        vn = create_voucher(lid, date_input.value or f"{state.selected_year}-{state.selected_month:02d}-01",
                            desc_input.value or "无摘要", voucher_entries, status="posted")
        show_toast(f"✅ 凭证 {vn} 已强制保存", "warning")
        confirm_d.close()
        d.close()
        state.selected_voucher_no = vn
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")

# ===== 过账/冲销/删除 =====
def _get_user_id():
    return state.current_user.get("id") if state.current_user else None

def do_submit_review(voucher_no):
    try:
        lid = state.selected_ledger_id
        submit_for_review(lid, voucher_no, user_id=_get_user_id())
        show_toast(f"凭证 {voucher_no} 已提交审核", "info")
        refresh_main()
    except Exception as e:
        show_toast(f"提交审核失败: {e}", "error")


def do_approve_voucher(voucher_no):
    try:
        lid = state.selected_ledger_id
        approve_voucher(lid, voucher_no, user_id=_get_user_id())
        show_toast(f"凭证 {voucher_no} 审核通过并已过账", "success")
        refresh_main()
    except Exception as e:
        show_toast(f"审核失败: {e}", "error")


def do_reject_voucher(voucher_no, reason="审核拒绝"):
    try:
        lid = state.selected_ledger_id
        reject_voucher(lid, voucher_no, reason=reason, user_id=_get_user_id())
        show_toast(f"凭证 {voucher_no} 已退回草稿", "warning")
        refresh_main()
    except Exception as e:
        show_toast(f"驳回失败: {e}", "error")


def show_reject_dialog(voucher_no):
    """驳回对话框（带原因输入）"""
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label(f"❌ 驳回凭证 {voucher_no}").classes("text-lg font-bold").style("color:var(--c-danger)")
            reason_input = ui.input("驳回原因", placeholder="请输入驳回原因").props("outlined").classes("w-full mt-2")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("确认驳回", color="red",
                          on_click=lambda: (do_reject_voucher(voucher_no, reason_input.value), d.close()))
    d.open()


def do_post_voucher(voucher_no):
    try:
        post_voucher(voucher_no)
        show_toast(f"凭证 {voucher_no} 已过账", "success")
        refresh_main()
    except Exception as e:
        show_toast(f"post failed: {e}", "error")


def do_delete_voucher(voucher_no):
    try:
        delete_voucher(voucher_no)
        show_toast(f"✅ 凭证 {voucher_no} 已删除", "success")
        state.selected_voucher_no = None
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def show_reverse_dialog(voucher_no):
    d = ui.dialog()
    with d, ui.card().classes("w-96"):
        with ui.card_section():
            ui.label(f"🔄 冲销凭证 {voucher_no}").classes("text-lg font-bold")
            ui.label("冲销将生成红字凭证，原凭证标记为已冲销").style("color:var(--c-text-secondary)")
            reason_input = ui.input("冲销原因", placeholder="选填").props("outlined").classes("w-full mt-2")
        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("确认冲销", color="red", on_click=lambda: do_reverse(d, voucher_no, reason_input.value))
    d.open()


def do_reverse(d, voucher_no, reason):
    try:
        rev_no = reverse_voucher(voucher_no, reason or "")
        show_toast(f"✅ 已冲销，新凭证：{rev_no}", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def show_edit_voucher_dialog(detail):
    d = ui.dialog()
    with d, ui.card().classes("w-[750px] max-w-[95vw]"):
        with ui.card_section():
            ui.label(f"✏️ 编辑凭证 {detail['voucher_no']}").classes("text-xl font-bold")
        with ui.card_section():
            date_input = ui.input("日期", value=detail["date"]).props("type=date outlined dense").classes("w-40")
            desc_input = ui.input("凭证摘要", value=detail["description"] or "").props("outlined dense").classes("flex-grow")
        with ui.card_section():
            ui.label("分录明细").classes("font-bold mb-2")
            entries_col = ui.column().classes("w-full gap-1")
            acct_opts = {a["code"]: f"{a['code']} {a['name']}" for a in get_accounts()}
            entry_rows = []
            for entry in detail.get("entries", []):
                with entries_col:
                    with ui.row().classes("items-center gap-2 w-full"):
                        acct_sel = ui.select(options=acct_opts, value=entry["account_code"]).props("outlined dense").classes("w-56")
                        summary_in = ui.input("摘要", value=entry["summary"] or "").props("outlined dense").classes("flex-grow")
                        debit_in = ui.number("借方", value=entry["debit"] or 0, precision=2).props("outlined dense").classes("w-28")
                        credit_in = ui.number("贷方", value=entry["credit"] or 0, precision=2).props("outlined dense").classes("w-28")
                entry_rows.append({"acct": acct_sel, "summary": summary_in, "debit": debit_in, "credit": credit_in})

        with ui.card_section():
            with ui.row().classes("justify-end gap-2"):
                ui.button("取消", on_click=d.close)
                ui.button("💾 保存", color="primary",
                    on_click=lambda: do_edit_voucher(d, detail["voucher_no"], date_input.value, desc_input.value, entry_rows))
    d.open()



def do_edit_voucher(d, voucher_no, date_str, desc, entry_rows):
    entries = []
    for r in entry_rows:
        dr = r["debit"].value or 0
        cr = r["credit"].value or 0
        if dr == 0 and cr == 0:
            continue
        code = r["acct"].value
        name = next((a["name"] for a in get_accounts() if a["code"] == code), code)
        entries.append({"account_code": code, "account_name": name, "debit": dr, "credit": cr, "summary": r["summary"].value or ""})
    try:
        update_voucher(voucher_no, date_str=date_str, description=desc, entries=entries)
        show_toast("✅ 凭证已更新", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def render_voucher_detail_page():
    """凭证详情页（从侧边栏直接进入）"""
    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-12 text-center"):
            ui.icon("description").style("font-size: 48px; color: var(--gray-300)")
            ui.label("凭证详情").classes("text-lg font-semibold mt-4").style("color:var(--c-text-muted)")
            ui.label("请从「记账凭证」列表点击进入详情").classes("text-sm mt-2").style("color:var(--c-text-muted)")


