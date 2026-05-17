"""Report data repository — provides data for financial reports."""
from sqlalchemy import select, and_, func, case, literal_column
from app.models.voucher import Voucher, JournalEntry
from app.models.account import Account
from app.models.opening_balance import OpeningBalance
from app.models.base import get_db


class ReportRepository:
    """Read-only queries for report generation."""

    async def get_account_balances(self, ledger_id: int, year: int, month: int):
        """Get account balances with opening + period activity.

        Uses batch GROUP BY queries instead of per-account N+1 queries.
        3 queries total regardless of account count.
        """
        async with get_db() as session:
            date_prefix = f"{year:04d}-{month:02d}"
            year_prefix = f"{year:04d}-"
            month_end = f"{year:04d}-{month:02d}-31"

            # 1. Get all active accounts
            stmt = select(Account).where(Account.is_active == 1).order_by(Account.code)
            result = await session.execute(stmt)
            accounts = result.scalars().all()
            account_codes = [a.code for a in accounts]

            if not accounts:
                return []

            # 2. Batch: opening balances for all accounts
            ob_stmt = select(
                OpeningBalance.account_code,
                OpeningBalance.balance,
            ).where(
                and_(
                    OpeningBalance.ledger_id == ledger_id,
                    OpeningBalance.account_code.in_(account_codes),
                    OpeningBalance.year == year,
                    OpeningBalance.month <= month,
                )
            ).order_by(OpeningBalance.account_code, OpeningBalance.year.desc(), OpeningBalance.month.desc())
            ob_result = await session.execute(ob_stmt)
            # Take the latest opening balance per account_code
            opening_map = {}
            for ob_row in ob_result.all():
                if ob_row.account_code not in opening_map:
                    opening_map[ob_row.account_code] = ob_row.balance

            # 3. Batch: period debit/credit (current month) — GROUP BY account_code
            period_stmt = select(
                JournalEntry.account_code,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    JournalEntry.ledger_id == ledger_id,
                    JournalEntry.account_code.in_(account_codes),
                    Voucher.date.like(f"{date_prefix}%"),
                    Voucher.status == "posted",
                )
            ).group_by(JournalEntry.account_code)
            period_result = await session.execute(period_stmt)
            period_map = {r.account_code: (r.total_debit, r.total_credit) for r in period_result.all()}

            # 4. Batch: YTD debit/credit (Jan through current month) — GROUP BY account_code
            ytd_stmt = select(
                JournalEntry.account_code,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    JournalEntry.ledger_id == ledger_id,
                    JournalEntry.account_code.in_(account_codes),
                    Voucher.date.like(f"{year_prefix}%"),
                    Voucher.date <= month_end,
                    Voucher.status == "posted",
                )
            ).group_by(JournalEntry.account_code)
            ytd_result = await session.execute(ytd_stmt)
            ytd_map = {r.account_code: (r.total_debit, r.total_credit) for r in ytd_result.all()}

            # 5. Assemble results (no more DB queries)
            balances = []
            for acct in accounts:
                opening = opening_map.get(acct.code, 0)
                period_debit, period_credit = period_map.get(acct.code, (0, 0))
                ytd_debit, ytd_credit = ytd_map.get(acct.code, (0, 0))

                if acct.category in ("资产", "费用"):
                    closing = opening + period_debit - period_credit
                else:
                    closing = opening + period_credit - period_debit

                balances.append({
                    "account_code": acct.code,
                    "account_name": acct.name,
                    "category": acct.category,
                    "opening_balance": opening,
                    "period_debit": period_debit,
                    "period_credit": period_credit,
                    "closing_balance": closing,
                    "ytd_debit": ytd_debit,
                    "ytd_credit": ytd_credit,
                })

            return balances

    async def get_monthly_trend(self, ledger_id: int, months: int = 6):
        """Get monthly revenue/expense trend."""
        async with get_db() as session:
            # Get income accounts (收入类)
            income_stmt = select(func.substr(Voucher.date, 1, 7).label("month"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("income"),
            ).join(JournalEntry, Voucher.id == JournalEntry.voucher_id).where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    Voucher.status == "posted",
                    JournalEntry.account_code >= "6000",
                    JournalEntry.account_code < "7000",
                )
            ).group_by(func.substr(Voucher.date, 1, 7)).order_by(
                func.substr(Voucher.date, 1, 7).desc()
            ).limit(months)
            result = await session.execute(income_stmt)
            income_rows = result.all()

            # Get expense accounts (费用类)
            expense_stmt = select(func.substr(Voucher.date, 1, 7).label("month"),
                func.coalesce(func.sum(JournalEntry.debit), 0).label("expense"),
            ).join(JournalEntry, Voucher.id == JournalEntry.voucher_id).where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    Voucher.status == "posted",
                    JournalEntry.account_code >= "5000",
                    JournalEntry.account_code < "6000",
                )
            ).group_by(func.substr(Voucher.date, 1, 7)).order_by(
                func.substr(Voucher.date, 1, 7).desc()
            ).limit(months)
            result = await session.execute(expense_stmt)
            expense_rows = result.all()

            return {"income": list(income_rows), "expense": list(expense_rows)}
