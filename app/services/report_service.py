"""报表服务层 — 封装 database_v3 的报表相关操作"""
from database_v3 import (
    get_account_balances, get_balance_sheet, get_income_statement,
    export_balance_sheet_csv, export_income_statement_csv,
    export_account_balances_csv, export_vouchers_csv,
    export_balance_sheet_pdf, export_income_statement_pdf,
    export_account_balances_pdf, export_vouchers_pdf,
    get_period_compare_income, get_period_compare_balance
)


class ReportService:
    """报表生成"""

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
    def get_period_compare_income(ledger_id, year, month):
        return get_period_compare_income(ledger_id, year, month)

    @staticmethod
    def get_period_compare_balance(ledger_id, year, month):
        return get_period_compare_balance(ledger_id, year, month)

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
