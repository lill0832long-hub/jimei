"""账套服务层 — 封装 database_v3 的账套/期间/科目初始化相关操作"""
from database_v3 import (
    create_ledger, get_ledgers, get_ledger, update_ledger, delete_ledger,
    set_opening_balance, get_opening_balance,
    get_period_status, close_period, reverse_close_period,
)
from app.services.account_service import AccountService


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

    # ── 期间管理 ──
    @staticmethod
    def get_period_status(ledger_id, year, month):
        return get_period_status(ledger_id, year, month)

    @staticmethod
    def close_period(ledger_id, year, month, user_id=None):
        return close_period(ledger_id, year, month, user_id)

    @staticmethod
    def reverse_close_period(ledger_id, year, month):
        return reverse_close_period(ledger_id, year, month)

    # ── 科目初始化（委托给 AccountService） ──
    @staticmethod
    def get_default_accounts():
        return AccountService.get_defaults()

    @staticmethod
    def import_accounts_from_template(ledger_id, template_name):
        return AccountService.import_from_template(ledger_id, template_name)
