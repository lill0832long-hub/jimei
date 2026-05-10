"""报表服务层 — 封装 database_v3 的报表/现金流/发票/预算汇总相关操作"""
from database_v3 import (
    get_account_balances, get_balance_sheet, get_income_statement,
    export_balance_sheet_csv, export_income_statement_csv,
    export_account_balances_csv, export_vouchers_csv,
    export_balance_sheet_pdf, export_income_statement_pdf,
    export_account_balances_pdf, export_vouchers_pdf,
    get_period_compare_income, get_period_compare_balance,
    get_cash_flow_statement, get_cash_flow_categories, add_cash_flow_category,
    get_invoices, add_invoice, link_invoice_voucher, get_invoice_vouchers, get_invoice_summary,
    get_dashboard_kpi, get_monthly_trend, get_expense_breakdown,
    get_budgets, set_budget, get_budget_execution, get_budget_summary,
)


class ReportService:
    """报表生成"""

    # ── 三大报表 ──
    @staticmethod
    def get_account_balances(ledger_id, year, month):
        return get_account_balances(ledger_id, year, month)

    @staticmethod
    def get_balance_sheet(ledger_id, year, month):
        return get_balance_sheet(ledger_id, year, month)

    @staticmethod
    def get_income_statement(ledger_id, year, month):
        return get_income_statement(ledger_id, year, month)

    @staticmethod
    def get_cash_flow_statement(ledger_id, year, month):
        return get_cash_flow_statement(ledger_id, year, month)

    @staticmethod
    def get_cash_flow_categories(ledger_id):
        return get_cash_flow_categories(ledger_id)

    @staticmethod
    def add_cash_flow_category(ledger_id, name, flow_type):
        return add_cash_flow_category(ledger_id, name, flow_type)

    # ── 期间对比 ──
    @staticmethod
    def get_period_compare_income(ledger_id, year, month):
        return get_period_compare_income(ledger_id, year, month)

    @staticmethod
    def get_period_compare_balance(ledger_id, year, month):
        return get_period_compare_balance(ledger_id, year, month)

    # ── Dashboard 指标 ──
    @staticmethod
    def get_dashboard_kpi(ledger_id, year, month):
        return get_dashboard_kpi(ledger_id, year, month)

    @staticmethod
    def get_monthly_trend(ledger_id, months=6):
        return get_monthly_trend(ledger_id, months)

    @staticmethod
    def get_expense_breakdown(ledger_id, year, month):
        return get_expense_breakdown(ledger_id, year, month)

    # ── 预算汇总 ──
    @staticmethod
    def get_budgets(ledger_id, year=None):
        return get_budgets(ledger_id, year)

    @staticmethod
    def set_budget(ledger_id, account_code, year, month, amount):
        return set_budget(ledger_id, account_code, year, month, amount)

    @staticmethod
    def get_budget_execution(ledger_id, year, month):
        return get_budget_execution(ledger_id, year, month)

    @staticmethod
    def get_budget_summary(ledger_id, year):
        return get_budget_summary(ledger_id, year)

    # ── 发票 ──
    @staticmethod
    def get_invoices(ledger_id, **kwargs):
        return get_invoices(ledger_id, **kwargs)

    @staticmethod
    def add_invoice(ledger_id, **kwargs):
        return add_invoice(ledger_id, **kwargs)

    @staticmethod
    def link_invoice_voucher(ledger_id, invoice_id, voucher_no):
        return link_invoice_voucher(ledger_id, invoice_id, voucher_no)

    @staticmethod
    def get_invoice_vouchers(ledger_id, invoice_id):
        return get_invoice_vouchers(ledger_id, invoice_id)

    @staticmethod
    def get_invoice_summary(ledger_id, year=None, month=None):
        return get_invoice_summary(ledger_id, year, month)

    # ── CSV 导出 ──
    @staticmethod
    def export_balance_sheet_csv(ledger_id, year, month, filepath):
        return export_balance_sheet_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_income_statement_csv(ledger_id, year, month, filepath):
        return export_income_statement_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_account_balances_csv(ledger_id, year, month, filepath):
        return export_account_balances_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_vouchers_csv(ledger_id, year, month, filepath):
        return export_vouchers_csv(ledger_id, year, month, filepath)

    # ── PDF 导出 ──
    @staticmethod
    def export_balance_sheet_pdf(ledger_id, year, month, filepath):
        return export_balance_sheet_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_income_statement_pdf(ledger_id, year, month, filepath):
        return export_income_statement_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_account_balances_pdf(ledger_id, year, month, filepath):
        return export_account_balances_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_vouchers_pdf(ledger_id, year, month, filepath):
        return export_vouchers_pdf(ledger_id, year, month, filepath)
