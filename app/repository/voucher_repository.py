"""Voucher repository."""
from sqlalchemy import select, and_, or_, func
from app.models.voucher import Voucher, JournalEntry
from app.models.voucher_workflow import VoucherWorkflow
from app.models.base import get_db
from .base import BaseRepository


class VoucherRepository(BaseRepository):
    model = Voucher

    async def get_by_no(self, ledger_id: int, voucher_no: str):
        async with get_db() as session:
            stmt = select(Voucher).where(
                and_(Voucher.ledger_id == ledger_id, Voucher.voucher_no == voucher_no)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_with_entries(self, ledger_id: int, voucher_no: str):
        """Get voucher with its journal entries."""
        async with get_db() as session:
            stmt = select(Voucher).where(
                and_(Voucher.ledger_id == ledger_id, Voucher.voucher_no == voucher_no)
            )
            result = await session.execute(stmt)
            voucher = result.scalar_one_or_none()
            if voucher:
                await session.refresh(voucher, ["journal_entries"])
            return voucher

    async def get_all(self, ledger_id: int, year: int = None, month: int = None, status: str = None, limit: int = 100):
        async with get_db() as session:
            stmt = select(Voucher).where(Voucher.ledger_id == ledger_id)
            if year is not None:
                date_prefix = f"{year:04d}"
                if month is not None:
                    date_prefix = f"{year:04d}-{month:02d}"
                stmt = stmt.where(Voucher.date.like(f"{date_prefix}%"))
            if status:
                stmt = stmt.where(Voucher.status == status)
            stmt = stmt.order_by(Voucher.date.desc(), Voucher.voucher_no.desc()).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create_with_entries(self, ledger_id: int, date: str, description: str, entries: list, status: str = "draft", voucher_no: str = None, **kwargs):
        """Create a voucher with its journal entries in one transaction."""
        async with get_db() as session:
            # Generate voucher number if not provided
            if not voucher_no:
                voucher_no = await self._generate_voucher_no(session, ledger_id, date)

            total_debit = sum(float(e.get("debit", 0) or 0) for e in entries)
            total_credit = sum(float(e.get("credit", 0) or 0) for e in entries)

            voucher = Voucher(
                ledger_id=ledger_id,
                voucher_no=voucher_no,
                date=date,
                description=description,
                total_debit=total_debit,
                total_credit=total_credit,
                status=status,
                **kwargs,
            )
            session.add(voucher)
            await session.flush()

            for entry_data in entries:
                entry = JournalEntry(
                    ledger_id=ledger_id,
                    voucher_id=voucher.id,
                    account_code=entry_data["account_code"],
                    account_name=entry_data["account_name"],
                    debit=float(entry_data.get("debit", 0) or 0),
                    credit=float(entry_data.get("credit", 0) or 0),
                    summary=entry_data.get("summary", ""),
                )
                session.add(entry)

            await session.flush()
            await session.refresh(voucher)
            return voucher

    async def _generate_voucher_no(self, session, ledger_id: int, date: str) -> str:
        """Generate next voucher number per ledger using sequential numbering."""
        stmt = select(func.count(Voucher.id)).where(Voucher.ledger_id == ledger_id)
        result = await session.execute(stmt)
        count = result.scalar() or 0
        seq = count + 1
        return f"PZ{ledger_id:02d}{seq:06d}"

    async def update(self, voucher_no: str, **kwargs):
        async with get_db() as session:
            stmt = select(Voucher).where(Voucher.voucher_no == voucher_no)
            result = await session.execute(stmt)
            voucher = result.scalar_one_or_none()
            if voucher:
                entries_data = kwargs.pop("entries", None)
                for k, v in kwargs.items():
                    setattr(voucher, k, v)
                if entries_data is not None:
                    # Delete existing entries and recreate
                    for old_entry in list(voucher.journal_entries):
                        await session.delete(old_entry)
                    for entry_data in entries_data:
                        entry = JournalEntry(
                            ledger_id=voucher.ledger_id,
                            voucher_id=voucher.id,
                            account_code=entry_data["account_code"],
                            account_name=entry_data["account_name"],
                            debit=float(entry_data.get("debit", 0) or 0),
                            credit=float(entry_data.get("credit", 0) or 0),
                            summary=entry_data.get("summary", ""),
                        )
                        session.add(entry)
                    voucher.total_debit = sum(float(e.get("debit", 0) or 0) for e in entries_data)
                    voucher.total_credit = sum(float(e.get("credit", 0) or 0) for e in entries_data)
            return voucher

    async def delete(self, voucher_no: str) -> bool:
        async with get_db() as session:
            stmt = select(Voucher).where(Voucher.voucher_no == voucher_no)
            result = await session.execute(stmt)
            voucher = result.scalar_one_or_none()
            if voucher:
                await session.delete(voucher)
                return True
            return False

    async def search(self, ledger_id: int, keyword: str = None, **kwargs):
        async with get_db() as session:
            stmt = select(Voucher).where(Voucher.ledger_id == ledger_id)
            if keyword:
                stmt = stmt.where(
                    or_(
                        Voucher.description.contains(keyword),
                        Voucher.voucher_no.contains(keyword),
                    )
                )
            for k, v in kwargs.items():
                if hasattr(Voucher, k) and v is not None:
                    stmt = stmt.where(getattr(Voucher, k) == v)
            stmt = stmt.order_by(Voucher.date.desc()).limit(50)
            result = await session.execute(stmt)
            return result.scalars().all()

    # -- Workflow operations --

    async def add_workflow(self, voucher_id: int, ledger_id: int, action: str, to_status: str, from_status: str = None, user_id: int = None, comment: str = ""):
        async with get_db() as session:
            wf = VoucherWorkflow(
                voucher_id=voucher_id,
                ledger_id=ledger_id,
                action=action,
                from_status=from_status,
                to_status=to_status,
                user_id=user_id,
                comment=comment,
            )
            session.add(wf)
            await session.flush()
            return wf

    async def update_status(self, voucher_no: str, new_status: str, user_id: int = None, action: str = None, comment: str = ""):
        async with get_db() as session:
            stmt = select(Voucher).where(Voucher.voucher_no == voucher_no)
            result = await session.execute(stmt)
            voucher = result.scalar_one_or_none()
            if voucher:
                old_status = voucher.status
                voucher.status = new_status
                if action:
                    await self.add_workflow(
                        voucher_id=voucher.id,
                        ledger_id=voucher.ledger_id,
                        action=action,
                        to_status=new_status,
                        from_status=old_status,
                        user_id=user_id,
                        comment=comment,
                    )
            return voucher

    async def get_entries(self, voucher_id: int):
        async with get_db() as session:
            stmt = select(JournalEntry).where(JournalEntry.voucher_id == voucher_id)
            result = await session.execute(stmt)
            return result.scalars().all()
