"""税务服务层 — 使用 Repository 模式"""
from app.services._utils import run_async, to_dict
from app.repository.tax_repository import TaxRepository

_tax_repo = TaxRepository()


class TaxService:
    """税务管理"""

    @staticmethod
    def get_config(ledger_id):
        return to_dict(run_async(_tax_repo.get_config(ledger_id)))

    @staticmethod
    def set_config(ledger_id, taxpayer_type="general", default_tax_rate=0.13):
        return to_dict(run_async(_tax_repo.set_config(ledger_id, taxpayer_type=taxpayer_type, default_tax_rate=default_tax_rate)))

    @staticmethod
    def get_rates(ledger_id):
        return to_dict(run_async(_tax_repo.get_rates(ledger_id)))

    @staticmethod
    def add_rate(ledger_id, rate, name, description="", is_default=0):
        return run_async(_tax_repo.add_rate(ledger_id, rate, name, description=description, is_default=is_default))

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
