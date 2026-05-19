"""凭证表单 — 内联页面版（无弹窗，直接在主内容区渲染）"""
import html as html_mod
import json

from nicegui import ui

from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main, navigate
from app.services import AccountService, LedgerService, VoucherService
from app.pages.journal_form_v2 import (
    _VC_JS, _generate_voucher_no, _collect_entries,
    _do_save_v3, _do_edit_v3,
)


def render_journal_form(detail=None):
    """凭证表单内联渲染 — 直接占据主内容区，无弹窗"""
    is_edit = detail is not None

    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
        else:
            show_toast("请先创建账套", "error")
            return

    lid = state.selected_ledger_id

    # ── 顶部操作栏（返回 + 标题）──
    with ui.row().classes("w-full items-center justify-between mb-3"):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="arrow_left", on_click=lambda: navigate("journal")) \
                .props("flat dense round").classes("text-sm")
            ui.label("编辑凭证" if is_edit else "新增记账凭证") \
                .classes("text-lg font-bold").style("color:var(--c-text-primary)")
        # 右侧：凭证号
        vn = detail.get("voucher_no", "") if is_edit else _generate_voucher_no(lid)
        ui.label(f"No. {vn}") \
            .classes("text-sm font-mono font-bold px-3 py-1 rounded") \
            .style("background:var(--c-primary-light);color:var(--c-primary)")

    # ── 注入 JS ──
    ui.add_body_html(_VC_JS, shared=True)

    # ── 科目数据 ──
    _acct_data = AccountService.get_all()
    acct_opts_list = sorted([(a["code"], f"{a['code']} {a['name']}") for a in _acct_data])
    _acct_map = {a["code"]: a for a in _acct_data}

    # 初始化分录数据
    init_entries = []
    if is_edit and detail:
        for entry in detail.get("entries", []):
            init_entries.append({
                "acct_code": entry.get("account_code", ""),
                "summary": entry.get("summary", ""),
                "debit": str(entry.get("debit", 0) or ""),
                "credit": str(entry.get("credit", 0) or ""),
            })
    while len(init_entries) < 6:
        init_entries.append({"acct_code": "", "summary": "", "debit": "", "credit": ""})

    _acct_opts_base = '<option value="">— 选择科目 —</option>' + ''.join(
        f'<option value="{c}">{html_mod.escape(disp)}</option>'
        for c, disp in acct_opts_list
    )

    def _acct_options_html(selected_code=""):
        if selected_code:
            return _acct_opts_base.replace(
                f'value="{selected_code}"',
                f'value="{selected_code}" selected'
            )
        return _acct_opts_base

    vtype_opts = {"记": "记", "收": "收", "付": "付"}
    default_vtype = detail.get("voucher_type", "记") if is_edit else "记"
    default_date = detail.get("date", "") if is_edit else ""
    default_desc = detail.get("description", "") if is_edit else ""
    attach_count = detail.get("attach_count", 0) if is_edit else 0

    def _build_rows_html(entries):
        rows = ""
        for i, e in enumerate(entries):
            acct_sel = _acct_options_html(e.get("acct_code", ""))
            summ_val = html_mod.escape(e.get("summary", ""), quote=True)
            debit_val = html_mod.escape(str(e.get("debit", "")), quote=True)
            credit_val = html_mod.escape(str(e.get("credit", "")), quote=True)
            rows += f'''<tr>
                <td class="vctd vctd-seq">{i + 1}</td>
                <td class="vctd vctd-summary"><input type="text" class="vctd-inp" name="r{i}_summ" value="{summ_val}" placeholder="摘要" /></td>
                <td class="vctd vctd-acct"><select class="vctd-sel" name="r{i}_acct">{acct_sel}</select></td>
                <td class="vctd vctd-debit"><input type="number" class="vctd-inp vctd-num" name="r{i}_dr" value="{debit_val}" placeholder="0.00" step="0.01" min="0" /></td>
                <td class="vctd vctd-credit"><input type="number" class="vctd-inp vctd-num" name="r{i}_cr" value="{credit_val}" placeholder="0.00" step="0.01" min="0" /></td>
                <td class="vctd vctd-op"><button type="button" class="vctd-del-btn" onclick="v5delRow(this)">&times;</button></td>
            </tr>'''
        return rows

    def _build_table_html(entries):
        rows = _build_rows_html(entries)
        tDr = sum(float(e.get("debit", 0) or 0) for e in entries)
        tCr = sum(float(e.get("credit", 0) or 0) for e in entries)
        return f'''<table class="vctable" id="vcTable">
<thead>
    <tr>
        <th class="vcth vcth-seq">序号</th>
        <th class="vcth vcth-summary">摘　　要</th>
        <th class="vcth vcth-acct">会计科目</th>
        <th class="vcth vcth-debit">借方金额</th>
        <th class="vcth vcth-credit">贷方金额</th>
        <th class="vcth vcth-op"></th>
    </tr>
</thead>
<tbody id="vcBody">{rows}</tbody>
<tfoot>
    <tr class="vctfoot-total">
        <td class="vctd"></td>
        <td class="vctd"></td>
        <td class="vctd vctfoot-label">合　计</td>
        <td class="vctd vctd-num"><span id="vcDrTotal">¥{tDr:.2f}</span></td>
        <td class="vctd vctd-num"><span id="vcCrTotal">¥{tCr:.2f}</span></td>
        <td class="vctd"></td>
    </tr>
    <tr>
        <td colspan="6" class="vctfoot-balance">
            <span id="vcBalance" class="vc-bal-ok">借贷平衡</span>
        </td>
    </tr>
</tfoot>
</table>'''

    # ── 凭证头部 ──
    with ui.card().classes("w-full"):
        with ui.card_section().classes("vcheader").style("text-align:center;padding:16px 20px 14px;border-bottom:2px solid #1a1a1a"):
            ui.label("记 账 凭 证").style("font-size:24px;font-weight:900;letter-spacing:8px;color:#1a1a1a;margin-bottom:8px")
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("凭证字：").style("font-size:14px;color:#333")
                    vtype_sel = ui.select(vtype_opts, value=default_vtype).props("outlined dense").classes("vctype-sel")
                with ui.row().classes("items-center gap-2"):
                    ui.label("日期：").style("font-size:14px;color:#333")
                    date_input = ui.input(value=default_date).props("type=date outlined dense").classes("vcdate-inp")

        # ── 摘要 + 附件 ──
        with ui.card_section().classes("vcsection-meta").style("padding:10px 20px;border-bottom:1px solid #1a1a1a;display:flex;justify-content:space-between;align-items:center"):
            with ui.row().classes("items-center gap-2"):
                ui.label("摘要：").style("font-size:14px;font-weight:600;color:#1a1a1a")
                desc_input = ui.input(value=default_desc, placeholder="请输入凭证摘要...").props("outlined dense").classes("vcsummary-inp")
            with ui.row().classes("items-center gap-2"):
                ui.label("附件：").style("font-size:14px;color:#333")
                attach_input = ui.number(value=attach_count, precision=0).props("outlined dense").classes("vcattach-inp")
                ui.label("张").style("font-size:14px;color:#333")

        # ── 凭证模板（仅新增时）──
        if not is_edit:
            try:
                _templates = VoucherService.get_templates(lid)
            except Exception:
                _templates = []
            if _templates:
                with ui.card_section().classes("vcsection-tpl").style("padding:8px 20px;background:#FFFBEB;border-bottom:1px solid #FDE68A;display:flex;align-items:center;gap:8px"):
                    ui.icon("description", size="sm").style("color:#D97706")
                    ui.label("模板").style("font-size:13px;font-weight:600;color:#D97706")
                    template_opts = {t["id"]: t["name"] for t in _templates}
                    template_select = ui.select(options=template_opts, value=None, label="选择").props("outlined dense clearable").classes("w-44")

                    def _on_tpl_apply():
                        try:
                            tpl_id = template_select.value
                            if not tpl_id:
                                return
                            tpl = next((t for t in _templates if t["id"] == tpl_id), None)
                            if not tpl:
                                show_toast("模板不存在", "error")
                                return
                            desc_input.value = tpl.get("description", "")
                            entries = tpl.get("entries", [])
                            new_entries = []
                            for entry in entries:
                                direction = entry.get("direction", "debit")
                                amount = entry.get("amount", 0) or 0
                                new_entries.append({
                                    "acct_code": entry.get("account_code", ""),
                                    "summary": entry.get("summary", ""),
                                    "debit": str(amount) if direction == "debit" else "",
                                    "credit": str(amount) if direction == "credit" else "",
                                })
                            while len(new_entries) < 6:
                                new_entries.append({"acct_code": "", "summary": "", "debit": "", "credit": ""})
                            acct_opts_json = json.dumps(_acct_options_html())
                            entries_json = json.dumps(new_entries)
                            ui.add_head_html(f"""
                            <script>
                            (function() {{
                                window._v5PendingRebuild = {{acctOpts: {acct_opts_json}, entries: {entries_json}}};
                                if (typeof v5rebuildTable === 'function' && document.getElementById('vcBody')) {{
                                    v5rebuildTable(window._v5PendingRebuild.acctOpts, window._v5PendingRebuild.entries);
                                }}
                            }})();
                            </script>
                            """)
                            show_toast(f"已应用模板：{tpl['name']}", "success")
                        except Exception as e:
                            show_toast(f"应用模板失败: {e}", "error")

                    ui.button("应用", on_click=_on_tpl_apply).props("dense color=warning").classes("px-3 text-xs")

        # ── 分录明细表格 ──
        with ui.card_section().classes("vcsection-table").style("padding:0"):
            table_html = _build_table_html(init_entries)
            ui.html(table_html, sanitize=False)
            ui.add_head_html("""
            <script>
            (function() {
                function initV5Table() {
                    if (!document.getElementById('vcBody')) {
                        setTimeout(initV5Table, 100);
                        return;
                    }
                    document.querySelectorAll('#vcBody .vctd-num').forEach(function(inp) {
                        inp.addEventListener('input', v5calcTotals);
                    });
                    v5calcTotals();
                }
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', initV5Table);
                } else {
                    setTimeout(initV5Table, 50);
                }
            })();
            </script>
            """)

        # ── 底部签章 ──
        with ui.card_section().classes("vcsection-footer").style("padding:12px 20px;border-top:1px solid #1a1a1a;display:flex;justify-content:space-between;align-items:center"):
            with ui.row().classes("gap-8"):
                maker = state.current_user.get('username', '') if state.current_user else ''
                ui.label(f"制单人：{maker}").style("font-size:13px;color:#666")
                ui.label("审核人：").style("font-size:13px;color:#666")
                ui.label("记账人：").style("font-size:13px;color:#666")
                ui.label("出纳人：").style("font-size:13px;color:#666")

    # ── 底部操作栏（独立区域，始终可见）──
    with ui.row().classes("w-full items-center justify-between mt-3"):
        ui.button("返回列表", icon="arrow_left", on_click=lambda: navigate("journal")) \
            .props("flat").style("font-size:14px")
        with ui.row().classes("gap-3"):
            ui.button("🖨️ 打印", on_click=lambda: ui.run_javascript("window.print();")) \
                .props("dense").style("font-size:14px")
            if not is_edit:
                save_draft = ui.checkbox("存为草稿", value=False).classes("text-sm")
            if is_edit:
                edit_save_btn = ui.button("💾 保存修改", color="primary", on_click=None).props("unelevated")
                async def _on_edit_click():
                    edit_save_btn.props("loading")
                    try:
                        await _do_edit_v3(None, detail.get("voucher_no", ""), date_input.value, desc_input.value, _acct_map)
                        navigate("journal")
                    finally:
                        edit_save_btn.props(remove="loading")
                edit_save_btn.on_click(_on_edit_click)
            else:
                new_save_btn = ui.button("💾 保存凭证", color="primary", on_click=None).props("unelevated")
                async def _on_save_click():
                    new_save_btn.props("loading")
                    try:
                        # _do_save_v3 expects a dialog arg, but we're not in a dialog
                        # Call the save logic directly
                        date_str = date_input.value or ""
                        desc = desc_input.value or ""
                        entries, total_dr, total_cr = await _collect_entries(_acct_map)
                        if not date_str:
                            show_toast("请填写日期", "warning")
                            return
                        status = "draft" if save_draft.value else "posted"
                        vn = VoucherService.create(
                            lid, date_str, desc,
                            entries=[{"account_code": e["account_code"], "account_name": e["account_name"],
                                       "summary": e["summary"], "debit": e["debit"], "credit": e["credit"]}
                                     for e in entries],
                            status=status,
                            user_id=state.current_user.get("id") if state.current_user else None,
                        )
                        show_toast(f"✅ 凭证 {vn} 保存成功！", "success")
                        navigate("journal")
                    except Exception as e:
                        if "借贷不平衡" not in str(e) and "请选择" not in str(e) and "空分录" not in str(e):
                            show_toast(f"❌ 保存失败: {e}", "error")
                    finally:
                        new_save_btn.props(remove="loading")
                new_save_btn.on_click(_on_save_click)
