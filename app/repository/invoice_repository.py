"""Invoice repository."""
from sqlalchemy import select, and_
from app.models.invoice import Invoice, InvoiceVoucher
from app.models.base import get_db
from .base import BaseRepository


class InvoiceRepository(BaseRepository):
    model = Invoice

    async def get_by_ledger(self, ledger_id: int, status: str = None, limit: int = 100):
        async with get_db() as session:
            stmt = select(Invoice).where(Invoice.ledger_id == ledger_id)
            if status:
                stmt = stmt.where(Invoice.status == status)
            stmt = stmt.order_by(Invoice.invoice_date.desc()).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create(self, ledger_id: int, **kwargs):
        async with get_db() as session:
            inv = Invoice(ledger_id=ledger_id, **kwargs)
            session.add(inv)
            await session.flush()
            await session.refresh(inv)
            return inv

    async def link_voucher(self, invoice_id: int, voucher_id: int, ledger_id: int):
        async with get_db() as session:
            link = InvoiceVoucher(
                invoice_id=invoice_id, voucher_id=voucher_id, ledger_id=ledger_id,
            )
            session.add(link)
            await session.flush()
            return link

    async def get_voucher_links(self, invoice_id: int):
        async with get_db() as session:
            stmt = select(InvoiceVoucher).where(InvoiceVoucher.invoice_id == invoice_id)
            result = await session.execute(stmt)
            return result.scalars().all()
