"""Ledger repository."""
from sqlalchemy import select
from app.models.ledger import Ledger
from app.models.base import get_db
from .base import BaseRepository


class LedgerRepository(BaseRepository):
    model = Ledger

    async def get_all(self):
        async with get_db() as session:
            result = await session.execute(select(Ledger))
            return result.scalars().all()

    async def get_by_id(self, ledger_id: int):
        async with get_db() as session:
            return await session.get(Ledger, ledger_id)

    async def create(self, name, company="默认公司", currency="CNY", **kwargs):
        async with get_db() as session:
            ledger = Ledger(name=name, company=company, currency=currency, **kwargs)
            session.add(ledger)
            await session.flush()
            await session.refresh(ledger)
            return ledger

    async def update(self, ledger_id: int, **kwargs):
        async with get_db() as session:
            ledger = await session.get(Ledger, ledger_id)
            if ledger:
                for k, v in kwargs.items():
                    setattr(ledger, k, v)
            return ledger

    async def delete(self, ledger_id: int) -> bool:
        async with get_db() as session:
            ledger = await session.get(Ledger, ledger_id)
            if ledger:
                await session.delete(ledger)
                return True
            return False
