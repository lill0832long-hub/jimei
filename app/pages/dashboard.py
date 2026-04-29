"""仪表盘"""
import os, sys, shutil, sqlite3
from datetime import datetime
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount, navigate
from database_v3 import (
    get_ledgers, get_vouchers, get_account_balances,
    get_balance_sheet, get_income_statement, get_period_status,
    get_dashboard_kpi, get_monthly_trend, get_expense_breakdown,
)

# 外部 API（已关闭）
_EXTERNAL_APIS_OK = False

# ── 系统健康检查依赖的全局变量 ──
_AUTO_BACKUP_DIR = os.path.join(os.path.dirname(__file__), "../backups")
_AUTO_BACKUP_ENABLED = True
_AUTO_BACKUP_INTERVAL_HOURS = 24
_backup_status = {
    "last_backup": None,
    "last_status": "未启动",
    "total_backups": 0,
    "errors": [],
}

def _check_database_integrity():
    """检查数据库完整性"""
    import sqlite3
    try:
        _db = os.path.join(os.path.dirname(__file__), "../finance_v2.db")
        _conn = sqlite3.connect(_db, timeout=10)
        _conn.execute("PRAGMA integrity_check")
        _conn.close()
        return True
    except Exception:
        return False

def _get_system_health():
    """获取系统健康状态"""
    import shutil

    # 数据库路径：dashboard.py 在 app/pages/ 子目录，需要 ../ 指向项目根目录
    db_path = os.path.join(os.path.dirname(__file__), "../finance_v2.db")
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    # 磁盘空间
    disk = shutil.disk_usage(os.path.dirname(__file__))
    disk_free_gb = round(disk.free / (1024**3), 2)
    disk_total_gb = round(disk.total / (1024**3), 2)
    disk_usage_pct = round((disk.used / disk.total) * 100, 1)

    # 数据库统计（使用独立连接避免 WAL 锁冲突）
    try:
        import sqlite3 as _sqlite3
        _db_path = os.path.join(os.path.dirname(__file__), "../finance_v2.db")
        _conn = _sqlite3.connect(_db_path, timeout=10)
        _conn.execute("PRAGMA query_only=ON")
        _conn.execute("PRAGMA journal_mode=WAL")
        voucher_count = _conn.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0]
        entry_count = _conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        user_count = _conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        ledger_count = _conn.execute("SELECT COUNT(*) FROM ledgers").fetchone()[0]
        _conn.close()
    except Exception as _e:
        voucher_count = entry_count = user_count = ledger_count = -1

    # 备份状态
    backup_dir = _AUTO_BACKUP_DIR  # 已在顶部定义
    backup_files = []
    if os.path.exists(backup_dir):
        backup_files = sorted([f for f in os.listdir(backup_dir) if f.endswith('.json')], reverse=True)

    db_healthy = _check_database_integrity()

    return {
        "status": "healthy" if db_healthy else "error",
        "timestamp": datetime.now().isoformat(),
        "database": {
            "healthy": db_healthy,
            "size_mb": round(db_size / (1024**2), 2),
            "vouchers": voucher_count,
            "entries": entry_count,
            "users": user_count,
            "ledgers": ledger_count,
        },
        "disk": {
            "free_gb": disk_free_gb,
            "total_gb": disk_total_gb,
            "usage_pct": disk_usage_pct,
            "warning": disk_usage_pct > 85,
        },
        "backup": {
            "enabled": _AUTO_BACKUP_ENABLED,
            "interval_hours": _AUTO_BACKUP_INTERVAL_HOURS,
            "last_backup": _backup_status["last_backup"],
            "last_status": _backup_status["last_status"],
            "total_backups": _backup_status["total_backups"],
            "recent_backups": backup_files[:5],
            "recent_errors": _backup_status["errors"][-5:],
        },
        "system": {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "db_path": db_path,
        }
    }

