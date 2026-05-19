"""
页面渲染验证 —— 所有页面能正常渲染不报错

运行方法: python tests/test_render.py
输出: 每个页面的渲染状态 + 汇总

验证维度:
1. 所有 28 个页面渲染不抛异常
2. header + sidebar 渲染正常
3. 登录页渲染正常
"""
import sys, os, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nicegui import ui
from app.components.state import state


def setup():
    """初始化数据库和状态"""
    from database.connection import init_db, init_v3_tables
    from app.services import LedgerService
    init_db()
    try:
        init_v3_tables()
    except:
        pass
    # 确保有默认账套
    ledgers = LedgerService.get_all()
    if not ledgers:
        from app.services import LedgerService
        LedgerService.create(name="默认账套", company="测试公司")
        ledgers = LedgerService.get_all()
    state.selected_ledger_id = ledgers[0]["id"]
    state.selected_year = 2026
    state.selected_month = 5
    state.current_user = {"id": 1, "username": "admin", "role": "admin"}
    state.sidebar_group_expanded = {
        "work": True, "operations": True, "reports": True, "finance": True,
    }


# 所有需要测试的页面
PAGES = [
    ("dashboard",      "app.pages.dashboard",              "render_dashboard"),
    ("journal",        "app.pages.journal",                "render_journal"),
    ("accounts",       "app.pages.reports",                "render_accounts"),
    ("balance_sheet",  "app.pages.reports_balance_sheet",  "render_balance_sheet"),
    ("trial_balance",  "app.pages.trial_balance",          "render_trial_balance"),
    ("income_statement","app.pages.reports_income_statement","render_income_statement"),
    ("close_period",   "app.pages.close_period",           "render_close_period"),
    ("charts",         "app.pages.charts",                 "render_charts"),
    ("compare",        "app.pages.compare",                "render_compare"),
    ("ai_assistant",   "app.pages.ai_assistant",           "render_ai_assistant"),
    ("import",         "app.pages.import_export",          "render_import"),
    ("export",         "app.pages.import_export",          "render_export"),
    ("fixed_assets",   "app.pages.fixed_assets",           "render_fixed_assets"),
    ("cashier",        "app.pages.cashier",                "render_cashier"),
    ("auxiliary",      "app.pages.auxiliary",              "render_auxiliary"),
    ("settings",       "app.pages.settings",               "render_settings"),
    ("about",          "app.pages.settings",               "render_about"),
    ("tax",            "app.pages.tax",                    "render_tax"),
    ("cash_flow",      "app.pages.cash_flow",              "render_cash_flow"),
    ("budget",         "app.pages.budget",                 "render_budget"),
    ("scheduled","app.pages.scheduled_vouchers",            "render_scheduled_vouchers"),
    ("invoices",       "app.pages.invoices",               "render_invoices"),
    ("multi_currency", "app.pages.multi_currency",          "render_multi_currency"),
    ("setup_wizard",   "app.pages.setup_wizard",           "render_setup_wizard"),
    ("voucher_template","app.pages.voucher_template",      "render_voucher_template"),
    ("account_ledger", "app.pages.account_ledger",          "render_account_ledger"),
    ("bank_recon",     "app.pages.bank_reconciliation",    "render_bank_reconciliation"),
    ("cash_flow_stmt", "app.pages.cash_flow_statement",    "render_cash_flow_statement"),
    ("audit_log",      "app.pages.audit_log",              "render_audit_log"),
]

# 组件测试
COMPONENTS = [
    ("header",  "app.components.ui_helpers", "render_header"),
    ("sidebar", "app.components.ui_helpers", "render_sidebar"),
    ("login",   "app.pages.auth",            "render_login"),
]


def test_pages():
    """测试所有页面渲染"""
    setup()
    results = []
    containers = []

    print("=" * 60)
    print("页面渲染测试")
    print("=" * 60)

    for page_key, module_path, func_name in PAGES:
        try:
            mod = __import__(module_path, fromlist=[func_name])
            render_fn = getattr(mod, func_name)
            state.current_page = page_key
            container = ui.column().classes("w-full")
            with container:
                render_fn()
            containers.append(container)
            results.append(("OK", page_key, ""))
            print(f"  ✅ {page_key}")
        except Exception as e:
            tb = traceback.format_exc()
            results.append(("FAIL", page_key, str(e)))
            print(f"  ❌ {page_key}: {e}")
            print(f"     {tb[:300]}")

    # 清理
    for c in containers:
        try:
            c.clear()
        except:
            pass

    ok = sum(1 for r in results if r[0] == "OK")
    fail = sum(1 for r in results if r[0] == "FAIL")
    print(f"\n结果: ✅ {ok} / ❌ {fail} / 总计 {len(results)}")
    return results


def test_components():
    """测试 header / sidebar / login 组件渲染"""
    setup()
    results = []

    print("\n" + "=" * 60)
    print("组件渲染测试")
    print("=" * 60)

    for comp_name, module_path, func_name in COMPONENTS:
        try:
            mod = __import__(module_path, fromlist=[func_name])
            render_fn = getattr(mod, func_name)
            if comp_name == "login":
                state.current_user = None
            container = ui.column().classes("w-full")
            with container:
                render_fn()
            container.clear()
            results.append(("OK", comp_name, ""))
            print(f"  ✅ {comp_name}")
        except Exception as e:
            tb = traceback.format_exc()
            results.append(("FAIL", comp_name, str(e)))
            print(f"  ❌ {comp_name}: {e}")
            print(f"     {tb[:300]}")

    ok = sum(1 for r in results if r[0] == "OK")
    fail = sum(1 for r in results if r[0] == "FAIL")
    print(f"\n结果: ✅ {ok} / ❌ {fail} / 总计 {len(results)}")
    return results


if __name__ == "__main__":
    page_results = test_pages()
    comp_results = test_components()

    all_ok = all(r[0] == "OK" for r in page_results + comp_results)
    print("\n" + "=" * 60)
    if all_ok:
        print("🎉 全部通过")
    else:
        print("💥 存在失败项，请检查上方输出")
    print("=" * 60)
    sys.exit(0 if all_ok else 1)
