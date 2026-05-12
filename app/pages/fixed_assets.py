"""固定资产"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast
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
                with ui.card_section().classes("py-12 text-center"):
                    ui.icon("precision_manufacturing").style("font-size: 48px; color: var(--gray-300)")
                    ui.label("暂无固定资产").classes("text-lg font-semibold mt-4").style("color:var(--c-text-muted)")
                    ui.label("点击「新增资产」添加").classes("text-sm mt-2").style("color:var(--c-text-muted)")
            return
        with cards_container:
            with ui.row().classes("gap-3 flex-wrap"):
                for asset in assets:
                    _render_asset_card(asset)

    def _render_asset_card(asset):
        with ui.card().classes("w-[300px] shadow-sm"):
            # 标题栏
            status_color = "bg-blue-50" if asset.status == "in_use" else "bg-grey-100"
            status_label = "在用" if asset.status == "in_use" else "已处置"
            with ui.card_section().classes(f"py-2 px-3 {status_color}"):
                with ui.row().classes("items-center justify-between"):
                    ui.label(asset.asset_name or "未命名").classes("text-sm font-bold")
                    ui.label(status_label).classes("text-xs px-2 py-0.5 rounded").style(
                        "background:#4caf50;color:white" if asset.status == "in_use" else "background:#9e9e9e;color=white"
                    )

            # 资产信息
            ov = asset.original_value / 100 if isinstance(asset.original_value, int) else (asset.original_value or 0)
            nv = asset.net_value / 100 if isinstance(asset.net_value, int) else (asset.net_value or 0)
            ad = asset.accumulated_depreciation / 100 if isinstance(asset.accumulated_depreciation, int) else (asset.accumulated_depreciation or 0)
            with ui.card_section().classes("py-1.5 px-3"):
                with ui.column().classes("gap-0.5 text-xs").style("color:var(--c-text-secondary)"):
                    ui.label(f"编码：{asset.asset_code}").classes("font-mono")
                    ui.label(f"原值：¥{ov:,.2f}")
                    ui.label(f"累计折旧：¥{ad:,.2f}")
                    ui.label(f"净值：¥{nv:,.2f}").classes("font-bold").style("color:var(--c-success)")
                    ui.label(f"使用年限：{asset.useful_life_months}个月")
                    if asset.department:
                        ui.label(f"使用部门：{asset.department}")

            # 操作按钮
            if asset.status == "in_use":
                with ui.card_section().classes("py-1 px-3 flex gap-1"):
                    ui.button("📊 折旧", color="blue",
                              on_click=lambda a=asset: _do_depreciate(a)).props("dense").classes("text-xs")
                    ui.button("🗑 处置", color="red",
                              on_click=lambda a=asset: _do_dispose(a)).props("dense").classes("text-xs")

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
                    dlg, code.value, name.value, float(original_value.value or 0),
                    int(useful_life.value or 36), float(residual_rate.value or 0.05),
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

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            with ui.row().classes("items-center justify-between"):
                ui.label("🏭 固定资产").classes("text-base font-bold")
                ui.button("➕ 新增资产", color="green", on_click=_show_add_dialog).props("dense")

        cards_container = ui.card().classes("w-full")
        _build_cards()
