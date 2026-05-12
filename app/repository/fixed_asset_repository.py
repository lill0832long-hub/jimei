"""Fixed asset repository."""
from sqlalchemy import select, and_, func
from app.models.fixed_asset import FixedAsset, FaChange
from app.models.fa_category import FaCategory
from app.models.base import get_db
from .base import BaseRepository


class FixedAssetRepository(BaseRepository):
    """固定资产管理"""

    model = FixedAsset

    async def get_by_ledger(self, ledger_id: int, status: str = None):
        async with get_db() as session:
            stmt = select(FixedAsset).where(FixedAsset.ledger_id == ledger_id)
            if status:
                stmt = stmt.where(FixedAsset.status == status)
            stmt = stmt.order_by(FixedAsset.asset_code)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_by_id(self, asset_id: int):
        async with get_db() as session:
            return await session.get(FixedAsset, asset_id)

    async def create(self, ledger_id: int, asset_code: str, asset_name: str,
                     original_value: int, useful_life_months: int, **kwargs):
        async with get_db() as session:
            residual_rate = kwargs.get("residual_rate", 0.05)
            residual_value = int(original_value * residual_rate)
            asset = FixedAsset(
                ledger_id=ledger_id,
                asset_code=asset_code,
                asset_name=asset_name,
                original_value=original_value,
                residual_rate=residual_rate,
                residual_value=residual_value,
                useful_life_months=useful_life_months,
                accumulated_depreciation=0,
                net_value=original_value,
                status="in_use",
                **kwargs,
            )
            session.add(asset)
            await session.flush()
            await session.refresh(asset)
            return asset

    async def dispose(self, asset_id: int, dispose_type: str, proceeds: int = 0):
        async with get_db() as session:
            asset = await session.get(FixedAsset, asset_id)
            if not asset:
                return None
            net_value = asset.original_value - asset.accumulated_depreciation
            gain_loss = proceeds - net_value
            asset.status = "disposed"
            asset.net_value = 0
            change = FaChange(
                asset_id=asset_id,
                change_type=f"dispose_{dispose_type}",
                old_value=net_value,
                new_value=0,
                reason=f"处置方式:{dispose_type}, 收入:{proceeds}",
            )
            session.add(change)
            await session.flush()
            return {
                "asset_id": asset_id,
                "original_value": asset.original_value,
                "accumulated_depreciation": asset.accumulated_depreciation,
                "net_value": net_value,
                "proceeds": proceeds,
                "gain_loss": gain_loss,
            }
