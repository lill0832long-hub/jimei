"""Voucher repository."""
import json
from sqlalchemy import select, and_, or_, func
from app.models.voucher import Voucher, JournalEntry
from app.models.voucher_workflow import VoucherWorkflow
from app.models.voucher_template import VoucherTemplate
from app.models.scheduled_voucher import ScheduledVoucher
from app.models.invoice import InvoiceVoucher
from app.models.base import get_db
from .base import BaseRepository


class VoucherRepository(BaseRepository):
    model = Voucher

    async def count(self, ledger_id: int, **filters):
        async with get_db() as session:
            stmt = select(func.count(Voucher.id)).where(Voucher.ledger_id == ledger_id)
            if filters.get("status"):
                stmt = stmt.where(Voucher.status == filters["status"])
            if filters.get("year") and filters.get("month"):
                period_prefix = f"{filters['year']}-{filters['month']:02d}"
                stmt = stmt.where(Voucher.date.like(f"{period_prefix}%"))
            result = await session.execute(stmt)
            return result.scalar() or 0

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

    async def create_with_entries(self, ledger_id: int, date: str, description: str, entries: list, status: str = "draft", voucher_no: str = None):
        """Create a voucher with its journal entries in one transaction."""
        async with get_db() as session:
            # Generate voucher number if not provided
            if not voucher_no:
                voucher_no = await self._generate_voucher_no(session, ledger_id, date)

            total_debit = sum(float(e.get("debit", 0) or 0) for e in entries)
            total_credit = sum(float(e.get("credit", 0) or 0) for e in entries)

            # Validate debit == credit
            if abs(total_debit - total_credit) >= 0.01:
                raise ValueError(f"借贷不平衡：借方 {total_debit:.2f} ≠ 贷方 {total_credit:.2f}")

            voucher = Voucher(
                ledger_id=ledger_id,
                voucher_no=voucher_no,
                date=date,
                description=description,
                total_debit=total_debit,
                total_credit=total_credit,
                status=status,
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

    async def update(self, voucher_no: str, date: str = None, description: str = None, entries: list = None, ledger_id: int = None):
        async with get_db() as session:
            stmt = select(Voucher).where(Voucher.voucher_no == voucher_no)
            if ledger_id is not None:
                stmt = stmt.where(Voucher.ledger_id == ledger_id)
            result = await session.execute(stmt)
            voucher = result.scalar_one_or_none()
            if voucher:
                if date is not None:
                    voucher.date = date
                if description is not None:
                    voucher.description = description
                if entries is not None:
                    # Delete existing entries and recreate
                    await session.refresh(voucher, ["journal_entries"])
                    for old_entry in list(voucher.journal_entries):
                        await session.delete(old_entry)
                    for entry_data in entries:
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
                    voucher.total_debit = sum(float(e.get("debit", 0) or 0) for e in entries)
                    voucher.total_credit = sum(float(e.get("credit", 0) or 0) for e in entries)
            return voucher

    async def delete(self, voucher_no: str, ledger_id: int = None) -> bool:
        async with get_db() as session:
            stmt = select(Voucher).where(Voucher.voucher_no == voucher_no)
            if ledger_id is not None:
                stmt = stmt.where(Voucher.ledger_id == ledger_id)
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
                    # Use the same session — don't call add_workflow which opens a new one
                    wf = VoucherWorkflow(
                        voucher_id=voucher.id,
                        ledger_id=voucher.ledger_id,
                        action=action,
                        from_status=old_status,
                        to_status=new_status,
                        user_id=user_id,
                        comment=comment,
                    )
                    session.add(wf)
            return voucher

    async def get_entries(self, voucher_id: int):
        async with get_db() as session:
            stmt = select(JournalEntry).where(JournalEntry.voucher_id == voucher_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_workflow_history(self, voucher_id: int):
        """获取凭证的操作历史记录"""
        async with get_db() as session:
            stmt = select(VoucherWorkflow).where(
                VoucherWorkflow.voucher_id == voucher_id
            ).order_by(VoucherWorkflow.created_at.asc())
            result = await session.execute(stmt)
            return result.scalars().all()


class VoucherTemplateRepository(BaseRepository):
    """凭证模板管理"""

    model = VoucherTemplate

    async def get_all(self, ledger_id: int, include_inactive: bool = False):
        async with get_db() as session:
            stmt = select(VoucherTemplate).where(VoucherTemplate.ledger_id == ledger_id)
            if not include_inactive:
                stmt = stmt.where(VoucherTemplate.is_active == 1)
            stmt = stmt.order_by(VoucherTemplate.name)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create(self, ledger_id: int, name: str, description: str, entries: list,
                     category: str = "general", is_system: int = 0):
        async with get_db() as session:
            import json as _json
            tpl = VoucherTemplate(
                ledger_id=ledger_id,
                name=name,
                description=description,
                category=category,
                entries=_json.dumps(entries, ensure_ascii=False),
                is_system=is_system,
            )
            session.add(tpl)
            await session.flush()
            await session.refresh(tpl)
            return tpl

    async def update(self, template_id: int, ledger_id: int, **kwargs):
        async with get_db() as session:
            stmt = select(VoucherTemplate).where(
                and_(VoucherTemplate.id == template_id, VoucherTemplate.ledger_id == ledger_id)
            )
            result = await session.execute(stmt)
            tpl = result.scalar_one_or_none()
            if tpl:
                import json as _json
                if "entries" in kwargs and kwargs["entries"] is not None:
                    kwargs["entries"] = _json.dumps(kwargs["entries"], ensure_ascii=False)
                if "is_active" in kwargs:
                    kwargs["is_active"] = 1 if kwargs["is_active"] else 0
                for k, v in kwargs.items():
                    if v is not None:
                        setattr(tpl, k, v)
            return tpl

    async def delete(self, template_id: int, ledger_id: int) -> bool:
        async with get_db() as session:
            stmt = select(VoucherTemplate).where(
                and_(
                    VoucherTemplate.id == template_id,
                    VoucherTemplate.ledger_id == ledger_id,
                    VoucherTemplate.is_system == 0,
                )
            )
            result = await session.execute(stmt)
            tpl = result.scalar_one_or_none()
            if tpl:
                await session.delete(tpl)
                return True
            return False

    async def save(self, ledger_id: int, name: str, entries: list,
                   description: str = "", voucher_type: str = "记"):
        """保存凭证模板（简化版创建）"""
        async with get_db() as session:
            import json as _json
            tpl = VoucherTemplate(
                ledger_id=ledger_id,
                name=name,
                description=description,
                voucher_type=voucher_type,
                entries=_json.dumps(entries, ensure_ascii=False),
            )
            session.add(tpl)
            await session.flush()
            await session.refresh(tpl)
            return tpl


class ScheduledVoucherRepository(BaseRepository):
    """定时凭证任务管理"""

    model = ScheduledVoucher

    async def get_all(self, ledger_id: int):
        async with get_db() as session:
            stmt = select(ScheduledVoucher).where(
                and_(ScheduledVoucher.ledger_id == ledger_id, ScheduledVoucher.is_active == 1)
            ).order_by(ScheduledVoucher.next_run_at)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create(self, ledger_id: int, name: str, cron_expression: str,
                     template_id: int = None, next_run_at: str = None):
        async with get_db() as session:
            sv = ScheduledVoucher(
                ledger_id=ledger_id,
                template_id=template_id,
                name=name,
                cron_expression=cron_expression,
                next_run_at=next_run_at,
            )
            session.add(sv)
            await session.flush()
            await session.refresh(sv)
            return sv


class InvoiceVoucherRepository(BaseRepository):
    """发票-凭证关联"""

    async def link(self, invoice_id: int, voucher_id: int, ledger_id: int):
        async with get_db() as session:
            link = InvoiceVoucher(
                invoice_id=invoice_id,
                voucher_id=voucher_id,
                ledger_id=ledger_id,
            )
            session.add(link)
            await session.flush()
            return link

    async def get_vouchers(self, invoice_id: int):
        async with get_db() as session:
            from app.models.voucher import Voucher
            stmt = select(Voucher).join(
                InvoiceVoucher, InvoiceVoucher.voucher_id == Voucher.id
            ).where(
                InvoiceVoucher.invoice_id == invoice_id
            ).order_by(Voucher.date.desc())
            result = await session.execute(stmt)
            return result.scalars().all()
