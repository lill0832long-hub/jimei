"""报表 — 资产负债表"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import refresh_main
from app.services import LedgerService, ReportService
from app.pages.reports_export import _export_balance_sheet, _export_balance_sheet_pdf


def render_balance_sheet():
    """资产负债表 — 左右两栏 ui.table，严格列对齐，同比/环比增强"""
    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    # ── 期间选择器 ──
    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2 px-4 border-b border-grey-2").style("color:var(--c-bg-hover)"):
            with ui.row().classes("items-center gap-3"):
                ui.label("📗 资产负债表").classes("text-base font-bold")
                ui.separator().props("vertical")
                year_sel = ui.select(
                    options=list(range(2020, 2031)),
                    value=state.selected_year,
                    label="年度"
                ).props("dense outlined").classes("w-28")
                month_sel = ui.select(
                    options=list(range(1, 13)),
                    value=state.selected_month,
                    label="月份"
                ).props("dense outlined").classes("w-24")
                ui.separator().props("vertical")
                ui.button("📥 导出Excel", color="green", on_click=lambda: _export_balance_sheet()) \
                    .props("dense").classes("text-xs")
                ui.button("📄 导出PDF", color="blue", on_click=lambda: _export_balance_sheet_pdf()) \
                    .props("dense").classes("text-xs")
                ui.separator().props("vertical")
                compare_mode = ui.toggle(
                    options={"mom": "环比", "yoy": "同比"},
                    value="mom"
                ).props("dense").classes("text-xs")

                def _on_period_change():
                    state.selected_year = year_sel.value
                    state.selected_month = month_sel.value
                    refresh_main()

                year_sel.on("update:value", lambda e: _on_period_change())
                month_sel.on("update:value", lambda e: _on_period_change())

    bs = ReportService.get_balance_sheet(lid, state.selected_year, state.selected_month)

    # 获取对比期间数据
    if compare_mode.value == "mom":
        prev_month = state.selected_month - 1
        prev_year = state.selected_year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1
        label_prev = f"{prev_year}年{prev_month}月"
    else:
        prev_year = state.selected_year - 1
        prev_month = state.selected_month
        label_prev = f"{prev_year}年{prev_month}月"
    bs_prev = ReportService.get_balance_sheet(lid, prev_year, prev_month)

    HC = "table-header-cell text-uppercase"
    num_style = "width:120px"

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            ui.label(f"📗 资产负债表 — {bs['date']}").classes("text-base font-bold")

        with ui.row().classes("w-full gap-0"):
            # 左栏：资产
            with ui.column().classes("w-1/2 pr-4"):
                with ui.card_section().classes("py-2 px-3 bg-green-50"):
                    ui.label("资 产").classes("text-sm font-bold text-center uppercase tracking-widest") \
                        .style("color:var(--c-success)")
                prev_assets = {r["name"]: r.get("end", 0) for r in bs_prev["assets"]}
                rows_a = []
                for r in bs["assets"]:
                    prev_val = prev_assets.get(r["name"], 0)
                    end_val = r.get("end", 0)
                    change_pct = ((end_val - prev_val) / abs(prev_val) * 100) if prev_val else None
                    rows_a.append({
                        "name": r["name"], "code": r.get("code", "") or "",
                        "end": end_val, "open": r.get("open", 0),
                        "prev": prev_val, "change": change_pct,
                        "level": r.get("level", 0)
                    })
                cols_a = [
                    {"name":"name","label":"项 目","field":"name","align":"left","headerClasses":HC,"classes":"text-sm","style":"min-width:120px"},
                    {"name":"code","label":"行次","field":"code","align":"center","headerClasses":HC,"classes":"text-xs font-mono","style":"width:48px"},
                    {"name":"end","label":"期末数","field":"end","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":num_style},
                    {"name":"open","label":"年初数","field":"open","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":num_style},
                    {"name":"prev","label":f"对比({label_prev})","field":"prev","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":num_style},
                    {"name":"change","label":"变化率","field":"change","align":"right","headerClasses":HC,"classes":"tabular-nums text-xs","style":"width:72px"},
                ]
                tbl_a = ui.table(columns=cols_a, rows=rows_a, row_key="name", pagination=False).classes("w-full")
                tbl_a.add_slot("body-cell-name", r"""
                    <q-td :props="props"
                           :style="props.row.level===0 ? 'background:var(--c-success-light);font-weight:700;' : (props.row.level===2 ? 'padding-left:20px;' : '')">
                        <span :class="props.row.level===0 ? 'font-bold text-success' : (props.row.level===2 ? 'text-sm text-secondary' : 'text-sm text-secondary')">
                            {{ props.row.name }}
                        </span>
                    </q-td>
                """)
                for col in ["end","open","prev"]:
                    tbl_a.add_slot(f"body-cell-{col}", r"""
                        <q-td :props="props" class="tabular-nums text-sm"
                               :style="props.row.level===0 ? 'background:var(--c-success-light);font-weight:700;' : ''">
                            <span :class="props.row.level===0 ? 'font-bold text-success' : 'text-primary'">
                                {{ props.row[""" + col + r"""] !== null ? '¥' + props.row[""" + col + r"""].toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                            </span>
                        </q-td>
                    """)
                tbl_a.add_slot("body-cell-change", r"""
                    <q-td :props="props" class="tabular-nums text-xs"
                           :style="props.row.level===0 ? 'background:var(--c-success-light);font-weight:700;' : ''">
                        <span v-if="props.row.change !== null"
                              :class="props.row.change > 0 ? 'num-positive' : (props.row.change < 0 ? 'num-negative' : 'text-muted')">
                            {{ props.row.change > 0 ? '▲' : (props.row.change < 0 ? '▼' : '—') }}
                            {{ Math.abs(props.row.change).toFixed(1) }}%
                        </span>
                        <span v-else class="text-muted">—</span>
                    </q-td>
                """)

            # 右栏：负债+权益
            with ui.column().classes("w-1/2 pl-4"):
                with ui.card_section().classes("py-2 px-3 bg-blue-50"):
                    ui.label("负债和所有者权益").classes("text-sm font-bold text-center uppercase tracking-widest") \
                        .style("color:var(--c-primary)")
                prev_le = {r["name"]: r.get("end", 0) for r in bs_prev["liabilities"] + bs_prev["equity"]}
                rows_l = []
                for r in bs["liabilities"] + bs["equity"]:
                    prev_val = prev_le.get(r["name"], 0)
                    end_val = r.get("end", 0)
                    change_pct = ((end_val - prev_val) / abs(prev_val) * 100) if prev_val else None
                    rows_l.append({
                        "name": r["name"], "code": r.get("code", "") or "",
                        "end": end_val, "open": r.get("open", 0),
                        "prev": prev_val, "change": change_pct,
                        "level": r.get("level", 0)
                    })
                cols_l = [
                    {"name":"name","label":"项 目","field":"name","align":"left","headerClasses":HC,"classes":"text-sm","style":"min-width:120px"},
                    {"name":"code","label":"行次","field":"code","align":"center","headerClasses":HC,"classes":"text-xs font-mono","style":"width:48px"},
                    {"name":"end","label":"期末数","field":"end","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":num_style},
                    {"name":"open","label":"年初数","field":"open","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":num_style},
                    {"name":"prev","label":f"对比({label_prev})","field":"prev","align":"right","headerClasses":HC,"classes":"tabular-nums text-sm","style":num_style},
                    {"name":"change","label":"变化率","field":"change","align":"right","headerClasses":HC,"classes":"tabular-nums text-xs","style":"width:72px"},
                ]
                tbl_l = ui.table(columns=cols_l, rows=rows_l, row_key="name", pagination=False).classes("w-full")
                tbl_l.add_slot("body-cell-name", r"""
                    <q-td :props="props"
                           :style="props.row.level===0 ? 'background:var(--c-primary-light);font-weight:700;' : (props.row.level===2 ? 'padding-left:20px;' : '')">
                        <span :class="props.row.level===0 ? 'font-bold text-primary' : (props.row.level===2 ? 'text-sm text-secondary' : 'text-sm text-secondary')">
                            {{ props.row.name }}
                        </span>
                    </q-td>
                """)
                for col in ["end","open","prev"]:
                    tbl_l.add_slot(f"body-cell-{col}", r"""
                        <q-td :props="props" class="tabular-nums text-sm"
                               :style="props.row.level===0 ? 'background:var(--c-primary-light);font-weight:700;' : ''">
                            <span :class="props.row.level===0 ? 'font-bold text-primary' : 'text-primary'">
                                {{ props.row[""" + col + r"""] !== null ? '¥' + props.row[""" + col + r"""].toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—' }}
                            </span>
                        </q-td>
                    """)
                tbl_l.add_slot("body-cell-change", r"""
                    <q-td :props="props" class="tabular-nums text-xs"
                           :style="props.row.level===0 ? 'background:var(--c-primary-light);font-weight:700;' : ''">
                        <span v-if="props.row.change !== null"
                              :class="props.row.change > 0 ? 'num-positive' : (props.row.change < 0 ? 'num-negative' : 'text-muted')">
                            {{ props.row.change > 0 ? '▲' : (props.row.change < 0 ? '▼' : '—') }}
                            {{ Math.abs(props.row.change).toFixed(1) }}%
                        </span>
                        <span v-else class="text-muted">—</span>
                    </q-td>
                """)

        # 平衡校验
        with ui.card_section().classes("py-3 px-4 bg-grey-50 border-t border-grey-2"):
            ta, tl, te = bs["total_assets"], bs["total_liab"], bs["total_equity"]
            diff = abs(ta - (tl + te))
            with ui.row().classes("justify-center gap-4 items-center text-sm"):
                for lbl, val, clr in [("资产总计",ta,"text-success"),("负债合计",tl,"text-danger"),("所有者权益",te,"text-primary")]:
                    ui.label(lbl).style("color:var(--c-text-muted)")
                    ui.label(f"¥{val:,.2f}").classes(f"{clr} font-bold tabular-nums text-base")
                if diff < 0.01:
                    ui.label("✅ 平衡").classes("font-bold ml-2").style("color:var(--c-success)")
                else:
                    ui.label(f"❌ 差额 ¥{diff:,.2f}").classes("font-bold tabular-nums ml-2").style("color:var(--c-danger)")
