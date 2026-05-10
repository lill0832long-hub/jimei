"""税务服务层 — 封装 database_v3 的税务相关操作"""
from database_v3 import (
    get_tax_config, set_tax_config, get_tax_rates, add_tax_rate,
    get_tax_summary, get_tax_detail,
)


class TaxService:
    """税务管理"""

    @staticmethod
    def get_config(ledger_id):
        return get_tax_config(ledger_id)

    @staticmethod
    def set_config(ledger_id, taxpayer_type="general", default_tax_rate=0.13):
        return set_tax_config(ledger_id, taxpayer_type=taxpayer_type, default_tax_rate=default_tax_rate)

    @staticmethod
    def get_rates(ledger_id):
        return get_tax_rates(ledger_id)

    @staticmethod
    def add_rate(ledger_id, rate, name, description="", is_default=0):
        return add_tax_rate(ledger_id, rate, name, description=description, is_default=is_default)

    @staticmethod
    def get_summary(ledger_id, year, month):
        return get_tax_summary(ledger_id, year, month)

    @staticmethod
    def get_detail(ledger_id, year, month):
        return get_tax_detail(ledger_id, year, month)
