"""凭证表单 v5 — 传统记账凭证格式（仿照标准会计凭证）"""
import html as html_mod
import json

from nicegui import ui

from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from app.services import AccountService, LedgerService, VoucherService


def _generate_voucher_no(lid, voucher_type="记"):
    """生成凭证号 — 用 SQL 直接查最大序号，避免全量加载"""
    from database.connection import get_conn, release_conn
    prefix = f"PZ{lid:02d}"
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(voucher_no, ?) AS INTEGER)) as max_seq "
            "FROM vouchers WHERE ledger_id = ? AND voucher_no LIKE ?",
            (len(prefix) + 1, lid, f"{prefix}%")
        ).fetchone()
        max_seq = row["max_seq"] or 0 if row else 0
        return f"{prefix}{max_seq + 1:06d}"
    except Exception:
        return f"{prefix}000001"
    finally:
        try:
            release_conn(conn)
        except Exception:
            pass


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


# ─── 交互 JS ───
_VC_JS = '''
<script>
if (!window.v5init) {
    window.v5init = true;

    window.v5calcTotals = function() {
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
            balEl.textContent = diff < 0.01 ? '借贷平衡' : '差额 ¥' + diff.toFixed(2);
            balEl.className = diff < 0.01 ? 'vc-balance-ok' : 'vc-balance-bad';
        }
    };

    window.v5delRow = function(btn) {
        var row = btn.closest('tr');
        var tbody = row.closest('tbody');
        if (tbody && tbody.querySelectorAll('tr').length > 1) {
            row.remove();
            v5calcTotals();
        }
    };

    window.v5addRow = function(acctOpts) {
        var tbody = document.getElementById('vcBody');
        if (!tbody) return;
        var idx = tbody.querySelectorAll('tr').length;
        var tr = document.createElement('tr');
        tr.innerHTML =
            '<td class="vctd vctd-seq">' + (idx+1) + '</td>'
            + '<td class="vctd vctd-summary"><input type="text" class="vctd-inp" name="r' + idx + '_summ" placeholder="摘要" /></td>'
            + '<td class="vctd vctd-acct"><select class="vctd-sel" name="r' + idx + '_acct">' + acctOpts + '</select></td>'
            + '<td class="vctd vctd-debit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_dr" placeholder="0.00" step="0.01" min="0" /></td>'
            + '<td class="vctd vctd-credit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_cr" placeholder="0.00" step="0.01" min="0" /></td>'
            + '<td class="vctd vctd-op"><button type="button" class="vctd-del-btn" onclick="v5delRow(this)">&times;</button></td>';
        tbody.appendChild(tr);
        tr.querySelectorAll('.vctd-num').forEach(function(inp) {
            inp.addEventListener('input', v5calcTotals);
        });
        v5calcTotals();
    };

    window.v5rebuildTable = function(acctOpts, entries) {
        var tbody = document.getElementById('vcBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        entries.forEach(function(e, idx) {
            var sel = acctOpts.replace('value="' + e.acct_code + '"', 'value="' + e.acct_code + '" selected');
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td class="vctd vctd-seq">' + (idx+1) + '</td>'
                + '<td class="vctd vctd-summary"><input type="text" class="vctd-inp" name="r' + idx + '_summ" value="' + (e.summary || '') + '" placeholder="摘要" /></td>'
                + '<td class="vctd vctd-acct"><select class="vctd-sel" name="r' + idx + '_acct">' + sel + '</select></td>'
                + '<td class="vctd vctd-debit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_dr" value="' + (e.debit || '') + '" placeholder="0.00" step="0.01" min="0" /></td>'
                + '<td class="vctd vctd-credit"><input type="number" class="vctd-inp vctd-num" name="r' + idx + '_cr" value="' + (e.credit || '') + '" placeholder="0.00" step="0.01" min="0" /></td>'
                + '<td class="vctd vctd-op"><button type="button" class="vctd-del-btn" onclick="v5delRow(this)">&times;</button></td>';
            tbody.appendChild(tr);
            tr.querySelectorAll('.vctd-num').forEach(function(inp) {
                inp.addEventListener('input', v5calcTotals);
            });
        });
        v5calcTotals();
    };

    window.v5collectEntries = function() {
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
    """凭证表单 v5 — 传统记账凭证格式"""
    ui.add_body_html(_VC_JS, shared=True)
    d = ui.dialog()
    is_edit = detail is not None

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

    # 科目选项 HTML
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

    # 凭证数据
    vtype_opts = {"记": "记", "收": "收", "付": "付"}
    default_vtype = detail.get("voucher_type", "记") if is_edit else "记"
    default_date = detail.get("date", "") if is_edit else ""
    default_desc = detail.get("description", "") if is_edit else ""
    vn = detail.get("voucher_no", "") if is_edit else _generate_voucher_no(state.selected_ledger_id)
    attach_count = detail.get("attach_count", 0) if is_edit else 0

    # 构建分录表格行
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

    # ── 渲染对话框 ──
    with d, ui.card().classes("vcdialog"):
        # ── 凭证头部（标题 + 凭证字/号/日期）──
        with ui.card_section().classes("vcheader").style("text-align:center;padding:12px 16px 10px;border-bottom:2px solid #1a1a1a"):
            # 大标题
            ui.label("记 账 凭 证").style("font-size:22px;font-weight:900;letter-spacing:8px;color:#1a1a1a;margin-bottom:6px")
            # 第二行：凭证字 + 凭证号 + 日期
            with ui.row().classes("w-full items-center justify-between"):
                # 凭证字
                with ui.row().classes("items-center gap-2"):
                    ui.label("凭证字：").style("font-size:13px;color:#333")
                    vtype_sel = ui.select(vtype_opts, value=default_vtype).props("outlined dense").classes("vctype-sel")
                # 凭证号
                ui.label(f"No. {vn}").style("font-size:14px;font-weight:700;font-family:Consolas,monospace;color:#1a1a1a")
                # 日期
                with ui.row().classes("items-center gap-2"):
                    ui.label("日期：").style("font-size:13px;color:#333")
                    date_input = ui.input(value=default_date).props("type=date outlined dense").classes("vcdate-inp")

        # ── 摘要 + 附件 ──
        with ui.card_section().classes("vcsection-meta").style("padding:8px 16px;border-bottom:1px solid #1a1a1a;display:flex;justify-content:space-between;align-items:center"):
            with ui.row().classes("items-center gap-2"):
                ui.label("摘要：").style("font-size:13px;font-weight:600;color:#1a1a1a")
                desc_input = ui.input(value=default_desc, placeholder="请输入凭证摘要...").props("outlined dense").classes("vcsummary-inp")
            with ui.row().classes("items-center gap-2"):
                ui.label("附件：").style("font-size:13px;color:#333")
                attach_input = ui.number(value=attach_count, precision=0).props("outlined dense").classes("vcattach-inp")
                ui.label("张").style("font-size:13px;color:#333")

        # ── 凭证模板（仅新增时显示）──
        if not is_edit:
            try:
                _templates = VoucherService.get_templates(state.selected_ledger_id) if state.selected_ledger_id else []
            except Exception:
                _templates = []
            if _templates:
                with ui.card_section().classes("vcsection-tpl").style("padding:6px 16px;background:#FFFBEB;border-bottom:1px solid #FDE68A;display:flex;align-items:center;gap:8px"):
                    ui.icon("description", size="sm").style("color:#D97706")
                    ui.label("模板").style("font-size:12px;font-weight:600;color:#D97706")
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
                            # 写入 hidden input 存储数据，由客户端 JS 监听并重建表格
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
            # 注入 JS：绑定 input 事件 + 初始计算（通过 script 标签而非 run_javascript，避免 event loop 依赖）
            ui.add_head_html(f"""
            <script>
            (function() {{
                function initV5Table() {{
                    if (!document.getElementById('vcBody')) {{
                        setTimeout(initV5Table, 100);
                        return;
                    }}
                    document.querySelectorAll('#vcBody .vctd-num').forEach(function(inp) {{
                        inp.addEventListener('input', v5calcTotals);
                    }});
                    v5calcTotals();
                }}
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initV5Table);
                }} else {{
                    setTimeout(initV5Table, 50);
                }}
            }})();
            </script>
            """)

        # ── 底部签章 ──
        with ui.card_section().classes("vcsection-footer").style("padding:10px 16px;border-top:1px solid #1a1a1a;display:flex;justify-content:space-between;align-items:center"):
            with ui.row().classes("gap-6"):
                maker = state.current_user.get('username', '') if state.current_user else ''
                ui.label(f"制单人：{maker}").style("font-size:12px;color:#666")
                ui.label("审核人：").style("font-size:12px;color:#666")
                ui.label("记账人：").style("font-size:12px;color:#666")
                ui.label("出纳人：").style("font-size:12px;color:#666")
            with ui.row().classes("gap-2"):
                ui.button("🖨️ 打印", on_click=lambda: ui.run_javascript("window.print();")).props("dense").style("font-size:12px")
                ui.button("取消", on_click=d.close).props("flat").style("font-size:12px")

        # ── 保存按钮（底部独立区域）──
        with ui.card_section().classes("vcsection-save").style("padding:12px 16px;text-align:right;border-top:1px solid #e5e7eb"):
            if not is_edit:
                save_draft = ui.checkbox("存为草稿", value=False).classes("text-xs mr-4")
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

    d.open()


async def _collect_entries(acct_map):
    """从 JS 收集分录数据并验证"""
    raw = await ui.run_javascript("return v5collectEntries();")
    # Handle undefined/null — JS function may not be loaded yet
    if raw is None or raw == "undefined" or raw == "null":
        show_toast("凭证表格尚未加载完成，请稍后重试", "warning")
        raise ValueError("表格未加载")
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
