"""Invoice repository."""
from sqlalchemy import select, and_
from app.models.invoice import Invoice, InvoiceVoucher
from app.models.base import get_db
from .base import BaseRepository


class InvoiceRepository(BaseRepository):
    model = Invoice

    async def get_by_ledger(self, ledger_id: int, status: str = None, invoice_type: str = None, limit: int = 100):
        async with get_db() as session:
            stmt = select(Invoice).where(Invoice.ledger_id == ledger_id)
            if status:
                stmt = stmt.where(Invoice.status == status)
            if invoice_type:
                stmt = stmt.where(Invoice.invoice_type == invoice_type)
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

    async def link_voucher(self, ledger_id: int, invoice_id: int, voucher_no: str):
        """Link an invoice to a voucher by voucher_no. Returns True if successful."""
        from app.models.voucher import Voucher
        async with get_db() as session:
            # Find the voucher by ledger_id + voucher_no
            v_stmt = select(Voucher).where(
                Voucher.ledger_id == ledger_id,
                Voucher.voucher_no == voucher_no,
            )
            v_result = await session.execute(v_stmt)
            voucher = v_result.scalar_one_or_none()
            if not voucher:
                return False
            # Check if link already exists
            existing = await session.execute(
                select(InvoiceVoucher).where(
                    InvoiceVoucher.invoice_id == invoice_id,
                    InvoiceVoucher.voucher_id == voucher.id,
                )
            )
            if existing.scalar_one_or_none():
                return True  # already linked
            link = InvoiceVoucher(
                invoice_id=invoice_id, voucher_id=voucher.id, ledger_id=ledger_id,
            )
            session.add(link)
            await session.flush()
            return True

    async def get_vouchers(self, ledger_id: int, invoice_id: int):
        """Get all voucher links for an invoice, returning voucher details."""
        from app.models.voucher import Voucher
        async with get_db() as session:
            stmt = select(Voucher, InvoiceVoucher).join(
                InvoiceVoucher, InvoiceVoucher.voucher_id == Voucher.id
            ).where(
                InvoiceVoucher.invoice_id == invoice_id,
                InvoiceVoucher.ledger_id == ledger_id,
            )
            result = await session.execute(stmt)
            rows = result.all()
            return [{
                "invoice_id": iv.invoice_id,
                "voucher_id": v.id,
                "voucher_no": v.voucher_no,
                "date": v.date,
                "description": v.description,
                "total_debit": v.total_debit,
                "total_credit": v.total_credit,
                "status": v.status,
            } for v, iv in rows]

    async def get_summary(self, ledger_id: int, year: int = None, month: int = None):
        """Get invoice summary: total count, total amount, by status."""
        from sqlalchemy import func, extract
        async with get_db() as session:
            stmt = select(
                Invoice.status,
                func.count().label("count"),
                func.coalesce(func.sum(Invoice.total_with_tax), 0).label("total"),
            ).where(Invoice.ledger_id == ledger_id)
            if year is not None:
                stmt = stmt.where(func.strftime("%Y", Invoice.invoice_date) == str(year))
            if month is not None:
                stmt = stmt.where(func.strftime("%m", Invoice.invoice_date) == f"{month:02d}")
            stmt = stmt.group_by(Invoice.status)
            result = await session.execute(stmt)
            rows = result.all()
            return [{
                "status": r.status,
                "count": r.count,
                "total": r.total,
            } for r in rows]
