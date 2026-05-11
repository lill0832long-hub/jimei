"""凭证表单 v3 — 原生 HTML 表格方案（ui.html + sanitize=False）"""
import html as html_mod
import json

from nicegui import ui

from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from app.services import AccountService, LedgerService, VoucherService


def _generate_voucher_no(lid, voucher_type="记"):
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
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
        else:
            show_toast("请先创建账套", "error")
            return
    _render_voucher_form_dialog()


def show_edit_voucher_dialog(detail):
    _render_voucher_form_dialog(detail=detail)


_VC_JS = '''
<script>
if (!window.v3calcTotals) {
    window.v3calcTotals = function() {
        var rows = document.querySelectorAll('#vcBody tr');
        var tDr = 0, tCr = 0;
        rows.forEach(function(row, idx) {
            var dr = parseFloat(row.querySelector('[name$="_dr"]').value) || 0;
            var cr = parseFloat(row.querySelector('[name$="_cr"]').value) || 0;
            tDr += dr; tCr += cr;
            var seqTd = row.querySelector('.vctd-seq');
            if (seqTd) seqTd.textContent = idx + 1;
        });
        var drEl = document.getElementById('vcDrTotal');
        var crEl = document.getElementById('vcCrTotal');
        var balEl = document.getElementById('vcBalance');
        if (drEl) drEl.textContent = tDr.toFixed(2);
        if (crEl) crEl.textContent = tCr.toFixed(2);
        if (balEl) {
            var diff = Math.abs(tDr - tCr);
            if (diff > 0.01) {
                balEl.textContent = '✗ 差额 ' + diff.toFixed(2);
                balEl.className = 'vc-balance-bad';
            } else {
                balEl.textContent = '✓ 借贷平衡';
                balEl.className = 'vc-balance-ok';
            }
        }
    };
    window.v3delRow = function(btn) {
        var row = btn.closest('tr');
        var tbody = row.closest('tbody');
        if (tbody && tbody.querySelectorAll('tr').length > 1) {
            row.remove();
            v3calcTotals();
        }
    };
    window.v3addRow = function(acctOpts) {
        var tbody = document.getElementById('vcBody');
        if (!tbody) return;
        var idx = tbody.querySelectorAll('tr').length;
        var tr = document.createElement('tr');
        tr.innerHTML = '<td class="vctd vctd-seq">' + (idx+1) + '</td>'
            + '<td class="vctd vctd-summary"><input type="text" class="vctd-inp" name="r' + idx + '_summ" value="" placeholder="摘要" /></td>'
            + '<td class="vctd vctd-acct"><select class="vctd-sel" name="r' + idx + '_acct">' + acctOpts + '</select></td>'
            + '<td class="vctd vctd-debit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_dr" value="" placeholder="0.00" step="0.01" min="0" /></td>'
            + '<td class="vctd vctd-credit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_cr" value="" placeholder="0.00" step="0.01" min="0" /></td>'
            + '<td class="vctd vctd-del"><button type="button" class="vctd-del-btn" onclick="v3delRow(this)">✕</button></td>';
        tbody.appendChild(tr);
        tr.querySelectorAll('.vctd-num').forEach(function(inp) {
            inp.addEventListener('input', v3calcTotals);
        });
        v3calcTotals();
    };
    window.v3collectEntries = function() {
        var rows = document.querySelectorAll('#vcBody tr');
        var entries = [];
        rows.forEach(function(row) {
            var summ = row.querySelector('[name$="_summ"]').value;
            var acct = row.querySelector('[name$="_acct"]').value;
            var dr = parseFloat(row.querySelector('[name$="_dr"]').value) || 0;
            var cr = parseFloat(row.querySelector('[name$="_cr"]').value) || 0;
            entries.push({summary: summ, acct_code: acct, debit: dr, credit: cr});
        });
        return JSON.stringify(entries);
    };
    window.v3rebuildTable = function(acctOpts, entries) {
        var tbody = document.getElementById('vcBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        entries.forEach(function(e, idx) {
            var sel = acctOpts.replace('value="' + e.acct_code + '"', 'value="' + e.acct_code + '" selected');
            var tr = document.createElement('tr');
            tr.innerHTML = '<td class="vctd vctd-seq">' + (idx+1) + '</td>'
                + '<td class="vctd vctd-summary"><input type="text" class="vctd-inp" name="r' + idx + '_summ" value="' + (e.summary || '') + '" placeholder="摘要" /></td>'
                + '<td class="vctd vctd-acct"><select class="vctd-sel" name="r' + idx + '_acct">' + sel + '</select></td>'
                + '<td class="vctd vctd-debit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_dr" value="' + (e.debit || '') + '" placeholder="0.00" step="0.01" min="0" /></td>'
                + '<td class="vctd vctd-credit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_cr" value="' + (e.credit || '') + '" placeholder="0.00" step="0.01" min="0" /></td>'
                + '<td class="vctd vctd-del"><button type="button" class="vctd-del-btn" onclick="v3delRow(this)">✕</button></td>';
            tbody.appendChild(tr);
            tr.querySelectorAll('.vctd-num').forEach(function(inp) {
                inp.addEventListener('input', v3calcTotals);
            });
        });
        v3calcTotals();
    };
}
</script>
'''


