"""账套服务层 — 使用 Repository 模式"""
from app.services._utils import run_async, to_dict
from app.repository.ledger_repository import LedgerRepository
from app.repository.period_repository import PeriodRepository
from app.services.account_service import AccountService

_ledger_repo = LedgerRepository()
_period_repo = PeriodRepository()


class LedgerService:
    """账套管理"""

    @staticmethod
    def create(name, company="默认公司", currency="CNY", fiscal_start=None, fiscal_end=None, settings=None):
        kwargs = {}
        if fiscal_start is not None:
            kwargs["fiscal_year_start"] = fiscal_start
        if fiscal_end is not None:
            kwargs["fiscal_year_end"] = fiscal_end
        if settings is not None:
            kwargs["settings"] = settings
        return run_async(_ledger_repo.create(
            name=name, company=company, currency=currency, **kwargs,
        ))

    @staticmethod
    def get_all():
        return to_dict(run_async(_ledger_repo.get_all()))

    @staticmethod
    def get_by_id(ledger_id):
        return to_dict(run_async(_ledger_repo.get_by_id(ledger_id)))

    @staticmethod
    def update(ledger_id, **kwargs):
        return run_async(_ledger_repo.update(ledger_id, **kwargs))

    @staticmethod
    def delete(ledger_id):
        return run_async(_ledger_repo.delete(ledger_id))

    @staticmethod
    def set_opening_balance(ledger_id, account_code, year, month, balance):
        return run_async(_period_repo.set_opening_balance(ledger_id, account_code, year, month, balance))

    @staticmethod
    def get_opening_balance(ledger_id, account_code, year, month):
        return run_async(_period_repo.get_opening_balance(ledger_id, account_code, year, month))

    # ── 期间管理 ──
    @staticmethod
    def get_period_status(ledger_id, year, month):
        return run_async(_period_repo.get_period_status(ledger_id, year, month))

    @staticmethod
    def close_period(ledger_id, year, month, user_id=None):
        return run_async(_period_repo.close_period(ledger_id, year, month))

    @staticmethod
    def reverse_close_period(ledger_id, year, month):
        return run_async(_period_repo.reverse_close_period(ledger_id, year, month))

    # ── 科目初始化（委托给 AccountService） ──
    @staticmethod
    def get_default_accounts():
        return AccountService.get_defaults()

    @staticmethod
    def import_accounts_from_template(ledger_id, template_name):
        return AccountService.import_from_template(ledger_id, template_name)
