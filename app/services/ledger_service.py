"""账套服务层 — 使用 Repository 模式"""
import asyncio
from app.repository.ledger_repository import LedgerRepository
from app.repository.period_repository import PeriodRepository
from app.services.account_service import AccountService

_ledger_repo = LedgerRepository()
_period_repo = PeriodRepository()


def _run(coro):
    """Run an async coroutine from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _to_dict(obj):
    """Convert a SQLAlchemy model instance to a dict, or None if obj is None."""
    if obj is None:
        return None
    if isinstance(obj, (list, tuple)):
        return [_to_dict(item) for item in obj]
    # SQLAlchemy model instances have __table__
    if hasattr(obj, "__table__"):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    # Already a dict or other mapping
    if isinstance(obj, dict):
        return obj
    return obj


class LedgerService:
    """账套管理"""

    @staticmethod
    def create(name, company="默认公司", currency="CNY", fiscal_start=None, fiscal_end=None, settings=None):
        return _run(_ledger_repo.create(
            name=name, company=company, currency=currency,
            fiscal_start=fiscal_start, fiscal_end=fiscal_end, settings=settings,
        ))

    @staticmethod
    def get_all():
        return _to_dict(_run(_ledger_repo.get_all()))

    @staticmethod
    def get_by_id(ledger_id):
        return _to_dict(_run(_ledger_repo.get_by_id(ledger_id)))

    @staticmethod
    def update(ledger_id, **kwargs):
        return _run(_ledger_repo.update(ledger_id, **kwargs))

    @staticmethod
    def delete(ledger_id):
        return _run(_ledger_repo.delete(ledger_id))

    @staticmethod
    def set_opening_balance(ledger_id, account_code, year, month, balance):
        return _run(_period_repo.set_opening_balance(ledger_id, account_code, year, month, balance))

    @staticmethod
    def get_opening_balance(ledger_id, account_code, year, month):
        return _run(_period_repo.get_opening_balance(ledger_id, account_code, year, month))

    # ── 期间管理 ──
    @staticmethod
    def get_period_status(ledger_id, year, month):
        return _run(_period_repo.get_period_status(ledger_id, year, month))

    @staticmethod
    def close_period(ledger_id, year, month, user_id=None):
        return _run(_period_repo.close_period(ledger_id, year, month))

    @staticmethod
    def reverse_close_period(ledger_id, year, month):
        return _run(_period_repo.reverse_close_period(ledger_id, year, month))

    # ── 科目初始化（委托给 AccountService） ──
    @staticmethod
    def get_default_accounts():
        return AccountService.get_defaults()

    @staticmethod
    def import_accounts_from_template(ledger_id, template_name):
        return AccountService.import_from_template(ledger_id, template_name)
