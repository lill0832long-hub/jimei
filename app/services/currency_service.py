"""币种服务层 — 使用 Repository 模式"""
import asyncio
from app.repository.currency_repository import CurrencyRepository, ExchangeRateRepository

_currency_repo = CurrencyRepository()
_rate_repo = ExchangeRateRepository()


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


def _to_dict(obj):
    """Convert SQLAlchemy model instance(s) to dict(s)."""
    if obj is None:
        return None
    if isinstance(obj, (list, tuple)):
        return [_to_dict(item) for item in obj]
    if hasattr(obj, "__table__"):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    if isinstance(obj, dict):
        return obj
    return obj


class CurrencyService:
    """币种与汇率管理"""

    @staticmethod
    def get_all(active_only=True):
        return _to_dict(_run(_currency_repo.get_all(active_only=active_only)))

    @staticmethod
    def get_by_code(code):
        return _to_dict(_run(_currency_repo.get_by_code(code)))

    @staticmethod
    def get_active_codes():
        return _to_dict(_run(_currency_repo.get_active_codes()))

    @staticmethod
    def create_currency(code, name, symbol=""):
        return _to_dict(_run(_currency_repo.create_currency(code, name, symbol)))

    @staticmethod
    def get_exchange_rate(from_currency, to_currency):
        return _to_dict(_run(_rate_repo.get_latest(from_currency, to_currency)))

    @staticmethod
    def get_all_rates(base_currency=None):
        return _to_dict(_run(_rate_repo.get_all_rates(base_currency=base_currency)))

    @staticmethod
    def get_all_rates_with_currency(limit=50):
        return _to_dict(_run(_rate_repo.get_all_rates_with_currency(limit=limit)))

    @staticmethod
    def add_rate(from_currency, to_currency, rate, date=None):
        return _to_dict(_run(_rate_repo.add_rate(from_currency, to_currency, rate, date)))
