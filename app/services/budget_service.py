"""预算服务层 — 使用 Repository 模式"""
import asyncio
from app.repository.budget_repository import BudgetRepository

_budget_repo = BudgetRepository()


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


class BudgetService:
    """预算管理"""

    @staticmethod
    def get_all(ledger_id, year=None, month=None):
        return _run(_budget_repo.get_by_ledger(ledger_id, year=year, month=month))

    @staticmethod
    def set(ledger_id, account_code, account_name, year, month, amount, description=""):
        return _run(_budget_repo.set_budget(ledger_id, account_code, account_name, year, month, amount, description))

    @staticmethod
    def get_execution(ledger_id, year, month):
        return _run(_budget_repo.get_execution(ledger_id, year, month))

    @staticmethod
    def get_summary(ledger_id, year, month=None):
        return _run(_budget_repo.get_summary(ledger_id, year, month))

    @staticmethod
    def check_exceeded(ledger_id, account_code, year, month, amount):
        return _run(_budget_repo.check_exceeded(ledger_id, account_code, year, month, amount))
