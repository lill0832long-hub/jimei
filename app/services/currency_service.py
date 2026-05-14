"""币种服务层 — 使用 Repository 模式"""
from app.services._utils import run_async, to_dict
from app.repository.currency_repository import CurrencyRepository, ExchangeRateRepository

_currency_repo = CurrencyRepository()
_rate_repo = ExchangeRateRepository()


class CurrencyService:
    """币种与汇率管理"""

    @staticmethod
    def get_all(active_only=True):
        return to_dict(run_async(_currency_repo.get_all(active_only=active_only)))

    @staticmethod
    def get_by_code(code):
        return to_dict(run_async(_currency_repo.get_by_code(code)))

    @staticmethod
    def get_active_codes():
        return to_dict(run_async(_currency_repo.get_active_codes()))

    @staticmethod
    def create_currency(code, name, symbol=""):
        return to_dict(run_async(_currency_repo.create_currency(code, name, symbol)))

    @staticmethod
    def get_exchange_rate(from_currency, to_currency):
        return to_dict(run_async(_rate_repo.get_latest(from_currency, to_currency)))

    @staticmethod
    def get_all_rates(base_currency=None):
        return to_dict(run_async(_rate_repo.get_all_rates(base_currency=base_currency)))

    @staticmethod
    def get_all_rates_with_currency(limit=50):
        return to_dict(run_async(_rate_repo.get_all_rates_with_currency(limit=limit)))

    @staticmethod
    def add_rate(from_currency, to_currency, rate, date=None):
        return to_dict(run_async(_rate_repo.add_rate(from_currency, to_currency, rate, date)))
