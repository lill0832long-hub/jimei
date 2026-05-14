"""固定资产"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast
from app.components.ui_components import KpiCard, EmptyState, SectionHeader, StatusBadge
from app.services.fixed_asset_service import FixedAssetService


def render_fixed_assets():
    """固定资产 — 资产卡片+折旧计提+处置流程"""
    if not state.selected_ledger_id:
        ledgers = FixedAssetService.get_all(0)  # just to check if we have a ledger
        return

    lid = state.selected_ledger_id

    def _refresh():
        nonlocal assets
        assets = FixedAssetService.get_all(lid) or []
        _build_cards()

    def _build_cards():
        cards_container.clear()
        if not assets:
            with cards_container:
                EmptyState(icon="precision_manufacturing", message="暂无固定资产",
                          hint="点击右上角「新增资产」添加第一张资产卡片",
                          action=_show_add_dialog, action_label="新增资产")
            return
        with cards_container:
            with ui.row().classes("gap-3 flex-wrap"):
                for asset in assets:
                    _render_asset_card(asset)

    def _render_asset_card(asset):
        ov = asset.original_value / 100 if isinstance(asset.original_value, int) else (asset.original_value or 0)
        nv = asset.net_value / 100 if isinstance(asset.net_value, int) else (asset.net_value or 0)
        ad = asset.accumulated_depreciation / 100 if isinstance(asset.accumulated_depreciation, int) else (asset.accumulated_depreciation or 0)
        is_in_use = asset.status == "in_use"

        with ui.card().classes("w-[300px]"):
            # 标题栏 — 状态色彩条
            bar_color = "var(--c-primary)" if is_in_use else "var(--c-text-muted)"
            with ui.element("div").style(f"height:3px; background:{bar_color}; border-radius:12px 12px 0 0;"):
                pass
            with ui.card_section().classes("py-2.5 px-3"):
                with ui.row().classes("items-center justify-between"):
                    with ui.column().classes("gap-0"):
                        ui.label(asset.asset_name or "未命名").classes("text-sm font-semibold").style("color:var(--c-text-primary)")
                        ui.label(asset.asset_code or "").classes("text-xs font-mono").style("color:var(--c-text-muted)")
                    StatusBadge("在用" if is_in_use else "已处置",
                               "approved" if is_in_use else "reversed")

            # 资产信息
            with ui.card_section().classes("py-2 px-3"):
                with ui.column().classes("gap-1"):
                    with ui.row().classes("items-center justify-between"):
                        ui.label("原值").classes("text-xs").style("color:var(--c-text-muted)")
                        ui.label(f"¥{ov:,.2f}").classes("text-xs tabular-nums font-medium").style("color:var(--c-text-primary)")
                    with ui.row().classes("items-center justify-between"):
                        ui.label("累计折旧").classes("text-xs").style("color:var(--c-text-muted)")
                        ui.label(f"¥{ad:,.2f}").classes("text-xs tabular-nums").style("color:var(--c-text-secondary)")
                    with ui.element("div").style("height:1px; background:var(--c-border-light); margin:4px 0;"):
                        pass
                    with ui.row().classes("items-center justify-between"):
                        ui.label("净值").classes("text-xs font-semibold").style("color:var(--c-text-muted)")
                        ui.label(f"¥{nv:,.2f}").classes("text-sm tabular-nums font-bold").style("color:var(--c-success)")
                    with ui.row().classes("items-center justify-between"):
                        ui.label("使用年限").classes("text-xs").style("color:var(--c-text-muted)")
                        ui.label(f"{asset.useful_life_months} 个月").classes("text-xs tabular-nums").style("color:var(--c-text-secondary)")
                    if asset.department:
                        with ui.row().classes("items-center justify-between"):
                            ui.label("使用部门").classes("text-xs").style("color:var(--c-text-muted)")
                            ui.label(asset.department).classes("text-xs").style("color:var(--c-text-secondary)")

            # 操作按钮
            if is_in_use:
                with ui.card_section().classes("py-1.5 px-3 flex gap-1.5 border-t border-grey-1"):
                    ui.button("折旧", icon="calculate", on_click=lambda a=asset: _do_depreciate(a)).props("dense no-caps").classes("text-xs")
                    ui.button("处置", icon="delete_outline", on_click=lambda a=asset: _do_dispose(a)).props("dense no-caps color=negative").classes("text-xs")

    def _do_depreciate(asset):
        try:
            from datetime import datetime as dt
            now = dt.now()
            amount = FixedAssetService.calculate_depreciation(asset.id, now.year, now.month)
            if amount > 0:
                show_toast(f"✅ 折旧计提成功：¥{amount/100:,.2f}", "success")
                _refresh()
            else:
                show_toast("该资产无需计提折旧", "info")
        except Exception as e:
            show_toast(f"❌ 折旧计提失败: {e}", "error")

    def _do_dispose(asset):
        with ui.dialog() as dlg, ui.card().classes("w-[400px]"):
            ui.label("🗑 资产处置").classes("text-lg font-bold mb-3")
            nv = asset.net_value / 100 if isinstance(asset.net_value, int) else (asset.net_value or 0)
            ui.label(f"资产：{asset.asset_name}（{asset.asset_code}）").classes("text-sm")
            ui.label(f"当前净值：¥{nv:,.2f}").classes("text-sm").style("color:var(--c-success)")
            with ui.column().classes("gap-2 mt-3"):
                dispose_type = ui.select(
                    options=["出售", "报废", "捐赠", "盘亏"],
                    value="出售", label="处置方式"
                ).props("outlined dense").classes("w-full")
                proceeds = ui.number(label="处置收入（元）", value=0, format="%.2f").props("outlined dense").classes("w-full")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("取消", on_click=dlg.close)
                ui.button("✅ 确认处置", color="red", on_click=lambda: _confirm_dispose(
                    asset, dlg, dispose_type.value, float(proceeds.value or 0)
                ))
        dlg.open()

    def _confirm_dispose(asset, dlg, dtype, proceeds_yuan):
        try:
            proceeds_fen = int(round(proceeds_yuan * 100))
            result = FixedAssetService.dispose(asset.id, dtype, proceeds_fen)
            if result:
                gl = result.get("gain_loss", 0) / 100
                msg = f"处置完成，{'收益' if gl >= 0 else '损失'}：¥{abs(gl):,.2f}"
                show_toast(f"✅ {msg}", "success")
                dlg.close()
                _refresh()
            else:
                show_toast("资产不存在", "error")
        except Exception as e:
            show_toast(f"❌ 处置失败: {e}", "error")

    def _show_add_dialog():
        with ui.dialog() as dlg, ui.card().classes("w-[450px]"):
            ui.label("➕ 新增固定资产").classes("text-lg font-bold mb-3")
            with ui.column().classes("gap-2"):
                code = ui.input("资产编码", placeholder="如：FA-001").props("outlined dense").classes("w-full")
                name = ui.input("资产名称", placeholder="如：戴尔服务器").props("outlined dense").classes("w-full")
                original_value = ui.number(label="原值（元）", value=0, format="%.2f").props("outlined dense").classes("w-full")
                useful_life = ui.number(label="使用年限（月）", value=36, format="%d").props("outlined dense").classes("w-full")
                residual_rate = ui.number(label="残值率", value=0.05, format="%.4f", step=0.01).props("outlined dense").classes("w-full")
                dept = ui.input("使用部门", placeholder="如：技术部").props("outlined dense").classes("w-full")
                location = ui.input("存放地点", placeholder="如：A栋3楼").props("outlined dense").classes("w-full")
                method = ui.select(
                    options=[{"label": "直线法", "value": "straight_line"},
                             {"label": "双倍余额递减法", "value": "double_declining"},
                             {"label": "年数总和法", "value": "sum_of_years"}],
                    value="straight_line", label="折旧方法"
                ).props("outlined dense").classes("w-full")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("取消", on_click=dlg.close)
                ui.button("✅ 添加", color="green", on_click=lambda: _do_add(
                    dlg, code.value, name.value,
                    float(original_value.value if original_value.value is not None else 0),
                    int(useful_life.value if useful_life.value is not None else 36),
                    float(residual_rate.value if residual_rate.value is not None else 0.05),
                    dept.value, location.value, method.value
                ))
        dlg.open()

    def _do_add(dlg, code, name, ov, life, rr, dept, loc, method):
        if not code or not name:
            show_toast("请填写资产编码和名称", "warning")
            return
        if ov <= 0:
            show_toast("原值必须大于0", "warning")
            return
        try:
            ov_fen = int(round(ov * 100))
            FixedAssetService.create(
                lid, code, name, ov_fen, life,
                residual_rate=rr, department=dept, location=loc,
                depreciation_method=method,
            )
            show_toast(f"✅ 资产 {code} 添加成功", "success")
            dlg.close()
            _refresh()
        except Exception as e:
            show_toast(f"❌ 添加失败: {e}", "error")

    # ── 主界面 ──
    assets = FixedAssetService.get_all(lid) or []

    # KPI 概览行
    total_count = len(assets)
    in_use_count = sum(1 for a in assets if a.status == "in_use")
    total_ov = sum((a.original_value or 0) / 100 for a in assets)
    total_nv = sum((a.net_value or 0) / 100 for a in assets)
    total_ad = sum((a.accumulated_depreciation or 0) / 100 for a in assets)

    with ui.row().classes("w-full gap-3"):
        KpiCard("资产总数", str(total_count), "precision_manufacturing", "blue")
        KpiCard("在用资产", str(in_use_count), "check_circle", "green")
        KpiCard("资产原值", f"¥{total_ov:,.0f}", "account_balance", "purple")
        KpiCard("累计折旧", f"¥{total_ad:,.0f}", "trending_down", "orange")
        KpiCard("资产净值", f"¥{total_nv:,.0f}", "savings", "teal")

    # 资产卡片列表
    with ui.card().classes("w-full mt-3"):
        SectionHeader("资产列表", icon="inventory_2", action=_show_add_dialog, action_icon="新增资产", action_color="positive")
        cards_container = ui.card().classes("w-full")
        _build_cards()
