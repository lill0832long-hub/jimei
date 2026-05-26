"""Ledger repository."""
from sqlalchemy import select, text
from app.models.ledger import Ledger
from app.models.voucher import Voucher, JournalEntry
from app.models.base import get_db
from app.models.account import Account
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

    async def get_account_ledger(self, ledger_id: int, account_code: str, year: int, month: int) -> dict:
        """Get account ledger: all journal entries for an account in a period with running balance."""
        async with get_db() as session:
            acct_stmt = select(Account).where(
                Account.code == account_code,
                Account.is_active == 1,
            )
            acct_result = await session.execute(acct_stmt)
            acct = acct_result.scalar_one_or_none()
            if not acct:
                return None

            # Get opening balance (from period_repo logic inline)
            ob_stmt = text("""
                SELECT balance FROM opening_balances
                WHERE ledger_id = :lid AND account_code = :acode
                  AND (year < :y OR (year = :y AND month <= :m))
                ORDER BY year DESC, month DESC
                LIMIT 1
            """)
            ob_result = await session.execute(
                ob_stmt,
                {"lid": ledger_id, "acode": account_code, "y": year, "m": month},
            )
            ob_row = ob_result.fetchone()
            opening = ob_row[0] if ob_row else 0

            entries_stmt = text("""
                SELECT je.id, je.debit, je.credit, je.summary,
                       v.voucher_no, v.date, v.description as voucher_desc, v.status
                FROM journal_entries je
                JOIN vouchers v ON je.voucher_id = v.id
                WHERE je.ledger_id = :lid AND je.account_code = :acode
                  AND strftime('%Y', v.date) = :year AND CAST(strftime('%m', v.date) AS INTEGER) <= :month
                  AND v.status = 'posted'
                ORDER BY v.date, v.voucher_no, je.id
            """)
            entries_result = await session.execute(
                entries_stmt,
                {"lid": ledger_id, "acode": account_code, "year": str(year), "month": month},
            )
            bal = opening
            rows = []
            for r in entries_result:
                d = dict(r._mapping)
                bal += d["debit"] - d["credit"]
                d["balance"] = round(bal, 2)
                rows.append(d)

            return {
                "account": {"code": acct.code, "name": acct.name, "category": acct.category},
                "opening_balance": round(opening, 2),
                "closing_balance": round(bal, 2),
                "entries": rows,
                "period": f"{year}-{month:02d}",
            }

    async def get_general_ledger(self, ledger_id: int, account_code: str = None, year: int = None, month: int = None) -> list:
        """Get general ledger: all posted journal entries, optionally filtered by account and period."""
        date_filter = ""
        params = {"ledger_id": ledger_id}
        if account_code is not None:
            date_filter += " AND je.account_code = :account_code"
            params["account_code"] = account_code
        if year is not None:
            date_filter += " AND strftime('%Y', v.date) = :year"
            params["year"] = str(year)
        if month is not None:
            date_filter += " AND strftime('%m', v.date) = :month"
            params["month"] = f"{month:02d}"
        sql = (
            "SELECT je.id, je.debit, je.credit, je.summary, "
            "je.account_code, je.account_name, "
            "v.voucher_no, v.date, v.description as voucher_desc, v.status "
            "FROM journal_entries je "
            "JOIN vouchers v ON je.voucher_id = v.id "
            "WHERE je.ledger_id = :ledger_id " + date_filter + " "
            "AND v.status = 'posted' "
            "ORDER BY v.date, v.voucher_no, je.id"
        )
        async with get_db() as session:
            result = await session.execute(text(sql), params)
            return [dict(r._mapping) for r in result]
