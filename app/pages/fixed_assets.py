"""固定资产"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast

def render_fixed_assets():
    """固定资产 — 资产卡片+折旧曲线+折旧方法+处置流程"""
    assets = []  # TODO: 从数据库获取

    with ui.card().classes("w-full"):
        with ui.card_section().classes("py-2.5 px-4 border-b border-grey-2"):
            with ui.row().classes("items-center justify-between"):
                ui.label("🏭 固定资产").classes("text-base font-bold")
                ui.button("➕ 新增资产", color="green", on_click=lambda: show_toast("新增资产功能", "info")).props("dense")

        # 折旧方法选择
        with ui.card_section().classes("py-2 px-4 border-b border-grey-2").style("color:var(--c-bg-hover)"):
            with ui.row().classes("items-center gap-3"):
                ui.label("默认折旧方法：").classes("text-sm").style("color:var(--c-text-secondary)")
                ui.select(
                    options=[{"label":"直线法（年限平均法）","value":"straight"},{"label":"双倍余额递减法","value":"double"},{"label":"年数总和法","value":"sum_years"}],
                    value="straight", label="折旧方法"
                ).props("dense outlined").classes("w-48")

        if assets:
            with ui.card_section().classes("py-3 px-4"):
                with ui.row().classes("gap-3 flex-wrap"):
                    for asset in assets:
                        with ui.card().classes("w-[280px] shadow-sm"):
                            with ui.card_section().classes("py-2 px-3 bg-blue-50"):
                                ui.label(asset.get("name","未命名")).classes("text-sm font-bold").style("color:var(--c-primary)")
                            with ui.card_section().classes("py-1.5 px-3"):
                                with ui.column().classes("gap-0.5 text-xs").style("color:var(--c-text-secondary)"):
                                    ui.label(f"编码：{asset.get('code','')}").classes("font-mono")
                                    ui.label(f"原值：¥{float(asset.get('purchase_price',0)):,.2f}").style("color:var(--c-text-secondary)")
                                    ui.label(f"净值：¥{float(asset.get('net_value',0)):,.2f}").classes("font-bold").style("color:var(--c-success)")
                            with ui.card_section().classes("py-1 px-3 flex gap-1"):
                                ui.button("📊 折旧明细", color="blue", on_click=lambda: show_toast("折旧明细", "info")).props("dense").classes("text-xs")
                                ui.button("🔄 计提", color="green", on_click=lambda: show_toast("折旧计提成功", "success")).props("dense").classes("text-xs")
                                ui.button("🗑 处置", color="red", on_click=lambda: show_toast("资产处置", "info")).props("dense").classes("text-xs")
        else:
            with ui.card_section().classes("py-12 text-center"):
                ui.icon("precision_manufacturing").style("font-size: 48px; color: var(--gray-300)")
                ui.label("暂无固定资产").classes("text-lg font-semibold mt-4").style("color:var(--c-text-muted)")
                ui.label("点击「新增资产」添加").classes("text-sm mt-2").style("color:var(--c-text-muted)")

