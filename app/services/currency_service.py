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


class CurrencyService:
    """币种与汇率管理"""

    @staticmethod
    def get_all(active_only=True):
        return _run(_currency_repo.get_all(active_only=active_only))

    @staticmethod
    def get_by_code(code):
        return _run(_currency_repo.get_by_code(code))

    @staticmethod
    def get_active_codes():
        return _run(_currency_repo.get_active_codes())

    @staticmethod
    def create_currency(code, name, symbol=""):
        return _run(_currency_repo.create_currency(code, name, symbol))

    @staticmethod
    def get_exchange_rate(from_currency, to_currency):
        return _run(_rate_repo.get_latest(from_currency, to_currency))

    @staticmethod
    def get_all_rates(base_currency=None):
        return _run(_rate_repo.get_all_rates(base_currency=base_currency))

    @staticmethod
    def get_all_rates_with_currency(limit=50):
        return _run(_rate_repo.get_all_rates_with_currency(limit=limit))

    @staticmethod
    def add_rate(from_currency, to_currency, rate, date=None):
        return _run(_rate_repo.add_rate(from_currency, to_currency, rate, date))
