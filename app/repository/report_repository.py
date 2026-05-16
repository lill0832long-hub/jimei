"""Report data repository — provides data for financial reports."""
from sqlalchemy import select, and_, func, case, literal_column
from app.models.voucher import Voucher, JournalEntry
from app.models.account import Account
from app.models.opening_balance import OpeningBalance
from app.models.base import get_db


class ReportRepository:
    """Read-only queries for report generation."""

    async def get_account_balances(self, ledger_id: int, year: int, month: int):
        """Get account balances with opening + period activity."""
        async with get_db() as session:
            # Get all active accounts
            stmt = select(Account).where(Account.is_active == 1).order_by(Account.code)
            result = await session.execute(stmt)
            accounts = result.scalars().all()

            balances = []
            date_prefix = f"{year:04d}-{month:02d}"
            year_prefix = f"{year:04d}-"

            for acct in accounts:
                # Opening balance
                ob_stmt = select(OpeningBalance).where(
                    and_(
                        OpeningBalance.ledger_id == ledger_id,
                        OpeningBalance.account_code == acct.code,
                        OpeningBalance.year == year,
                        OpeningBalance.month <= month,
                    )
                ).order_by(OpeningBalance.year.desc(), OpeningBalance.month.desc())
                ob_result = await session.execute(ob_stmt)
                ob = ob_result.scalar_one_or_none()
                opening = ob.balance if ob else 0

                # Period debit/credit from posted vouchers (current month only)
                je_stmt = select(
                    func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                    func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
                ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        JournalEntry.account_code == acct.code,
                        Voucher.date.like(f"{date_prefix}%"),
                        Voucher.status == "posted",
                    )
                )
                je_result = await session.execute(je_stmt)
                row = je_result.one()
                period_debit = row.total_debit
                period_credit = row.total_credit

                # Year-to-date debit/credit from posted vouchers (Jan through current month)
                ytd_stmt = select(
                    func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                    func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
                ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        JournalEntry.account_code == acct.code,
                        Voucher.date.like(f"{year_prefix}%"),
                        Voucher.date <= f"{year:04d}-{month:02d}-31",
                        Voucher.status == "posted",
                    )
                )
                ytd_result = await session.execute(ytd_stmt)
                ytd_row = ytd_result.one()
                ytd_debit = ytd_row.total_debit
                ytd_credit = ytd_row.total_credit

                # Calculate closing balance based on account category
                # Asset/Expense: debit increases, credit decreases
                # Liability/Equity/Credit: credit increases, debit decreases
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
