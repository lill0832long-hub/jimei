"""报表服务层 — 使用 Repository 模式"""
import asyncio
from app.repository.report_repository import ReportRepository
from app.repository.invoice_repository import InvoiceRepository
from .budget_service import BudgetService

_report_repo = ReportRepository()
_invoice_repo = InvoiceRepository()


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class ReportService:
    """报表生成"""

    # ── 科目余额表 ──
    @staticmethod
    def get_account_balances(ledger_id, year, month):
        return _run(_report_repo.get_account_balances(ledger_id, year, month))

    # ── 资产负债表（使用 repository 数据 + service 层计算） ──
    @staticmethod
    def get_balance_sheet(ledger_id, year, month):
        balances = _run(_report_repo.get_account_balances(ledger_id, year, month))
        # Aggregate into balance sheet categories
        assets = {"current": [], "non_current": [], "total": 0}
        liabilities = {"current": [], "non_current": [], "total": 0}
        equity = {"items": [], "total": 0}

        for b in balances:
            cat = b["category"]
            closing = b["closing_balance"]
            if cat == "资产":
                if b["account_code"][0] in ("1",):
                    assets["current"].append(b)
                else:
                    assets["non_current"].append(b)
                assets["total"] += closing
            elif cat == "负债":
                liabilities["current"].append(b)
                liabilities["total"] += closing
            elif cat == "权益":
                equity["items"].append(b)
                equity["total"] += closing

        return {
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "total_liabilities_equity": liabilities["total"] + equity["total"],
        }

    # ── 利润表 ──
    @staticmethod
    def get_income_statement(ledger_id, year, month):
        balances = _run(_report_repo.get_account_balances(ledger_id, year, month))
        revenue = []
        expenses = []
        total_revenue = 0
        total_expense = 0

        for b in balances:
            cat = b["category"]
            period_credit = b["period_credit"]
            period_debit = b["period_debit"]
            if cat == "收入":
                revenue.append(b)
                total_revenue += period_credit
            elif cat == "费用":
                expenses.append(b)
                total_expense += period_debit

        return {
            "revenue": revenue,
            "expenses": expenses,
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_income": total_revenue - total_expense,
        }

    # ── 现金流（暂保留旧实现） ──
    @staticmethod
    def get_cash_flow_statement(ledger_id, year, month):
        from database_v3 import get_cash_flow_statement
        return get_cash_flow_statement(ledger_id, year, month)

    @staticmethod
    def get_cash_flow_categories(ledger_id):
        from database_v3 import get_cash_flow_categories
        return get_cash_flow_categories(ledger_id)

    @staticmethod
    def add_cash_flow_category(ledger_id, name, flow_type):
        from database_v3 import add_cash_flow_category
        return add_cash_flow_category(ledger_id, name, flow_type)

    # ── 期间对比（暂保留旧实现） ──
    @staticmethod
    def get_period_compare_income(ledger_id, year, month):
        from database_v3 import get_period_compare_income
        return get_period_compare_income(ledger_id, year, month)

    @staticmethod
    def get_period_compare_balance(ledger_id, year, month):
        from database_v3 import get_period_compare_balance
        return get_period_compare_balance(ledger_id, year, month)

    # ── Dashboard 指标 ──
    @staticmethod
    def get_dashboard_kpi(ledger_id, year, month):
        from database_v3 import get_dashboard_kpi
        return get_dashboard_kpi(ledger_id, year, month)

    @staticmethod
    def get_monthly_trend(ledger_id, months=6):
        return _run(_report_repo.get_monthly_trend(ledger_id, months=months))

    @staticmethod
    def get_expense_breakdown(ledger_id, year, month):
        from database_v3 import get_expense_breakdown
        return get_expense_breakdown(ledger_id, year, month)

    # ── 预算汇总（委托给 BudgetService） ──
    @staticmethod
    def get_budgets(ledger_id, year=None):
        return BudgetService.get_all(ledger_id, year)

    @staticmethod
    def set_budget(ledger_id, account_code, year, month, amount):
        return BudgetService.set(ledger_id, account_code, None, year, month, amount)

    @staticmethod
    def get_budget_execution(ledger_id, year, month):
        return BudgetService.get_execution(ledger_id, year, month)

    @staticmethod
    def get_budget_summary(ledger_id, year):
        return BudgetService.get_summary(ledger_id, year)

    # ── 发票 ──
    @staticmethod
    def get_invoices(ledger_id, **kwargs):
        return _run(_invoice_repo.get_by_ledger(ledger_id, **kwargs))

    @staticmethod
    def add_invoice(ledger_id, **kwargs):
        return _run(_invoice_repo.create(ledger_id=ledger_id, **kwargs))

    @staticmethod
    def link_invoice_voucher(ledger_id, invoice_id, voucher_no):
        from database_v3 import link_invoice_voucher
        return link_invoice_voucher(ledger_id, invoice_id, voucher_no)

    @staticmethod
    def get_invoice_vouchers(ledger_id, invoice_id):
        from database_v3 import get_invoice_vouchers
        return get_invoice_vouchers(ledger_id, invoice_id)

    @staticmethod
    def get_invoice_summary(ledger_id, year=None, month=None):
        from database_v3 import get_invoice_summary
        return get_invoice_summary(ledger_id)

    @staticmethod
    def ocr_recognize_invoice(file_path):
        from database_v3 import ocr_recognize_invoice
        return ocr_recognize_invoice(file_path)

    # ── CSV/PDF 导出（暂保留旧实现） ──
    @staticmethod
    def export_balance_sheet_csv(ledger_id, year, month, filepath):
        from database_v3 import export_balance_sheet_csv
        return export_balance_sheet_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_income_statement_csv(ledger_id, year, month, filepath):
        from database_v3 import export_income_statement_csv
        return export_income_statement_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_account_balances_csv(ledger_id, year, month, filepath):
        from database_v3 import export_account_balances_csv
        return export_account_balances_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_vouchers_csv(ledger_id, year, month, filepath):
        from database_v3 import export_vouchers_csv
        return export_vouchers_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_balance_sheet_pdf(ledger_id, year, month, filepath):
        from database_v3 import export_balance_sheet_pdf
        return export_balance_sheet_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_income_statement_pdf(ledger_id, year, month, filepath):
        from database_v3 import export_income_statement_pdf
        return export_income_statement_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_account_balances_pdf(ledger_id, year, month, filepath):
        from database_v3 import export_account_balances_pdf
        return export_account_balances_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_vouchers_pdf(ledger_id, year, month, filepath):
        from database_v3 import export_vouchers_pdf
        return export_vouchers_pdf(ledger_id, year, month, filepath)
