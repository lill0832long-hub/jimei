"""Tax repository."""
from sqlalchemy import select, and_, func
from app.models.tax import TaxConfig, TaxRate
from app.models.voucher import Voucher, JournalEntry
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

    async def get_tax_summary(self, ledger_id: int, year: int, month: int) -> dict:
        """Get VAT summary (input tax / output tax) for a given period."""
        async with get_db() as session:
            # Input tax: sum of tax_amount where tax_type='input'
            input_stmt = select(
                func.coalesce(func.sum(JournalEntry.tax_amount), 0).label("total_input_tax")
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    Voucher.status == "posted",
                    JournalEntry.tax_type == "input",
                    func.strftime("%Y", Voucher.date) == str(year),
                    func.strftime("%m", Voucher.date) == f"{month:02d}",
                )
            )
            input_result = await session.execute(input_stmt)
            input_tax = input_result.scalar()

            # Output tax: sum of tax_amount where tax_type='output'
            output_stmt = select(
                func.coalesce(func.sum(JournalEntry.tax_amount), 0).label("total_output_tax")
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    Voucher.status == "posted",
                    JournalEntry.tax_type == "output",
                    func.strftime("%Y", Voucher.date) == str(year),
                    func.strftime("%m", Voucher.date) == f"{month:02d}",
                )
            )
            output_result = await session.execute(output_stmt)
            output_tax = output_result.scalar()

            config = await self.get_config(ledger_id)

            return {
                "input_tax": input_tax or 0,
                "output_tax": output_tax or 0,
                "tax_payable": (output_tax or 0) - (input_tax or 0),
                "taxpayer_type": config.taxpayer_type if config else "general",
                "default_rate": config.default_tax_rate if config else 0.13,
            }

    async def get_tax_detail(self, ledger_id: int, year: int, month: int, tax_type: str = "input") -> list:
        """Get detailed tax entries (input or output) for a given period."""
        async with get_db() as session:
            stmt = select(
                JournalEntry.account_code,
                JournalEntry.account_name,
                JournalEntry.tax_rate,
                JournalEntry.tax_amount,
                Voucher.voucher_no,
                Voucher.date,
                Voucher.description,
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    Voucher.status == "posted",
                    JournalEntry.tax_type == tax_type,
                    func.strftime("%Y", Voucher.date) == str(year),
                    func.strftime("%m", Voucher.date) == f"{month:02d}",
                )
            ).order_by(Voucher.date)
            result = await session.execute(stmt)
            rows = result.all()
            return [
                {
                    "account_code": r.account_code,
                    "account_name": r.account_name,
                    "tax_rate": r.tax_rate,
                    "tax_amount": r.tax_amount,
                    "voucher_no": r.voucher_no,
                    "date": r.date,
                    "description": r.description,
                }
                for r in rows
            ]
