"""账套服务层 — 封装 database_v3 的账套相关操作"""
from database_v3 import (
    create_ledger, get_ledgers, get_ledger, update_ledger, delete_ledger,
    set_opening_balance, get_opening_balance
)


class LedgerService:
    """账套管理"""

    @staticmethod
    def create(name, company="默认公司", currency="CNY", fiscal_start=None, fiscal_end=None, settings=None):
        return create_ledger(name, company, currency, fiscal_start, fiscal_end, settings)

    @staticmethod
    def get_all():
        return get_ledgers()

    @staticmethod
    def get_by_id(ledger_id):
        return get_ledger(ledger_id)

    @staticmethod
    def update(ledger_id, **kwargs):
        return update_ledger(ledger_id, **kwargs)

    @staticmethod
    def delete(ledger_id):
        return delete_ledger(ledger_id)

    @staticmethod
    def set_opening_balance(ledger_id, account_code, year, month, balance):
        return set_opening_balance(ledger_id, account_code, year, month, balance)

    @staticmethod
    def get_opening_balance(ledger_id, account_code, year, month):
        return get_opening_balance(ledger_id, account_code, year, month)
