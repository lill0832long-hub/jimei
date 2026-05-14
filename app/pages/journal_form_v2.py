"""凭证表单 v4 — 传统 Excel 记账凭证风格（NiceGUI 组件 + 原生 HTML 表格）"""
import html as html_mod
import json

from nicegui import ui

from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from app.services import AccountService, LedgerService, VoucherService, CurrencyService


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


# ─── 原生 HTML 表格方案（Excel 风格，打印友好） ───

_VC_JS = '''
<script>
if (!window.v4calcTotals) {
    window.v4calcTotals = function() {
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
        if (drEl) drEl.textContent = '¥' + tDr.toFixed(2);
        if (crEl) crEl.textContent = '¥' + tCr.toFixed(2);
        if (balEl) {
            var diff = Math.abs(tDr - tCr);
            if (diff > 0.01) {
                balEl.textContent = '借贷不平衡，差额 ' + diff.toFixed(2);
                balEl.className = 'vc-balance-bad';
            } else {
                balEl.textContent = '借贷平衡';
                balEl.className = 'vc-balance-ok';
            }
        }
    };
    window.v4delRow = function(btn) {
        var row = btn.closest('tr');
        var tbody = row.closest('tbody');
        if (tbody && tbody.querySelectorAll('tr').length > 1) {
            row.remove();
            v4calcTotals();
        }
    };
    window.v4addRow = function(acctOpts) {
        var tbody = document.getElementById('vcBody');
        if (!tbody) return;
        var idx = tbody.querySelectorAll('tr').length;
        var tr = document.createElement('tr');
        tr.innerHTML = '<td class="vctd vctd-seq">' + (idx+1) + '</td>'
            + '<td class="vctd vctd-summary"><input type="text" class="vctd-inp" name="r' + idx + '_summ" value="" placeholder="摘要" /></td>'
            + '<td class="vctd vctd-acct"><select class="vctd-sel" name="r' + idx + '_acct">' + acctOpts + '</select></td>'
            + '<td class="vctd vctd-debit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_dr" value="" placeholder="0.00" step="0.01" min="0" /></td>'
            + '<td class="vctd vctd-credit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_cr" value="" placeholder="0.00" step="0.01" min="0" /></td>'
            + '<td class="vctd vctd-del"><button type="button" class="vctd-del-btn" onclick="v4delRow(this)">✕</button></td>';
        tbody.appendChild(tr);
        tr.querySelectorAll('.vctd-num').forEach(function(inp) {
            inp.addEventListener('input', v4calcTotals);
        });
        v4calcTotals();
    };
    window.v4rebuildTable = function(acctOpts, entries) {
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
                + '<td class="vctd vctd-del"><button type="button" class="vctd-del-btn" onclick="v4delRow(this)">✕</button></td>';
            tbody.appendChild(tr);
            tr.querySelectorAll('.vctd-num').forEach(function(inp) {
                inp.addEventListener('input', v4calcTotals);
            });
        });
        v4calcTotals();
    };
    window.v4collectEntries = function() {
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
}
</script>
'''


