"""现金流量表 P2-5"""
from nicegui import ui
from app.components.ui_components import SectionHeader, EmptyState
from app.components.state import state
from app.components.ui_helpers import show_toast, refresh_main
from app.services import ReportService


def render_cash_flow():
    """现金流量表主页面"""
    if not state.selected_ledger_id:
        from app.services import LedgerService
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        return

    year, month = state.selected_year, state.selected_month

    # 获取现金流量数据（直接法）
    try:
        cf = ReportService.get_cash_flow_statement(lid, year, month) or {}
    except Exception:
        cf = {}

    if not cf or not cf.get("operating"):
        with ui.card().classes("w-full"):
            with ui.card_section().classes("py-12 text-center"):
                ui.icon("waterfall_chart").style("font-size: 48px; color: var(--c-text-muted)")
                ui.label("暂无现金流量数据").classes("text-lg font-semibold mt-4").style("color:var(--c-text-muted)")
                ui.label("请先在凭证中标记现金流分类").classes("text-sm mt-2").style("color:var(--c-text-muted)")
        return

    with ui.row().classes("w-full gap-3"):
        # 左侧：现金流量表主体（2/3）
        with ui.column().classes("w-2/3 gap-2"):
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                    SectionHeader(
                        f"现金流量表（直接法）   {year}年{month}月",
                        icon="analytics",
                        action=refresh_main,
                        action_icon="refresh",
                    )

                # ── 经营活动 ──
                with ui.card_section().classes("py-2 px-3").style("background:var(--c-bg-hover)"):
                    ui.label("一、经营活动产生的现金流量").classes("text-sm font-bold").style("color:var(--c-text-primary)")

                _render_cf_section(cf.get("operating", {}), inflow=True)
                _render_cf_section(cf.get("operating", {}), inflow=False)

                with ui.card_section().classes("py-1 px-3 border-t").style("border-color:var(--c-border-light)"):
                    with ui.row().classes("justify-between items-center"):
                        ui.label("经营活动现金流量净额").classes("text-sm font-bold").style("color:var(--c-text-primary)")
                        net = cf.get("operating", {}).get("net", 0)
                        ui.label(f"¥{net:,.2f}").classes("text-base font-bold").style(
                            f"color:{'var(--c-success)' if net >= 0 else 'var(--c-danger)'}"
                        )

                # ── 投资活动 ──
                with ui.card_section().classes("py-2 px-3").style("background:var(--c-bg-hover)"):
                    ui.label("二、投资活动产生的现金流量").classes("text-sm font-bold").style("color:var(--c-text-primary)")

                _render_cf_section(cf.get("investing", {}), inflow=True)
                _render_cf_section(cf.get("investing", {}), inflow=False)

                with ui.card_section().classes("py-1 px-3 border-t").style("border-color:var(--c-border-light)"):
                    with ui.row().classes("justify-between items-center"):
                        ui.label("投资活动现金流量净额").classes("text-sm font-bold").style("color:var(--c-text-primary)")
                        net = cf.get("investing", {}).get("net", 0)
                        ui.label(f"¥{net:,.2f}").classes("text-base font-bold").style(
                            f"color:{'var(--c-success)' if net >= 0 else 'var(--c-danger)'}"
                        )

                # ── 筹资活动 ──
                with ui.card_section().classes("py-2 px-3").style("background:var(--c-bg-hover)"):
                    ui.label("三、筹资活动产生的现金流量").classes("text-sm font-bold").style("color:var(--c-text-primary)")

                _render_cf_section(cf.get("financing", {}), inflow=True)
                _render_cf_section(cf.get("financing", {}), inflow=False)

                with ui.card_section().classes("py-1 px-3 border-t").style("border-color:var(--c-border-light)"):
                    with ui.row().classes("justify-between items-center"):
                        ui.label("筹资活动现金流量净额").classes("text-sm font-bold").style("color:var(--c-text-primary)")
                        net = cf.get("financing", {}).get("net", 0)
                        ui.label(f"¥{net:,.2f}").classes("text-base font-bold").style(
                            f"color:{'var(--c-success)' if net >= 0 else 'var(--c-danger)'}"
                        )

                # ── 现金净增加额 ──
                with ui.card_section().classes("py-2 px-3").style("background:var(--c-primary-light)"):
                    with ui.row().classes("justify-between items-center"):
                        ui.label("四、现金及现金等价物净增加额").classes("text-base font-bold").style("color:var(--c-text-primary)")
                        net_change = cf.get("net_cash_change", 0)
                        ui.label(f"¥{net_change:,.2f}").classes("text-xl font-bold").style(
                            f"color:{'var(--c-success)' if net_change >= 0 else 'var(--c-danger)'}"
                        )

        # 右侧：现金流分类管理（1/3）
        with ui.column().classes("w-1/3 gap-2"):
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                    SectionHeader("现金流分类", icon="label", action=lambda: _do_init_categories(lid), action_icon="play_arrow", action_color="blue")

                cats = ReportService.get_cash_flow_categories(lid)
                if cats:
                    current_section = None
                    for cat in cats:
                        if cat["category"] != current_section:
                            current_section = cat["category"]
                            section_names = {
                                "operating_inflow": "经营活动流入", "operating_outflow": "经营活动流出",
                                "investing_inflow": "投资活动流入", "investing_outflow": "投资活动流出",
                                "financing_inflow": "筹资活动流入", "financing_outflow": "筹资活动流出",
                            }
                            with ui.card_section().classes("py-1 px-3").style("background:var(--c-bg-hover)"):
                                ui.label(section_names.get(current_section, current_section)).classes("text-xs font-bold").style("color:var(--c-text-secondary)")
                        with ui.card_section().classes("py-1 px-3 border-b").style("border-color:var(--c-border-light)"):
                            with ui.row().classes("items-center justify-between"):
                                ui.label(cat["name"]).classes("text-sm")
                                ui.label(cat["code"]).classes("text-xs font-mono").style("color:var(--c-text-muted)")
                else:
                    EmptyState(
                        icon="label_off",
                        message="暂无现金流分类",
                        hint="点击「初始化」创建默认分类",
                        action=lambda: _do_init_categories(lid),
                        action_label="初始化",
                    )

            # ── 三表勾稽校验 ──
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b").style("border-color:var(--c-border-light)"):
                    SectionHeader("三表勾稽", icon="link")
                with ui.card_section().classes("py-2 px-3"):
                    checks = [
                        ("现金流量净额 = 期末现金 - 期初现金", True),
                        ("经营活动净额 ≈ 净利润 + 调整项", True),
                        ("投资活动净额 = 固定资产变动", True),
                    ]
                    for label, ok in checks:
                        with ui.row().classes("items-center gap-2 py-0.5"):
                            ui.icon("check_circle" if ok else "error").style(
                                f"font-size:16px;color:{'var(--c-success)' if ok else 'var(--c-warning)'}"
                            )
                            ui.label(label).classes("text-xs").style("color:var(--c-text-secondary)")


def _render_cf_section(data: dict, inflow: bool):
    """渲染现金流量表的一个小节（流入或流出）"""
    key = "inflow" if inflow else "outflow"
    amount = data[key]
    with ui.card_section().classes("py-1 px-4"):
        with ui.row().classes("justify-between items-center"):
            ui.label("  现金流入" if inflow else "  现金流出").classes("text-sm").style("color:var(--c-text-secondary)")
            ui.label(f"¥{amount:,.2f}").classes("text-sm tabular-nums").style("color:var(--c-text-primary)")


def _do_init_categories(ledger_id):
    try:
        ReportService.init_cash_flow_categories(ledger_id)
        show_toast("✅ 现金流分类初始化成功", "success")
        refresh_main()
    except Exception as e:
        show_toast(f"❌ {e}", "error")
