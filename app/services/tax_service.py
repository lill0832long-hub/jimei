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
    def set_config(ledger_id, **kwargs):
        return set_tax_config(ledger_id, **kwargs)

    @staticmethod
    def get_rates(ledger_id):
        return get_tax_rates(ledger_id)

    @staticmethod
    def add_rate(ledger_id, name, rate, **kwargs):
        return add_tax_rate(ledger_id, name, rate, **kwargs)

    @staticmethod
    def get_summary(ledger_id, year, month):
        return get_tax_summary(ledger_id, year, month)

    @staticmethod
    def get_detail(ledger_id, year, month):
        return get_tax_detail(ledger_id, year, month)