def _render_voucher_form_dialog(detail=None):
    """凭证表单 v4 — 传统 Excel 记账凭证风格"""
    ui.add_body_html(_VC_JS, shared=True)
    d = ui.dialog()
    is_edit = detail is not None

    _acct_data = AccountService.get_all()
    acct_opts_list = sorted([(a["code"], f"{a['code']} {a['name']}") for a in _acct_data])
    _acct_map = {a["code"]: a for a in _acct_data}

    _ccys = CurrencyService.get_active_codes()

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

    # 科目选项 HTML（只构建一次）
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
                <td class="vctd vctd-del"><button type="button" class="vctd-del-btn" onclick="v4delRow(this)">&times;</button></td>
            </tr>'''
        return rows

    def _build_table_html(entries):
        rows = _build_rows_html(entries)
        # 计算初始合计
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
        <th class="vcth vcth-del"></th>
    </tr>
</thead>
<tbody id="vcBody">{rows}</tbody>
<tfoot>
    <tr class="vctfoot-total">
        <td class="vctd"></td>
        <td class="vctd vctfoot-label" style="text-align:center;font-weight:700;">合　计</td>
        <td class="vctd"></td>
        <td class="vctd vctd-num vc-total-debit"><span id="vcDrTotal">¥{tDr:.2f}</span></td>
        <td class="vctd vctd-num vc-total-credit"><span id="vcCrTotal">¥{tCr:.2f}</span></td>
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

    with d, ui.card().classes("w-[980px] max-w-[96vw] rounded-lg shadow-xl"):
        # ── 标题栏 ──
        with ui.card_section().classes("py-3 px-5 bg-indigo-600 text-white rounded-t-lg"):
            with ui.row().classes("w-full items-center justify-between"):
                label = f"✏️ 编辑凭证" if is_edit else "📝 新增记账凭证"
                ui.label(label).classes("text-lg font-bold tracking-wide")
                with ui.column().classes("items-end gap-0"):
                    ui.label(f"凭证号：{vn}").classes("text-sm font-mono opacity-90")
                    if is_edit:
                        ui.label(f"日期：{default_date}").classes("text-xs opacity-75")

        # ── 凭证头信息 ──
        with ui.card_section().classes("py-3 px-5 bg-indigo-50 border-b border-indigo-100"):
            with ui.row().classes("w-full gap-4 items-center"):
                vtype_sel = ui.select(vtype_opts, value=default_vtype, label="凭证字").props("outlined dense").classes("w-24")
                date_input = ui.input("日期", value=default_date).props("type=date outlined dense").classes("w-40")
                attach_input = ui.number("附件数", value=(detail.get("attach_count", 0) if is_edit else 0), precision=0).props("outlined dense").classes("w-20")

        # ── 摘要 ──
        with ui.card_section().classes("py-2 px-5 border-b border-grey-100"):
            desc_input = ui.input("凭证摘要", value=default_desc, placeholder="请输入凭证摘要...").props("outlined dense").classes("w-full")

        # ── 凭证模板 ──
        if not is_edit:
            try:
                _templates = VoucherService.get_templates(state.selected_ledger_id) if state.selected_ledger_id else []
            except Exception:
                _templates = []
            if _templates:
                with ui.card_section().classes("py-2 px-5 bg-amber-50 border-b border-amber-100"):
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.icon("description", size="sm").classes("text-amber-600")
                        ui.label("凭证模板").classes("text-xs font-semibold").classes("text-amber-700")
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
                                while len(new_entries) < 6:
                                    new_entries.append({"acct_code": "", "summary": "", "debit": "", "credit": ""})
                                acct_opts_json = json.dumps(_acct_options_html())
                                entries_json = json.dumps(new_entries)
                                ui.run_javascript(f"v4rebuildTable({acct_opts_json}, {entries_json});")
                                show_toast(f"已应用模板：{tpl['name']}", "success")
                            except Exception as e:
                                show_toast(f"应用模板失败: {e}", "error")

                        ui.button("应用", on_click=_on_tpl_apply).props("dense color=warning").classes("px-3 text-xs")

        # ── 分录明细表格 ──
        with ui.card_section().classes("p-0"):
            table_html = _build_table_html(init_entries)
            ui.html(table_html, sanitize=False)
            ui.run_javascript("""
                document.querySelectorAll('#vcBody .vctd-num').forEach(function(inp) {
                    inp.addEventListener('input', v4calcTotals);
                });
                v4calcTotals();
            """)

        # ── 操作按钮 ──
        with ui.card_section().classes("py-3 px-5 border-t border-grey-100"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.row().classes("gap-2"):
                    acct_opts_json = json.dumps(_acct_options_html())
                    ui.button("➕ 添加行", on_click=lambda: ui.run_javascript(f"v4addRow({acct_opts_json});")).props("dense flat color=primary").classes("text-sm")
                with ui.row().classes("gap-3 items-center"):
                    if not is_edit:
                        save_draft = ui.checkbox("存为草稿", value=False).classes("text-xs")
                    ui.button("取消", on_click=d.close).props("flat")
                    if is_edit:
                        edit_save_btn = ui.button("💾 保存修改", color="primary", on_click=None).props("unelevated")
                        async def _on_edit_click():
                            edit_save_btn.props("loading")
                            try:
                                await _do_edit_v3(d, detail.get("voucher_no", ""), date_input.value, desc_input.value, _acct_map)
                            finally:
                                edit_save_btn.props(remove="loading")
                        edit_save_btn.on_click(_on_edit_click)
                    else:
                        new_save_btn = ui.button("💾 保存凭证", color="primary", on_click=None).props("unelevated")
                        async def _on_save_click():
                            new_save_btn.props("loading")
                            try:
                                await _do_save_v3(d, date_input=date_input, desc_input=desc_input, save_draft=save_draft, acct_map=_acct_map)
                            finally:
                                new_save_btn.props(remove="loading")
                        new_save_btn.on_click(_on_save_click)

        # ── 底部签章 ──
        with ui.card_section().classes("py-2 px-5 border-t border-grey-100 bg-grey-50 rounded-b-lg"):
            with ui.row().classes("w-full justify-between gap-4 text-xs text-grey-500"):
                maker = state.current_user.get('username', '') if state.current_user else ''
                ui.label(f"制单：{maker}")
                ui.label("审核：__________")
                ui.label("记账：__________")

    d.open()


async def _collect_entries(acct_map):
    """从 JS 收集分录数据并验证。"""
    raw = await ui.run_javascript("return v4collectEntries();")
    try:
        entries_raw = json.loads(raw) if isinstance(raw, str) else json.loads(str(raw))
    except Exception as e:
        show_toast(f"数据收集失败: {e}", "error")
        raise ValueError(str(e)) from e

    entries = []
    total_debit = 0.0
    total_credit = 0.0
    for i, row in enumerate(entries_raw):
        acct_code = row.get("acct_code", "").strip()
        summary = row.get("summary", "").strip()
        debit = float(row.get("debit", 0) or 0)
        credit = float(row.get("credit", 0) or 0)

        if not acct_code:
            if debit == 0 and credit == 0:
                continue
            show_toast(f"第 {i + 1} 行：请选择会计科目", "warning")
            raise ValueError(f"第 {i + 1} 行缺少科目")

        acct_info = acct_map.get(acct_code, {})
        entries.append({
            "account_code": acct_code,
            "account_name": acct_info.get("name", ""),
            "summary": summary,
            "debit": debit,
            "credit": credit,
        })
        total_debit += debit
        total_credit += credit

    if not entries:
        show_toast("请至少填写一条分录", "warning")
        raise ValueError("空分录")

    if len(entries) < 2:
        show_toast("凭证至少需要两行分录", "warning")
        raise ValueError("分录行数不足")

    diff = abs(total_debit - total_credit)
    if diff > 0.01:
        show_toast(f"借贷不平衡，差额 ¥{diff:.2f}", "warning")
        raise ValueError(f"借贷不平衡: {diff}")

    return entries, total_debit, total_credit


async def _do_save_v3(d, date_input, desc_input, save_draft, acct_map):
    try:
        lid = state.selected_ledger_id
        date_str = date_input.value or ""
        desc = desc_input.value or ""
        entries, total_dr, total_cr = await _collect_entries(acct_map)

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
        d.close()
        show_toast(f"✅ 凭证 {vn} 保存成功！", "success")
        refresh_main()
    except Exception as e:
        if "借贷不平衡" not in str(e) and "请选择" not in str(e) and "空分录" not in str(e):
            show_toast(f"❌ 保存失败: {e}", "error")


async def _do_edit_v3(d, voucher_no, date_str, desc, acct_map):
    try:
        entries, total_dr, total_cr = await _collect_entries(acct_map)
        if not date_str:
            show_toast("请填写日期", "warning")
            return

        VoucherService.update(
            voucher_no, date_str=date_str, description=desc,
            entries=[{"account_code": e["account_code"], "account_name": e["account_name"],
                       "summary": e["summary"], "debit": e["debit"], "credit": e["credit"]}
                     for e in entries],
            user_id=state.current_user.get("id") if state.current_user else None,
        )
        d.close()
        show_toast(f"✅ 凭证 {voucher_no} 修改成功！", "success")
        refresh_main()
    except Exception as e:
        if "借贷不平衡" not in str(e) and "请选择" not in str(e) and "空分录" not in str(e):
            show_toast(f"❌ 修改失败: {e}", "error")