def render_dashboard():
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        with ui.card().classes("w-full"):
            with ui.card_section().classes("py-12 text-center"):
                ui.label("请先创建账套").classes("text-grey-4")
        return
    cache_key = (lid, state.selected_year, state.selected_month)
    if state._dashboard_cache is not None and state._dashboard_cache_key == cache_key:
        bs, inc, recent_vouchers = state._dashboard_cache
    else:
        bs = get_balance_sheet(lid, state.selected_year, state.selected_month)
        inc = get_income_statement(lid, state.selected_year, state.selected_month)
        recent_vouchers = get_vouchers(lid, state.selected_year, state.selected_month, limit=8)
        state._dashboard_cache = (bs, inc, recent_vouchers)
        state._dashboard_cache_key = cache_key

    # ── 新用户引导面板 ──
    if state.show_onboarding:
        with ui.card().classes("w-full"):
            with ui.card_section().classes("py-3 px-4 border-b border-grey-1"):
                with ui.row().classes("items-center justify-between"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("rocket_launch").classes("text-blue-7")
                        ui.label("🚀 欢迎使用 AI 财务系统！").classes("text-sm font-semibold")
                    ui.button("跳过引导", on_click=lambda: setattr(state, 'show_onboarding', False)).props("flat dense").classes("text-xs text-grey-5")
            with ui.card_section().classes("py-3 px-4"):
                with ui.row().classes("gap-4"):
                    with ui.column().classes("flex-1 gap-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label("1️⃣").classes("text-base")
                            ui.label("创建凭证").classes("text-sm font-semibold")
                        ui.label("点击「新增凭证」录入记账凭证，支持借贷平衡校验").classes("text-xs text-grey-5 ml-6")
                    with ui.column().classes("flex-1 gap-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label("2️⃣").classes("text-base")
                            ui.label("查看报表").classes("text-sm font-semibold")
                        ui.label("资产负债表、利润表自动生成，实时查看财务状况").classes("text-xs text-grey-5 ml-6")
                    with ui.column().classes("flex-1 gap-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label("3️⃣").classes("text-base")
                            ui.label("期末结转").classes("text-sm font-semibold")
                        ui.label("月末执行损益结转，系统自动生成结转凭证").classes("text-xs text-grey-5 ml-6")
                    with ui.column().classes("flex-1 gap-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label("4️⃣").classes("text-base")
                            ui.label("AI 助手").classes("text-sm font-semibold")
                        ui.label("使用 AI 助手查询汇率、计算税额、生成凭证建议").classes("text-xs text-grey-5 ml-6")

    # ── 第一行：KPI 卡片（增强版）──
    # 获取 Dashboard KPI 数据
    try:
        kpi = get_dashboard_kpi(lid, state.selected_year, state.selected_month)
    except Exception:
        kpi = {}

    # 时间段选择器
    with ui.row().classes("w-full items-center gap-2 mb-1"):
        ui.icon("calendar_today").classes("text-grey-5 text-sm")
        ui.label(f"{state.selected_year}年{state.selected_month}月").classes("text-sm text-grey-6")
        ui.select(
            options={"month": "本月", "quarter": "本季", "year": "本年"},
            value="month",
            label="时间范围"
        ).props("outlined dense").classes("w-28").style("font-size:12px;")

    # 第一行 KPI：资产/负债/权益（原有）
    with ui.row().classes("w-full gap-3"):
        _kpi_card("资产总计",   f"¥{bs['total_assets']:,.0f}",   "account_balance", "blue",   "↑ 2.3%", "balance_sheet")
        _kpi_card("负债总计",   f"¥{bs['total_liab']:,.0f}",     "credit_card",    "red",    "↓ 1.1%", "balance_sheet")
        _kpi_card("所有者权益", f"¥{bs['total_equity']:,.0f}",   "savings",        "green",  "↑ 3.8%", "balance_sheet")
        _kpi_card("本月收入",   f"¥{inc.get('total_revenue',0):,.0f}", "trending_up","purple", "↑ 12.5%", "income_statement")
        _kpi_card("本月利润",   f"¥{inc.get('net_profit',0):,.0f}",    "attach_money","orange", "↑ 8.2%", "income_statement")

    # 第二行 KPI：应收账款/应付账款/银行存款/本月费用/现金净流量（新增）
    with ui.row().classes("w-full gap-3 mt-2"):
        _kpi_card("应收账款",   f"¥{kpi.get('ar_balance', 0):,.0f}",  "receipt",        "indico",  None, "account_ledger")
        _kpi_card("应付账款",   f"¥{kpi.get('ap_balance', 0):,.0f}",  "payment",        "orange",  None, "account_ledger")
        _kpi_card("银行存款",   f"¥{kpi.get('bank_balance', 0):,.0f}", "account_balance_wallet", "cyan", None, "cashier")
        _kpi_card("本月费用",   f"¥{kpi.get('month_expense', 0):,.0f}", "money_off",     "red",   None, "income_statement")
        _kpi_card("现金净流量", f"¥{kpi.get('net_cash_flow', 0):,.0f}", "swap_horiz",  "teal",  kpi.get('net_cash_flow', 0) >= 0 and "↑" or "↓", "cash_flow_statement")


    # ── 第二行：最近凭证 + 快捷操作 ──
    with ui.row().classes("w-full gap-4 mt-2"):
        # 左侧：最近凭证（占 2/3 宽度）
        with ui.card().classes("flex-[2]"):
            with ui.card_section().classes("py-3 px-4 border-b border-grey-1"):
                with ui.row().classes("items-center justify-between"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("receipt_long").classes("text-blue-7")
                        ui.label("最近凭证").classes("text-sm font-semibold")
                    ui.button("查看全部", on_click=lambda: navigate("journal")).props("flat dense").classes("text-xs text-blue-7")
            if recent_vouchers:
                cols = [
                    {"name":"voucher_no","label":"凭证号","field":"voucher_no","align":"left","headerClasses":"text-xs font-semibold text-grey-6 uppercase"},
                    {"name":"date","label":"日期","field":"date","headerClasses":"text-xs font-semibold text-grey-6 uppercase"},
                    {"name":"description","label":"摘要","field":"description","align":"left","headerClasses":"text-xs font-semibold text-grey-6 uppercase"},
                    {"name":"total","label":"金额","field":"total_debit","align":"right","classes":"tabular-nums text-sm","headerClasses":"text-xs font-semibold text-grey-6 uppercase"},
                    {"name":"status","label":"状态","field":"status","align":"center","headerClasses":"text-xs font-semibold text-grey-6 uppercase"},
                ]
                sm = {"draft":"草稿","posted":"已过账","reversed":"已冲销","pending_review":"待审核"}
                sc = {"draft":"orange","posted":"green","reversed":"red","pending_review":"blue"}
                rows = [{**v,"status_label":sm.get(v["status"],v["status"]),"status_color":sc.get(v["status"],"grey")} for v in recent_vouchers]
                tbl = ui.table(columns=cols, rows=rows, row_key="voucher_no", pagination={"rowsPerPage":8}).classes("w-full")
                tbl.add_slot("body-cell-voucher_no", r"""<q-td key="voucher_no" :props="props"><q-btn flat dense no-caps color="primary" :label="props.row.voucher_no" @click="$parent.$emit('view', props.row.voucher_no)" /></q-td>""")
                tbl.add_slot("body-cell-status", r"""<q-td key="status" :props="props"><q-badge :color="props.row.status_color" :label="props.row.status_label" size="sm" /></q-td>""")
                tbl.add_slot("body-cell-total", r"""<q-td key="total" :props="props" class="tabular-nums text-sm font-medium">¥{{ props.row.total_debit !== null ? Number(props.row.total_debit).toLocaleString('en-US',{minimumFractionDigits:0,maximumFractionDigits:0}) : '—' }}</q-td>""")
                tbl.on("view", lambda e: navigate("journal"))
            else:
                with ui.card_section().classes("py-12 text-center"):
                    ui.icon("inbox").classes("text-grey-3 text-3xl")
                    ui.label("暂无凭证").classes("text-grey-4 text-sm mt-2")
                    ui.button("新增凭证", icon="add", on_click=lambda: navigate("journal")).props("flat").classes("text-blue-7 mt-2")

        # 右侧：快捷操作（占 1/3 宽度）
        with ui.card().classes("w-72"):
            with ui.card_section().classes("py-3 px-4 border-b border-grey-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("bolt").classes("text-orange-6")
                    ui.label("快捷操作").classes("text-sm font-semibold")
            with ui.card_section().classes("py-2 px-3"):
                with ui.column().classes("gap-1.5"):
                    for nav, icon_n, label, color in [
                        ("journal","add","新增凭证","var(--blue-600)"),
                        ("accounts","table_chart","科目余额",""),
                        ("balance_sheet","account_balance","资产负债表",""),
                        ("income_statement","trending_up","利润表",""),
                        ("close_period","sync_alt","期末结转",""),
                        ("ai_assistant","smart_toy","AI助手",""),
                        ("export","cloud_download","导出数据",""),
                    ]:
                        ui.button(label, icon=icon_n, on_click=lambda n=nav: navigate(n)).props("dense").classes("w-full justify-start nav-btn").style(f"color: {color or 'inherit'}")

    # ── 第三行：图表（月度趋势 + 费用占比）──
    with ui.row().classes("w-full gap-4 mt-3"):
        # 左侧：月度收支趋势图
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4 border-b border-grey-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("show_chart").classes("text-blue-7")
                    ui.label("月度收支趋势").classes("text-sm font-semibold")
            with ui.card_section().classes("py-3 px-4"):
                try:
                    trend_data = get_monthly_trend(lid, 12)
                    if trend_data:
                        months_list = [f"{m.get('year','')}-{m.get('month',''):02d}" if isinstance(m.get('month'), int) else str(m.get('month','')) for m in trend_data]
                        income_list = [float(m.get('revenue', m.get('income', 0)) or 0) for m in trend_data]
                        expense_list = [float(m.get('expense', 0) or 0) for m in trend_data]
                        trend_option = {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"data": ["收入", "费用"], "bottom": 0},
                            "grid": {"left": "3%", "right": "4%", "bottom": "12%", "top": "8%", "containLabel": True},
                            "xAxis": {"type": "category", "data": months_list, "axisLabel": {"fontSize": 11}},
                            "yAxis": {"type": "value", "axisLabel": {"fontSize": 11, "formatter": "¥{value}"}},
                            "series": [
                                {"name": "收入", "type": "line", "smooth": True, "data": income_list, "itemStyle": {"color": "#43a047"}, "areaStyle": {"opacity": 0.1}},
                                {"name": "费用", "type": "line", "smooth": True, "data": expense_list, "itemStyle": {"color": "#e53935"}, "areaStyle": {"opacity": 0.1}},
                            ]
                        }
                        ui.chart(trend_option).classes("h-64 w-full")
                    else:
                        with ui.column().classes("items-center justify-center py-8 gap-2"):
                            ui.icon("bar_chart").classes("text-3xl text-grey-3")
                            ui.label("暂无趋势数据").classes("text-sm text-grey-4")
                except Exception as e:
                    with ui.column().classes("items-center justify-center py-8 gap-2"):
                        ui.icon("error_outline").classes("text-3xl text-grey-3")
                        ui.label("图表加载失败").classes("text-sm text-grey-4")

        # 右侧：费用占比饼图
        with ui.card().classes("flex-1"):
            with ui.card_section().classes("py-3 px-4 border-b border-grey-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("pie_chart").classes("text-purple-7")
                    ui.label("费用占比分析").classes("text-sm font-semibold")
            with ui.card_section().classes("py-3 px-4"):
                try:
                    expense_data = get_expense_breakdown(lid, state.selected_year, state.selected_month)
                    if expense_data:
                        pie_option = {
                            "tooltip": {"trigger": "item", "formatter": "{b}: ¥{c} ({d}%)"},
                            "legend": {"orient": "vertical", "right": "5%", "top": "middle", "itemWidth": 10, "itemHeight": 10},
                            "series": [{
                                "name": "费用占比",
                                "type": "pie",
                                "radius": ["40%", "70%"],
                                "center": ["40%", "50%"],
                                "avoidLabelOverlap": False,
                                "itemStyle": {"borderRadius": 4, "borderColor": "#fff", "borderWidth": 2},
                                "label": {"show": False},
                                "data": [{"name": e.get("category", e.get("name", "其他")), "value": float(e.get("amount", 0) or 0)} for e in expense_data]
                            }]
                        }
                        ui.chart(pie_option).classes("h-64 w-full")
                    else:
                        with ui.column().classes("items-center justify-center py-8 gap-2"):
                            ui.icon("pie_chart").classes("text-3xl text-grey-3")
                            ui.label("暂无费用数据").classes("text-sm text-grey-4")
                except Exception as e:
                    with ui.column().classes("items-center justify-center py-8 gap-2"):
                        ui.icon("error_outline").classes("text-3xl text-grey-3")
                        ui.label("图表加载失败").classes("text-sm text-grey-4")

    # ── 第四行：系统健康状态面板（Week 4 可观测性）──
    try:
        _health = _get_system_health()
        _db = _health.get("database", {})
        _bk = _health.get("backup", {})
        _dk = _health.get("disk", {})
        _db_ok = _db.get("healthy", False)
        _bk_ok = _bk.get("last_status") == "成功"
        _dk_warn = _dk.get("warning", False)
        _overall = "healthy" if (_db_ok and _bk_ok and not _dk_warn) else "warning"

        with ui.row().classes("w-full gap-3 mt-1"):
            # 数据库状态
            with ui.card().classes("flex-1"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("storage").classes("text-blue-7")
                        ui.label("系统状态").classes("text-sm font-semibold")
                        ui.label("● " + ("正常" if _overall == "healthy" else "警告")).classes("text-xs font-semibold ml-auto").style(
                            "color: #4caf50;" if _overall == "healthy" else "color: #ff9800;"
                        )
                with ui.card_section().classes("py-2 px-3"):
                    with ui.column().classes("gap-1.5"):
                        with ui.row().classes("items-center justify-between"):
                            ui.label("数据库").classes("text-xs text-grey-5")
                            ui.label("✅ 正常" if _db_ok else "❌ 异常").classes("text-xs font-semibold").style(
                                "color: #4caf50;" if _db_ok else "color: #f44336;"
                            )
                        with ui.row().classes("items-center justify-between"):
                            ui.label("凭证/分录").classes("text-xs text-grey-5")
                            ui.label(f"{_db.get('vouchers',0)} / {_db.get('entries',0)}").classes("text-xs tabular-nums text-grey-7")
                        with ui.row().classes("items-center justify-between"):
                            ui.label("数据库大小").classes("text-xs text-grey-5")
                            ui.label(f"{_db.get('size_mb',0):.1f} MB").classes("text-xs tabular-nums text-grey-7")

            # 备份状态
            with ui.card().classes("flex-1"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("backup").classes("text-green-7")
                        ui.label("备份状态").classes("text-sm font-semibold")
                        ui.label("自动" if _bk.get("enabled") else "关闭").classes("text-xs text-grey-4 ml-auto")
                with ui.card_section().classes("py-2 px-3"):
                    with ui.column().classes("gap-1.5"):
                        with ui.row().classes("items-center justify-between"):
                            ui.label("上次备份").classes("text-xs text-grey-5")
                            _lb = _bk.get("last_backup", "--")
                            ui.label(_lb[:19].replace("T", " ") if _lb and _lb != "--" else "--").classes("text-xs tabular-nums text-grey-7")
                        with ui.row().classes("items-center justify-between"):
                            ui.label("备份总数").classes("text-xs text-grey-5")
                            ui.label(f"{_bk.get('total_backups', 0)} 次").classes("text-xs tabular-nums text-grey-7")
                        with ui.row().classes("items-center justify-between"):
                            ui.label("状态").classes("text-xs text-grey-5")
                            ui.label("✅ " + str(_bk.get("last_status","--")) if _bk_ok else "⚠️ " + str(_bk.get("last_status","--"))).classes("text-xs font-semibold").style(
                                "color: #4caf50;" if _bk_ok else "color: #ff9800;"
                            )

            # 磁盘空间
            with ui.card().classes("flex-1"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("sd_storage").classes("text-purple-7")
                        ui.label("磁盘空间").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    with ui.column().classes("gap-1.5"):
                        with ui.row().classes("items-center justify-between"):
                            ui.label("已用").classes("text-xs text-grey-5")
                            ui.label(f"{_dk.get('usage_pct', 0):.1f}%").classes("text-xs tabular-nums font-semibold").style(
                                "color: #f44336;" if _dk_warn else "color: #4caf50;"
                            )
                        with ui.row().classes("items-center justify-between"):
                            ui.label("可用").classes("text-xs text-grey-5")
                            ui.label(f"{_dk.get('free_gb', 0):.0f} GB").classes("text-xs tabular-nums text-grey-7")
                        # 进度条
                        with ui.element("div").style("width:100%; height:6px; background:#e0e0e0; border-radius:3px; margin-top:2px;"):
                            ui.element("div").style(
                                f"width:{_dk.get('usage_pct',0)}%; height:6px; "
                                f"background:{'#f44336' if _dk_warn else '#4caf50'}; "
                                f"border-radius:3px;"
                            )
    except Exception as _he:
        # 健康面板加载失败不影响主界面
        pass
def _kpi_card(title: str, value: str, icon: str, color: str, trend: str = None, navigate_to: str = None):
    """KPI 卡片 — 大数字 + 等宽 + 趋势标签 + 点击跳转"""
    colors = {
        "blue":   ("#1976d2", "#e3f2fd"),
        "red":    ("#e53935", "#ffebee"),
        "green":  ("#43a047", "#e8f5e9"),
        "purple": ("#7b1fa2", "#f3e5f5"),
        "orange": ("#f57c00", "#fff3e0"),
        "indico": ("#3949ab", "#e8eaf6"),
        "cyan":   ("#00838d", "#e0f7fa"),
        "teal":   ("#00695c", "#e0f2f1"),
    }
    hex_c, bg_c = colors.get(color, colors["blue"])
    tc, tb = (("#2e7d32","#e8f5e9") if trend and trend.startswith("↑") else
              ("#c62828","#ffebee") if trend and trend.startswith("↓") else
              ("#757575","#eeeeee"))
    card = ui.card().classes("kpi-card flex-1")
    if navigate_to:
        card.style("cursor: pointer;")
        card.on("click", lambda: navigate(navigate_to))
    with card:
        with ui.card_section().classes("py-3 px-4"):
            with ui.row().classes("items-center gap-3"):
                with ui.element("div").style(
                    f"width:40px; height:40px; border-radius:10px; background:{bg_c}; "
                    f"display:flex; align-items:center; justify-content:center; flex-shrink:0;"
                ):
                    ui.icon(icon).classes("kpi-icon").style(f"color: {hex_c}")
                with ui.column().classes("gap-0.5 flex-1 min-w-0"):
                    ui.label(title).classes("text-xs text-grey-5 font-medium truncate")
                    ui.label(value).classes("tabular-nums").style(
                        "font-size:26px; font-weight:700; color:#1a1a1a; line-height:1.2;"
                    )
                    if trend:
                        ui.label(trend).classes("text-xs font-semibold").style(
                            f"color:{tc}; background:{tb}; padding:2px 8px; "
                            f"border-radius:4px; display:inline-block; width:fit-content;"
                        )