def _render_voucher_form_dialog(detail=None):
    """凭证表单 v3 — 原生 HTML 表格"""
    ui.add_body_html(_VC_JS, shared=True)
    d = ui.dialog()
    is_edit = detail is not None

    _acct_data = AccountService.get_all()
    acct_opts_list = sorted([(a["code"], f"{a['code']} {a['name']}") for a in _acct_data])
    _acct_map = {a["code"]: a for a in _acct_data}

    from database.connection import get_conn as _get_conn
    _ccy_conn = _get_conn()
    _ccys = _ccy_conn.execute("SELECT code FROM currencies WHERE is_active=1 ORDER BY code").fetchall()
    _ccy_conn.close()

    init_entries = []
    if is_edit and detail:
        for entry in detail.get("entries", []):
            init_entries.append({
                "acct_code": entry.get("account_code", ""),
                "summary": entry.get("summary", ""),
                "debit": str(entry.get("debit", 0) or ""),
                "credit": str(entry.get("credit", 0) or ""),
            })
    while len(init_entries) < 4:
        init_entries.append({"acct_code": "", "summary": "", "debit": "", "credit": ""})

    # 构建科目选项 HTML（只构建一次，复用于所有行）
    _acct_opts_base = '<option value="">选择科目</option>' + ''.join(
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

    def _build_rows_html(entries):
        rows = ""
        for i, e in enumerate(entries):
            acct_sel = _acct_options_html(e.get("acct_code", ""))
            summ_val = html_mod.escape(e.get("summary", ""), quote=True)
            debit_val = html_mod.escape(e.get("debit", ""), quote=True)
            credit_val = html_mod.escape(e.get("credit", ""), quote=True)
            rows += f'''<tr>
                <td class="vctd vctd-seq">{i + 1}</td>
                <td class="vctd vctd-summary"><input type="text" class="vctd-inp" name="r{i}_summ" value="{summ_val}" placeholder="摘要" /></td>
                <td class="vctd vctd-acct"><select class="vctd-sel" name="r{i}_acct">{acct_sel}</select></td>
                <td class="vctd vctd-debit"><input type="number" class="vctd-inp vctd-num" name="r{i}_dr" value="{debit_val}" placeholder="0.00" step="0.01" min="0" /></td>
                <td class="vctd vctd-credit"><input type="number" class="vctd-inp vctd-num" name="r{i}_cr" value="{credit_val}" placeholder="0.00" step="0.01" min="0" /></td>
                <td class="vctd vctd-del"><button type="button" class="vctd-del-btn" onclick="v3delRow(this)">✕</button></td>
            </tr>'''
        return rows

    def _build_table_html(entries):
        rows = _build_rows_html(entries)
        return f'''<table class="vctable" id="vcTable">
<thead>
    <tr>
        <th class="vcth vcth-seq">序号</th>
        <th class="vcth vcth-summary">摘要</th>
        <th class="vcth vcth-acct">会计科目</th>
        <th class="vcth vcth-debit">借方金额</th>
        <th class="vcth vcth-credit">贷方金额</th>
        <th class="vcth vcth-del"></th>
    </tr>
</thead>
<tbody id="vcBody">{rows}</tbody>
<tfoot>
    <tr class="vctfoot-total">
        <td class="vctd"></td>
        <td class="vctd vctfoot-label">合　计</td>
        <td class="vctd"></td>
        <td class="vctd vctd-num"><span id="vcDrTotal">0.00</span></td>
        <td class="vctd vctd-num"><span id="vcCrTotal">0.00</span></td>
        <td class="vctd"></td>
    </tr>
    <tr class="vctfoot-balance">
        <td colspan="6" class="vctfoot-balance-cell">
            <span id="vcBalance" class="vc-balance-ok">✓ 借贷平衡</span>
        </td>
    </tr>
</tfoot>
</table>'''

    vtype_opts = {"记": "记", "收": "收", "付": "付"}
    default_vtype = detail.get("voucher_type", "记") if is_edit else "记"
    default_date = detail.get("date", "") if is_edit else ""
    default_desc = detail.get("description", "") if is_edit else ""
    vn = detail.get("voucher_no", "") if is_edit else _generate_voucher_no(state.selected_ledger_id)

    with d, ui.card().classes("w-[960px] max-w-[95vw]"):
        with ui.card_section().classes("pb-2"):
            with ui.row().classes("w-full items-center justify-between"):
                label = f"✏️ 编辑凭证 {detail.get('voucher_no', '')}" if is_edit else "📝 新增记账凭证"
                ui.label(label).classes("text-xl font-bold")
                ui.label(f"凭证号：{vn}").classes("text-sm text-grey-6 font-mono")

        with ui.card_section().classes("pt-2 pb-2"):
            with ui.row().classes("w-full gap-4 items-center"):
                vtype_sel = ui.select(vtype_opts, value=default_vtype, label="凭证字").props("outlined dense").classes("w-24")
                date_input = ui.input("日期", value=default_date).props("type=date outlined dense").classes("w-40")
                attach_input = ui.number("附件", value=(detail.get("attach_count", 0) if is_edit else 0), precision=0).props("outlined dense").classes("w-20")

        with ui.card_section().classes("pt-2 pb-2"):
            desc_input = ui.input("凭证摘要", value=default_desc).props("outlined dense").classes("w-full")

        if not is_edit:
            try:
                _templates = VoucherService.get_templates(state.selected_ledger_id) if state.selected_ledger_id else []
            except Exception:
                _templates = []
            if _templates:
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.icon("description").style("color:var(--c-primary)")
                        ui.label("模板").classes("text-xs font-semibold").style("color:var(--c-text-secondary)")
                        template_opts = {t["id"]: t["name"] for t in _templates}
                        template_select = ui.select(options=template_opts, value=None, label="选择模板").props("outlined dense clearable").classes("w-48")

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
                                while len(new_entries) < 4:
                                    new_entries.append({"acct_code": "", "summary": "", "debit": "", "credit": ""})
                                acct_opts_json = json.dumps(_acct_options_html())
                                entries_json = json.dumps(new_entries)
                                ui.run_javascript(f"v3rebuildTable({acct_opts_json}, {entries_json});")
                                show_toast(f"已应用模板：{tpl['name']}", "success")
                            except Exception as e:
                                show_toast(f"应用模板失败: {e}", "error")

                        ui.button("应用", on_click=_on_tpl_apply).props("dense color=primary").classes("px-3")

        with ui.card_section().classes("pt-2 pb-1"):
            ui.label("分录明细").classes("text-xs font-semibold uppercase tracking-wide mb-1").style("color:var(--c-text-secondary)")

            table_html = _build_table_html(init_entries)
            table_el = ui.html(table_html, sanitize=False)

            ui.run_javascript("""
                document.querySelectorAll('#vcBody .vctd-num').forEach(function(inp) {
                    inp.addEventListener('input', v3calcTotals);
                });
                v3calcTotals();
            """)

        with ui.card_section().classes("pt-3 pb-2"):
            with ui.row().classes("w-full justify-between items-center"):
                acct_opts_json = json.dumps(_acct_options_html())
                ui.button("➕ 添加行", on_click=lambda: ui.run_javascript(f"v3addRow({acct_opts_json});")).props("dense flat color=blue")
                with ui.row().classes("gap-2"):
                    ui.button("取消", on_click=d.close)
                    if is_edit:
                        ui.button("💾 保存", color="primary",
                                  on_click=lambda: _do_edit_v3(d, detail.get("voucher_no", ""), date_input.value, desc_input.value, _acct_map))
                    else:
                        save_draft = ui.checkbox("存为草稿", value=False).classes("text-xs")
                        ui.button("💾 保存", color="primary",
                                  on_click=lambda: _do_save_v3(d, date_input=date_input, desc_input=desc_input, save_draft=save_draft, acct_map=_acct_map))

        with ui.card_section().classes("pt-1 pb-2 border-t border-grey-1"):
            with ui.row().classes("w-full justify-between gap-4 text-xs text-grey-6"):
                maker = state.current_user.get('username', '') if state.current_user else ''
                ui.label(f"制单人：{maker}")
                ui.label("审核人：")
                ui.label("记账人：")

    d.open()


def _collect_entries(acct_map):
    """从 JS 收集分录数据并验证。返回 (entries, total_debit, total_credit) 或抛出异常。"""
    raw = ui.run_javascript("return v3collectEntries();")
    try:
        entries_raw = json.loads(raw) if isinstance(raw, str) else json.loads(raw.result if hasattr(raw, 'result') else str(raw))
    except Exception as e:
        show_toast(f"数据收集失败: {e}", "error")
        raise ValueError(str(e)) from e

    entries = []
    for e in entries_raw:
        dr = float(e.get("debit") or 0)
        cr = float(e.get("credit") or 0)
        if dr == 0 and cr == 0:
            continue
        code = e.get("acct_code", "")
        if not code:
            continue
        name = acct_map.get(code, {}).get("name", code) if isinstance(acct_map.get(code), dict) else code
        entries.append({"account_code": code, "account_name": name, "debit": dr, "credit": cr, "summary": e.get("summary", "")})

    if not entries:
        show_toast("请至少填写一条分录", "warning")
        raise ValueError("empty entries")

    total_debit = sum(e["debit"] for e in entries)
    total_credit = sum(e["credit"] for e in entries)
    if abs(total_debit - total_credit) > 0.01:
        show_toast(f"❌ 借贷不平衡！借方 ¥{total_debit:,.2f} ≠ 贷方 ¥{total_credit:,.2f}", "error")
        raise ValueError("unbalanced")

    return entries, total_debit, total_credit


def _do_save_v3(d, date_input, desc_input, save_draft, acct_map):
    """保存新凭证 v3"""
    from app.services import BudgetService

    try:
        entries, total_debit, total_credit = _collect_entries(acct_map)
    except ValueError:
        return

    if not save_draft.value:
        date_str = date_input.value or f"{state.selected_year}-{state.selected_month:02d}-01"
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            chk_year, chk_month = dt.year, dt.month
        except Exception:
            chk_year, chk_month = state.selected_year, state.selected_month
        over = []
        for entry in entries:
            if entry["debit"] > 0:
                result = BudgetService.check_exceeded(state.selected_ledger_id, entry["account_code"], chk_year, chk_month, entry["debit"])
                if result["has_budget"] and result["exceeded"]:
                    over.append({"account": f"{entry['account_code']} {entry['account_name']}", "budget": result["budget_amount"], "actual": result["actual_amount"], "projected": result["projected"], "remaining": result["remaining"]})
        if over:
            msg = ["⚠️ 超预算预警：以下科目将超预算\n"]
            for item in over:
                msg.append(f"• {item['account']}：预算 ¥{item['budget']:,.2f}，已用 ¥{item['actual']:,.2f}")
            msg.append("\n仍要保存吗？")
            with ui.dialog() as cd, ui.card().classes("w-[520px]"):
                with ui.card_section():
                    ui.label("\n".join(msg)).classes("text-sm whitespace-pre-wrap")
                with ui.card_section():
                    with ui.row().classes("justify-end gap-2"):
                        ui.button("取消", on_click=cd.close)
                        ui.button("⚠️ 强制保存", color="danger", on_click=lambda: _force_save_v3(d, cd, date_input, desc_input, entries))
            cd.open()
            return

    try:
        status = "draft" if save_draft.value else "posted"
        vn = VoucherService.create(state.selected_ledger_id,
            date_input.value or f"{state.selected_year}-{state.selected_month:02d}-01",
            desc_input.value or "无摘要", entries, status=status)
        show_toast(f"✅ 凭证 {vn} 保存成功" + ("（草稿）" if status == "draft" else ""), "success")
        d.close()
        state.selected_voucher_no = vn
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _force_save_v3(d, cd, date_input, desc_input, entries):
    try:
        vn = VoucherService.create(state.selected_ledger_id,
            date_input.value or f"{state.selected_year}-{state.selected_month:02d}-01",
            desc_input.value or "无摘要", entries, status="posted")
        show_toast(f"✅ 凭证 {vn} 已强制保存", "warning")
        cd.close()
        d.close()
        state.selected_voucher_no = vn
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")


def _do_edit_v3(d, voucher_no, date_str, desc, acct_map):
    """保存编辑后的凭证 v3"""
    try:
        entries, total_debit, total_credit = _collect_entries(acct_map)
    except ValueError:
        return

    try:
        VoucherService.update(voucher_no, date_str=date_str, description=desc, entries=entries)
        show_toast("✅ 凭证已更新", "success")
        d.close()
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
