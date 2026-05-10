"""报表 — 科目余额表"""
from nicegui import ui
from app.components.state import state
from database_v3 import get_ledgers, get_account_balances


def render_accounts():
    """科目余额表 — ui.table 严格列对齐，金额等宽，借贷分色"""
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return
    balances = get_account_balances(lid, state.selected_year, state.selected_month)

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            ui.label(f"📊 科目余额表 — {state.selected_year}年{state.selected_month}月").classes("text-base font-bold")

        if not balances:
            with ui.card_section().classes("py-12"):
                ui.label("暂无数据").classes("text-sm text-center").style("color:var(--c-text-muted)")
            return

        # 构建行数据
        total = dict.fromkeys(["od","oc","cd","cc","yd","yc","ed","ec"], 0)
        rows = []
        for b in balances:
            od = b.get("opening_dr") or 0; oc = b.get("opening_cr") or 0
            cd = b.get("curr_dr") or 0;  cc = b.get("curr_cr") or 0
            yd = b.get("ytd_dr") or 0;   yc = b.get("ytd_cr") or 0
            ed = b.get("closing_dr") or 0; ec = b.get("closing_cr") or 0
            is_t = b["name"] == "合计"
            if not is_t:
                for k,v in [("od",od),("oc",oc),("cd",cd),("cc",cc),("yd",yd),("yc",yc),("ed",ed),("ec",ec)]:
                    total[k] += v
            rows.append({
                "code": b.get("code",""), "name": b["name"],
                "od": od, "oc": oc, "cd": cd, "cc": cc,
                "yd": yd, "yc": yc, "ed": ed, "ec": ec,
                "level": b.get("level",0), "is_total": is_t,
            })

        # 合计行
        rows.append({
            "code": "", "name": "合 计",
            "od": total["od"], "oc": total["oc"], "cd": total["cd"], "cc": total["cc"],
            "yd": total["yd"], "yc": total["yc"], "ed": total["ed"], "ec": total["ec"],
            "level": 0, "is_total": True,
        })

        HC = "table-header-cell text-uppercase"
        cols = [
            {"name":"code","label":"科目编码","field":"code","align":"left","headerClasses":HC,"classes":"text-xs font-mono","style":"width:96px"},
            {"name":"name","label":"科目名称","field":"name","align":"left","headerClasses":HC,"classes":"text-sm","style":"min-width:140px"},
            {"name":"od","label":"期初借方","field":"od","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":"width:112px"},
            {"name":"oc","label":"期初贷方","field":"oc","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":"width:112px"},
            {"name":"cd","label":"本期借方","field":"cd","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":"width:112px"},
            {"name":"cc","label":"本期贷方","field":"cc","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":"width:112px"},
            {"name":"yd","label":"累计借方","field":"yd","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":"width:112px"},
            {"name":"yc","label":"累计贷方","field":"yc","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":"width:112px"},
            {"name":"ed","label":"期末借方","field":"ed","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":"width:112px"},
            {"name":"ec","label":"期末贷方","field":"ec","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":"width:112px"},
        ]

        tbl = ui.table(columns=cols, rows=rows, row_key="name", pagination={"rowsPerPage":50}).classes("w-full")

        # 借方列 slot（绿色）
        for col in ["od","cd","yd","ed"]:
            tbl.add_slot(f"body-cell-{col}", r"""
                <q-td :props="props" class="tabular-nums text-sm"
                       :style="props.row.is_total ? 'background:var(--c-bg-hover);font-weight:700;' : (props.row.level===2 ? 'padding-left:24px;' : '')">
                    <span :class="props.row.is_total ? 'font-bold' : 'font-bold'">
                        {{ props.row[""" + col + r"""] ? '¥' + props.row[""" + col + r"""].toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                    </span>
                </q-td>
            """)

        # 贷方列 slot（红色）
        for col in ["oc","cc","yc","ec"]:
            tbl.add_slot(f"body-cell-{col}", r"""
                <q-td :props="props" class="tabular-nums text-sm"
                       :style="props.row.is_total ? 'background:var(--c-bg-hover);font-weight:700;' : (props.row.level===2 ? 'padding-left:24px;' : '')">
                    <span :class="props.row.is_total ? 'font-bold' : 'font-bold'">
                        {{ props.row[""" + col + r"""] ? '¥' + props.row[""" + col + r"""].toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                    </span>
                </q-td>
            """)

        tbl.add_slot("body-cell-name", r"""
            <q-td :props="props"
                   :style="props.row.is_total ? 'background:var(--c-bg-hover);font-weight:700;' : ''">
                <span :class="props.row.is_total ? 'font-bold text-base' : (props.row.level === 2 ? 'pl-4 text-sm text-grey-6' : 'text-sm text-secondary')">
                    {{ props.row.name }}
                </span>
            </q-td>
        """)

        # 借贷平衡校验
        with ui.card_section().classes("py-2.5 px-4 bg-grey-50 border-t border-grey-2"):
            with ui.row().classes("justify-center gap-8 items-center text-sm"):
                ui.label("本期借方合计").style("color:var(--c-text-muted)")
                ui.label(f"¥{total['cd']:,.2f}").classes("font-bold tabular-nums").style("color:var(--c-success)")
                ui.label("本期贷方合计").classes("ml-4").style("color:var(--c-text-muted)")
                ui.label(f"¥{total['cc']:,.2f}").classes("font-bold tabular-nums").style("color:var(--c-danger)")
                if abs(total['cd'] - total['cc']) < 0.01:
                    ui.label("✅ 借贷平衡").classes("font-bold ml-4").style("color:var(--c-success)")
                else:
                    ui.label(f"❌ 差额 ¥{abs(total['cd']-total['cc']):,.2f}").classes("font-bold tabular-nums ml-4").style("color:var(--c-danger)")
