"""仪表盘"""
import os, sys, shutil
from datetime import datetime
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast, format_amount, navigate, refresh_main
from app.components.ui_components import KpiCard, EmptyState, SectionHeader, StatusBadge, MetricRow
from app.services import LedgerService, ReportService, VoucherService, AuthService

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

    # 数据库统计（通过服务层获取）
    try:
        _all_ledgers = LedgerService.get_all()
        ledger_count = len(_all_ledgers) if _all_ledgers else 0
        voucher_count = 0
        if _all_ledgers:
            for _lg in _all_ledgers:
                _lg_id = _lg.get("id") if isinstance(_lg, dict) else getattr(_lg, "id", None)
                if _lg_id:
                    try:
                        voucher_count += VoucherService.count(_lg_id) or 0
                    except Exception:
                        pass
        _all_users = AuthService.get_all()
        user_count = len(_all_users) if _all_users else 0
        entry_count = -1  # 无系统级分录统计服务
    except Exception:
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
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    if not lid:
        EmptyState(
            icon="account_balance",
            message="暂无账套",
            hint="请先创建账套以开始使用财务系统",
            action=lambda: navigate("settings"),
            action_label="前往设置"
        )
        return
    cache_key = (lid, state.selected_year, state.selected_month)
    if state._dashboard_cache is not None and state._dashboard_cache_key == cache_key:
        bs, inc, recent_vouchers = state._dashboard_cache
    else:
        bs = ReportService.get_balance_sheet(lid, state.selected_year, state.selected_month)
        inc = ReportService.get_income_statement(lid, state.selected_year, state.selected_month)
        recent_vouchers = VoucherService.get_all(lid, state.selected_year, state.selected_month, limit=8)
        state._dashboard_cache = (bs, inc, recent_vouchers)
        state._dashboard_cache_key = cache_key

    # 刷新按钮
    with ui.row().classes("w-full justify-end mb-2"):
        ui.button(icon="refresh", on_click=_refresh_dashboard).props("flat dense round").tooltip("刷新仪表盘")

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

    # ── KPI 指标区 ──
    try:
        kpi = ReportService.get_dashboard_kpi(lid, state.selected_year, state.selected_month)
    except Exception:
        kpi = {}

    # 动态计算上月对比趋势
    def _calc_trend(cur_val, prev_val):
        """计算环比趋势百分比，无法计算时返回 None"""
        try:
            cur = float(cur_val or 0)
            prev = float(prev_val or 0)
            if prev == 0:
                return None
            pct = (cur - prev) / abs(prev) * 100
            arrow = "↑" if pct >= 0 else "↓"
            return f"{arrow} {abs(pct):.1f}%"
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    # 获取上月数据用于趋势计算
    prev_month = state.selected_month - 1
    prev_year = state.selected_year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    try:
        inc_prev = ReportService.get_income_statement(lid, prev_year, prev_month)
    except Exception:
        inc_prev = {}
    try:
        bs_prev = ReportService.get_balance_sheet(lid, prev_year, prev_month)
    except Exception:
        bs_prev = {}

    # 时间段选择器
    with ui.row().classes("w-full items-center gap-2 mb-2"):
        ui.icon("calendar_today").classes("text-sm").style("color:var(--c-text-muted)")
        ui.label(f"{state.selected_year}年{state.selected_month}月").classes("text-sm").style("color:var(--c-text-secondary)")
        ui.select(
            options={"month": "本月", "quarter": "本季", "year": "本年"},
            value="month", label="时间范围"
        ).props("outlined dense").classes("w-28").style("font-size:12px;")

    # 第一行 KPI：资产负债权益 + 收入利润
    with ui.row().classes("w-full gap-3"):
        KpiCard("资产总计",   format_amount(bs.get('total_assets', 0)),   "account_balance", "blue",   trend=_calc_trend(bs.get('total_assets', 0), bs_prev.get('total_assets', 0)), on_click=lambda: navigate("balance_sheet"))
        KpiCard("负债总计",   format_amount(bs.get('total_liab', 0)),     "credit_card",    "red",    trend=_calc_trend(bs.get('total_liab', 0), bs_prev.get('total_liab', 0)), on_click=lambda: navigate("balance_sheet"))
        KpiCard("所有者权益", format_amount(bs.get('total_equity', 0)),   "savings",        "green",  trend=_calc_trend(bs.get('total_equity', 0), bs_prev.get('total_equity', 0)), on_click=lambda: navigate("balance_sheet"))
        KpiCard("本月收入",   format_amount(inc.get('total_revenue', 0)), "trending_up",    "purple", trend=_calc_trend(inc.get('total_revenue', 0), inc_prev.get('total_revenue', 0)), on_click=lambda: navigate("income_statement"))
        KpiCard("本月利润",   format_amount(inc.get('net_profit', 0)),    "attach_money",   "orange", trend=_calc_trend(inc.get('net_profit', 0), inc_prev.get('net_profit', 0)), on_click=lambda: navigate("income_statement"))

    # 第二行 KPI：应收/应付/银行存款/费用/现金流
    with ui.row().classes("w-full gap-3 mt-3"):
        KpiCard("应收账款",   format_amount(kpi.get('ar_balance', 0)),    "receipt",                  "indigo", on_click=lambda: navigate("account_ledger"))
        KpiCard("应付账款",   format_amount(kpi.get('ap_balance', 0)),    "payment",                  "orange", on_click=lambda: navigate("account_ledger"))
        KpiCard("银行存款",   format_amount(kpi.get('bank_balance', 0)), "account_balance_wallet",   "cyan",   on_click=lambda: navigate("cashier"))
        KpiCard("本月费用",   format_amount(kpi.get('month_expense', 0)),"money_off",                "red",    on_click=lambda: navigate("income_statement"))
        KpiCard("现金净流量", format_amount(kpi.get('net_cash_flow', 0)),"swap_horiz",               "teal",
                trend=_calc_trend(kpi.get('net_cash_flow', 0), None), on_click=lambda: navigate("cash_flow_statement"))


    # ── 第二行：最近凭证 + 快捷操作 ──
    with ui.row().classes("w-full gap-4 mt-4"):
        # 左侧：最近凭证（占 2/3 宽度）
        with ui.card().classes("flex-[2]"):
            SectionHeader("最近凭证", icon="receipt_long", action=lambda: navigate("journal"), action_icon="查看全部")
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
                rows = [{**v,"status_label":sm.get(v["status"],v["status"]),"status_color":sc.get(v["status"],"grey"),"total_formatted":format_amount(v.get("total_debit"))} for v in recent_vouchers]
                tbl = ui.table(columns=cols, rows=rows, row_key="voucher_no", pagination={"rowsPerPage":8}).classes("w-full")
                tbl.add_slot("body-cell-voucher_no", r"""<q-td key="voucher_no" :props="props"><q-btn flat dense no-caps color="primary" :label="props.row.voucher_no" @click="$parent.$emit('view', props.row.voucher_no)" /></q-td>""")
                tbl.add_slot("body-cell-status", r"""<q-td key="status" :props="props"><q-badge :color="props.row.status_color" :label="props.row.status_label" size="sm" /></q-td>""")
                tbl.add_slot("body-cell-total", r"""<q-td key="total" :props="props" class="tabular-nums text-sm font-medium">{{ props.row.total_formatted }}</q-td>""")
                tbl.on("view", lambda e: navigate("journal"))
            else:
                EmptyState(message="暂无凭证", hint="点击创建第一张凭证", action=lambda: navigate("journal"), action_label="新增凭证")

        # 右侧：快捷操作（占 1/3 宽度）
        with ui.card().classes("w-72"):
            SectionHeader("快捷操作", icon="bolt")
            with ui.card_section().classes("py-2 px-3"):
                with ui.column().classes("gap-1"):
                    _quick_actions = [
                        ("journal",              "add",           "新增凭证",   "var(--c-primary)"),
                        ("account_ledger",       "table_chart",   "科目余额",   ""),
                        ("balance_sheet",        "account_balance","资产负债表", ""),
                        ("income_statement",     "trending_up",   "利润表",     ""),
                        ("close_period",         "sync_alt",      "期末结转",   ""),
                        ("ai_assistant",         "smart_toy",     "AI助手",     ""),
                        ("export",               "cloud_download","导出数据",   ""),
                    ]
                    for nav, icon_n, label, color in _quick_actions:
                        ui.button(label, icon=icon_n, on_click=lambda n=nav: navigate(n)).props("dense no-caps").classes("w-full justify-start nav-btn").style(f"color: {color or 'var(--c-text-secondary)'}")

    # ── 第三行：图表（月度趋势 + 费用占比）──
    with ui.row().classes("w-full gap-4 mt-4"):
        # 左侧：月度收支趋势图
        with ui.card().classes("flex-1"):
            SectionHeader("月度收支趋势", icon="show_chart")
            with ui.card_section().classes("py-3 px-4"):
                try:
                    trend_data = ReportService.get_monthly_trend(lid, 12)
                    if trend_data:
                        months_list = [str(m.get("month", "")) for m in trend_data]
                        income_list = [float(m.get("income") or m.get("revenue") or 0) for m in trend_data]
                        expense_list = [float(m.get("expense") or 0) for m in trend_data]
                        trend_option = {
                            "tooltip": {"trigger": "axis"},
                            "legend": {"data": ["收入", "费用"], "bottom": 0},
                            "grid": {"left": "3%", "right": "4%", "bottom": "12%", "top": "8%", "containLabel": True},
                            "xAxis": {"type": "category", "data": months_list, "axisLabel": {"fontSize": 11}},
                            "yAxis": {"type": "value", "axisLabel": {"fontSize": 11, "formatter": "¥{value}"}},
                            "series": [
                                {"name": "收入", "type": "line", "smooth": True, "data": income_list, "itemStyle": {"color": "var(--c-success)"}, "areaStyle": {"opacity": 0.1}},
                                {"name": "费用", "type": "line", "smooth": True, "data": expense_list, "itemStyle": {"color": "var(--c-danger)"}, "areaStyle": {"opacity": 0.1}},
                            ]
                        }
                        ui.chart(trend_option).classes("h-64 w-full")
                    else:
                        EmptyState(icon="bar_chart", message="暂无趋势数据")
                except Exception:
                    EmptyState(icon="error_outline", message="图表加载失败")

        # 右侧：费用占比饼图
        with ui.card().classes("flex-1"):
            SectionHeader("费用占比分析", icon="pie_chart")
            with ui.card_section().classes("py-3 px-4"):
                try:
                    expense_data = ReportService.get_expense_breakdown(lid, state.selected_year, state.selected_month)
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
                        EmptyState(icon="pie_chart", message="暂无费用数据")
                except Exception:
                    EmptyState(icon="error_outline", message="图表加载失败")

    # ── 第四行：系统健康状态面板 ──
    try:
        _health = _get_system_health()
        _db = _health.get("database", {})
        _bk = _health.get("backup", {})
        _dk = _health.get("disk", {})
        _db_ok = _db.get("healthy", False)
        _bk_ok = _bk.get("last_status") == "成功"
        _dk_warn = _dk.get("warning", False)
        _overall = "healthy" if (_db_ok and _bk_ok and not _dk_warn) else "warning"

        with ui.row().classes("w-full gap-3 mt-3"):
            # 数据库状态
            with ui.card().classes("flex-1"):
                SectionHeader("系统状态 · " + ("正常" if _overall == "healthy" else "警告"), icon="storage")
                with ui.card_section().classes("py-2 px-3"):
                    with ui.column().classes("gap-1.5"):
                        MetricRow("数据库", "✅ 正常" if _db_ok else "❌ 异常",
                                  value_color="var(--c-success)" if _db_ok else "var(--c-danger)")
                        _vc = _db.get('vouchers', 0) if _db.get('vouchers', -1) >= 0 else "—"
                        _ec = _db.get('entries', 0) if _db.get('entries', -1) >= 0 else "—"
                        MetricRow("凭证/分录", f"{_vc} / {_ec}")
                        MetricRow("数据库大小", f"{_db.get('size_mb',0):.1f} MB")

            # 备份状态
            with ui.card().classes("flex-1"):
                SectionHeader("备份状态", icon="backup")
                with ui.card_section().classes("py-2 px-3"):
                    with ui.column().classes("gap-1.5"):
                        _lb = _bk.get("last_backup", "--")
                        MetricRow("上次备份", _lb[:19].replace("T", " ") if _lb and _lb != "--" else "--")
                        MetricRow("备份总数", f"{_bk.get('total_backups', 0)} 次")
                        MetricRow("状态", "✅ " + str(_bk.get("last_status","--")) if _bk_ok else "⚠️ " + str(_bk.get("last_status","--")),
                                  value_color="var(--c-success)" if _bk_ok else "var(--c-warning)")

            # 磁盘空间
            with ui.card().classes("flex-1"):
                SectionHeader("磁盘空间", icon="sd_storage")
                with ui.card_section().classes("py-2 px-3"):
                    with ui.column().classes("gap-1.5"):
                        MetricRow("已用", f"{_dk.get('usage_pct', 0):.1f}%",
                                  value_color="var(--c-danger)" if _dk_warn else "var(--c-success)")
                        MetricRow("可用", f"{_dk.get('free_gb', 0):.0f} GB")
                        # 进度条
                        with ui.element("div").style("width:100%; height:6px; background:var(--c-border); border-radius:3px; margin-top:2px;"):
                            ui.element("div").style(
                                f"width:{_dk.get('usage_pct',0)}%; height:6px; "
                                f"background:{'var(--c-danger)' if _dk_warn else 'var(--c-success)'}; "
                                f"border-radius:3px;"
                            )
    except Exception:
        pass

def _refresh_dashboard():
    """清除缓存并重新渲染仪表盘"""
    state._dashboard_cache = None
    state._dashboard_cache_key = None
    refresh_main()
    show_toast("仪表盘已刷新", "success")
