"""预算服务层 — 封装 database_v3 的预算相关操作"""
from database_v3 import (
    get_budgets, set_budget, get_budget_execution, get_budget_summary, check_budget_exceeded,
)


class BudgetService:
    """预算管理"""

    @staticmethod
    def get_all(ledger_id, year=None, month=None):
        return get_budgets(ledger_id, year, month)

    @staticmethod
    def set(ledger_id, account_code, account_name, year, month, amount, description=""):
        return set_budget(ledger_id, account_code, account_name, year, month, amount, description)

    @staticmethod
    def get_execution(ledger_id, year, month):
        return get_budget_execution(ledger_id, year, month)

    @staticmethod
    def get_summary(ledger_id, year, month=None):
        return get_budget_summary(ledger_id, year, month)

    @staticmethod
    def check_exceeded(ledger_id, account_code, amount):
        return check_budget_exceeded(ledger_id, account_code, amount)
