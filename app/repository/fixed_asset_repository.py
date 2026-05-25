"""Fixed asset repository."""
import math
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

    async def calculate_depreciation(self, asset_id: int, year: int, month: int) -> int:
        """Calculate monthly depreciation amount for a single asset (in cents/fen).

        Supports: straight_line, double_declining, sum_of_years.
        Returns integer amount (same unit as original_value, e.g. fen).
        """
        async with get_db() as session:
            asset = await session.get(FixedAsset, asset_id)
            if not asset or asset.status != "in_use":
                return 0

            remaining = asset.original_value - asset.accumulated_depreciation
            residual = asset.residual_value
            if remaining <= residual:
                return 0

            method = asset.depreciation_method
            original = asset.original_value
            life_months = asset.useful_life_months
            depreciable_base = original - residual

            if method == "straight_line":
                monthly = depreciable_base / life_months
            elif method == "double_declining":
                if depreciable_base > 0:
                    monthly_sl = depreciable_base / life_months
                    months_used = asset.accumulated_depreciation / monthly_sl
                else:
                    months_used = 0
                remaining_life = life_months - months_used
                if remaining_life <= 24:
                    # Switch to straight-line for last 2 years
                    monthly = (remaining - residual) / remaining_life if remaining_life > 0 else 0
                else:
                    monthly = remaining * (2.0 / life_months)
            elif method == "sum_of_years":
                total_years = life_months / 12
                sum_years = total_years * (total_years + 1) / 2
                if depreciable_base > 0:
                    monthly_sl = depreciable_base / life_months
                    months_used = asset.accumulated_depreciation / monthly_sl
                else:
                    months_used = 0
                current_year = int(months_used / 12) + 1
                remaining_years = total_years - current_year + 1
                monthly = depreciable_base * (remaining_years / sum_years) / 12
            else:
                monthly = depreciable_base / life_months

            # Cap at remaining depreciable amount
            depreciable = remaining - residual
            monthly = min(monthly, depreciable)
            return int(round(monthly))

    async def batch_calculate_depreciation(self, ledger_id: int, year: int, month: int) -> list:
        """Batch calculate depreciation for all in-use assets.

        Returns list of (asset_id, amount) tuples where amount > 0.
        Depreciation is computed in-memory after fetching assets — no per-asset DB query.
        """
        assets = await self.get_by_ledger(ledger_id, status="in_use")
        results = []
        for asset in assets:
            amount = _calc_depreciation(asset, year, month)
            if amount > 0:
                results.append((asset.id, amount))
        return results


def _calc_depreciation(asset, year: int, month: int) -> int:
    """Pure in-memory depreciation calculation — mirrors FixedAssetRepository.calculate_depreciation
    but reads from the already-fetched asset object instead of hitting the DB."""
    if not asset or asset.status != "in_use":
        return 0

    remaining = asset.original_value - asset.accumulated_depreciation
    residual = asset.residual_value
    if remaining <= residual:
        return 0

    method = asset.depreciation_method
    original = asset.original_value
    life_months = asset.useful_life_months
    depreciable_base = original - residual

    if method == "straight_line":
        monthly = depreciable_base / life_months
    elif method == "double_declining":
        if depreciable_base > 0:
            monthly_sl = depreciable_base / life_months
            months_used = asset.accumulated_depreciation / monthly_sl
        else:
            months_used = 0
        remaining_life = life_months - months_used
        if remaining_life <= 24:
            monthly = (remaining - residual) / remaining_life if remaining_life > 0 else 0
        else:
            monthly = remaining * (2.0 / life_months)
    elif method == "sum_of_years":
        total_years = life_months / 12
        sum_years = total_years * (total_years + 1) / 2
        if depreciable_base > 0:
            monthly_sl = depreciable_base / life_months
            months_used = asset.accumulated_depreciation / monthly_sl
        else:
            months_used = 0
        current_year = int(months_used / 12) + 1
        remaining_years = total_years - current_year + 1
        monthly = depreciable_base * (remaining_years / sum_years) / 12
    else:
        monthly = depreciable_base / life_months

    depreciable = remaining - residual
    monthly = min(monthly, depreciable)
    return int(round(monthly))
