"""预算服务层 — 使用 Repository 模式"""
from app.services._utils import run_async, to_dict
from app.repository.budget_repository import BudgetRepository

_budget_repo = BudgetRepository()


class BudgetService:
    """预算管理"""

    @staticmethod
    def get_all(ledger_id, year=None, month=None):
        return to_dict(run_async(_budget_repo.get_by_ledger(ledger_id, year=year, month=month)))

    @staticmethod
    def set(ledger_id, account_code, account_name, year, month, amount, description=""):
        return to_dict(run_async(_budget_repo.set_budget(ledger_id, account_code, account_name, year, month, amount, description)))

    @staticmethod
    def get_execution(ledger_id, year, month):
        return to_dict(run_async(_budget_repo.get_execution(ledger_id, year, month)))

    @staticmethod
    def get_summary(ledger_id, year, month=None):
        return to_dict(run_async(_budget_repo.get_summary(ledger_id, year, month)))

    @staticmethod
    def check_exceeded(ledger_id, account_code, year, month, amount):
        return to_dict(run_async(_budget_repo.check_exceeded(ledger_id, account_code, year, month, amount)))
