"""Period management repository."""
from sqlalchemy import select, and_
from app.models.closing_entry import ClosingEntry
from app.models.opening_balance import OpeningBalance
from app.models.base import get_db
from .base import BaseRepository


class PeriodRepository(BaseRepository):
    """期间管理 — opening balances and period closing."""

    async def get_period_status(self, ledger_id: int, year: int, month: int) -> str:
        """Check if a period is closed."""
        period_str = f"{year:04d}-{month:02d}"
        async with get_db() as session:
            stmt = select(ClosingEntry).where(
                and_(
                    ClosingEntry.ledger_id == ledger_id,
                    ClosingEntry.period == period_str,
                    ClosingEntry.status == "completed",
                )
            )
            result = await session.execute(stmt)
            return "closed" if result.first() else "open"

    async def get_opening_balance(self, ledger_id: int, account_code: str, year: int, month: int):
        async with get_db() as session:
            stmt = select(OpeningBalance).where(
                and_(
                    OpeningBalance.ledger_id == ledger_id,
                    OpeningBalance.account_code == account_code,
                    OpeningBalance.year == year,
                    OpeningBalance.month == month,
                )
            )
            result = await session.execute(stmt)
            ob = result.scalar_one_or_none()
            return ob.balance if ob else 0

    async def set_opening_balance(self, ledger_id: int, account_code: str, year: int, month: int, balance: float):
        async with get_db() as session:
            stmt = select(OpeningBalance).where(
                and_(
                    OpeningBalance.ledger_id == ledger_id,
                    OpeningBalance.account_code == account_code,
                    OpeningBalance.year == year,
                    OpeningBalance.month == month,
                )
            )
            result = await session.execute(stmt)
            ob = result.scalar_one_or_none()
            if ob:
                ob.balance = balance
            else:
                ob = OpeningBalance(
                    ledger_id=ledger_id, account_code=account_code,
                    year=year, month=month, balance=balance,
                )
                session.add(ob)
                await session.flush()
            return ob

    async def close_period(self, ledger_id: int, year: int, month: int, voucher_id: int = None):
        """Mark a period as closed."""
        period_str = f"{year:04d}-{month:02d}"
        async with get_db() as session:
            ce = ClosingEntry(
                ledger_id=ledger_id, period=period_str,
                close_type="month_end", voucher_id=voucher_id, status="completed",
            )
            session.add(ce)
            await session.flush()
            return ce

    async def reverse_close_period(self, ledger_id: int, year: int, month: int):
        """Reverse a period close."""
        period_str = f"{year:04d}-{month:02d}"
        async with get_db() as session:
            stmt = select(ClosingEntry).where(
                and_(
                    ClosingEntry.ledger_id == ledger_id,
                    ClosingEntry.period == period_str,
                )
            )
            result = await session.execute(stmt)
            entries = result.scalars().all()
            for e in entries:
                await session.delete(e)
            return True
