"""Tax repository."""
from sqlalchemy import select, and_
from app.models.tax import TaxConfig, TaxRate
from app.models.base import get_db
from .base import BaseRepository


class TaxRepository(BaseRepository):
    model = TaxConfig

    async def get_config(self, ledger_id: int):
        async with get_db() as session:
            stmt = select(TaxConfig).where(
                and_(TaxConfig.ledger_id == ledger_id, TaxConfig.is_active == 1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def set_config(self, ledger_id: int, taxpayer_type: str = "general", default_tax_rate: float = 0.13):
        async with get_db() as session:
            config = await self.get_config(ledger_id)
            if config:
                config.taxpayer_type = taxpayer_type
                config.default_tax_rate = default_tax_rate
                return config
            config = TaxConfig(
                ledger_id=ledger_id,
                taxpayer_type=taxpayer_type,
                default_tax_rate=default_tax_rate,
            )
            session.add(config)
            await session.flush()
            await session.refresh(config)
            return config

    async def get_rates(self, ledger_id: int):
        async with get_db() as session:
            stmt = select(TaxRate).where(
                and_(TaxRate.ledger_id == ledger_id, TaxRate.is_active == 1)
            ).order_by(TaxRate.rate)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def add_rate(self, ledger_id: int, rate: float, name: str, description: str = "", is_default: int = 0):
        async with get_db() as session:
            tr = TaxRate(
                ledger_id=ledger_id, rate=rate, name=name,
                description=description, is_default=is_default,
            )
            session.add(tr)
            await session.flush()
            await session.refresh(tr)
            return tr
