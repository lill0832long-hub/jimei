"""Currency and exchange rate repository."""
from sqlalchemy import select, and_
from app.models.currency import Currency
from app.models.exchange_rate import ExchangeRate
from app.models.base import get_db
from .base import BaseRepository


class CurrencyRepository(BaseRepository):
    """币种管理"""

    model = Currency

    async def get_all(self, active_only: bool = True):
        async with get_db() as session:
            stmt = select(Currency)
            if active_only:
                stmt = stmt.where(Currency.is_active == 1)
            stmt = stmt.order_by(Currency.sort_order, Currency.code)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_by_code(self, code: str):
        async with get_db() as session:
            stmt = select(Currency).where(Currency.code == code)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_active_codes(self):
        """Get list of active currency codes."""
        async with get_db() as session:
            stmt = select(Currency.code).where(Currency.is_active == 1).order_by(Currency.code)
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def create_currency(self, code: str, name: str, symbol: str = ""):
        async with get_db() as session:
            currency = Currency(code=code.upper(), name=name, symbol=symbol)
            session.add(currency)
            await session.flush()
            await session.refresh(currency)
            return currency


class ExchangeRateRepository(BaseRepository):
    """汇率管理"""

    model = ExchangeRate

    async def get_latest(self, from_currency: str, to_currency: str):
        async with get_db() as session:
            stmt = select(ExchangeRate).where(
                and_(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                )
            ).order_by(ExchangeRate.date.desc()).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_rates(self, base_currency: str = None):
        async with get_db() as session:
            stmt = select(ExchangeRate)
            if base_currency:
                stmt = stmt.where(ExchangeRate.from_currency == base_currency)
            stmt = stmt.order_by(ExchangeRate.date.desc())
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_all_rates_with_currency(self, limit: int = 50):
        """Get all rates joined with currency info."""
        from app.models.currency import Currency as C
        async with get_db() as session:
            stmt = select(ExchangeRate, C).join(
                C, ExchangeRate.from_currency == C.code, isouter=True
            ).order_by(ExchangeRate.date.desc()).limit(limit)
            result = await session.execute(stmt)
            return result.all()

    async def add_rate(self, from_currency: str, to_currency: str, rate: float, date: str = None):
        from datetime import date as date_type
        async with get_db() as session:
            er = ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                date=date or date_type.today().isoformat(),
            )
            session.add(er)
            await session.flush()
            await session.refresh(er)
            return er
