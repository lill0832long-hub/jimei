"""固定资产服务层 — 使用 Repository 模式"""
from app.services._utils import run_async
from app.repository.fixed_asset_repository import FixedAssetRepository

_fa_repo = FixedAssetRepository()


class FixedAssetService:
    """固定资产管理"""

    @staticmethod
    def get_all(ledger_id, status=None):
        return run_async(_fa_repo.get_by_ledger(ledger_id, status=status))

    @staticmethod
    def get_by_id(asset_id):
        return run_async(_fa_repo.get_by_id(asset_id))

    @staticmethod
    def create(ledger_id, asset_code, asset_name, original_value,
               useful_life_months, **kwargs):
        return run_async(_fa_repo.create(
            ledger_id=ledger_id, asset_code=asset_code,
            asset_name=asset_name, original_value=original_value,
            useful_life_months=useful_life_months, **kwargs,
        ))

    @staticmethod
    def dispose(asset_id, dispose_type, proceeds=0):
        return run_async(_fa_repo.dispose(asset_id, dispose_type, proceeds=proceeds))

    # ── 折旧计算（业务逻辑，保留在服务层） ──

    @staticmethod
    def calculate_depreciation(asset_id, year, month):
        """计算单资产月折旧额"""
        # TODO: migrate to repository pattern
        from database.fixed_asset import calculate_depreciation
        return calculate_depreciation(asset_id, year, month)

    @staticmethod
    def batch_calculate_depreciation(ledger_id, year, month):
        """批量计提折旧"""
        # TODO: migrate to repository pattern
        from database.fixed_asset import batch_calculate_depreciation
        return batch_calculate_depreciation(ledger_id, year, month)
