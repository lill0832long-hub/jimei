"""税务服务层 — 使用 Repository 模式"""
import asyncio
from app.repository.tax_repository import TaxRepository

_tax_repo = TaxRepository()


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


class TaxService:
    """税务管理"""

    @staticmethod
    def get_config(ledger_id):
        return _run(_tax_repo.get_config(ledger_id))

    @staticmethod
    def set_config(ledger_id, taxpayer_type="general", default_tax_rate=0.13):
        return _run(_tax_repo.set_config(ledger_id, taxpayer_type=taxpayer_type, default_tax_rate=default_tax_rate))

    @staticmethod
    def get_rates(ledger_id):
        return _run(_tax_repo.get_rates(ledger_id))

    @staticmethod
    def add_rate(ledger_id, rate, name, description="", is_default=0):
        return _run(_tax_repo.add_rate(ledger_id, rate, name, description=description, is_default=is_default))

    @staticmethod
    def get_summary(ledger_id, year, month):
        # TODO: migrate to repository pattern
        from database.tax import get_tax_summary
        return get_tax_summary(ledger_id, year, month)

    @staticmethod
    def get_detail(ledger_id, year, month):
        # TODO: migrate to repository pattern
        from database.tax import get_tax_detail
        return get_tax_detail(ledger_id, year, month)
