"""Budget repository."""
from sqlalchemy import select, and_, func, case, literal_column
from app.models.budget import Budget, BudgetExecution
from app.models.voucher import Voucher, JournalEntry
from app.models.base import get_db
from .base import BaseRepository


class BudgetRepository(BaseRepository):
    model = Budget

    # ── Budget CRUD ──────────────────────────────────────────────────────

    async def get_by_ledger(self, ledger_id: int, year: int = None, month: int = None):
        """Return budgets for a ledger, optionally filtered by year and month."""
        async with get_db() as session:
            stmt = select(Budget).where(Budget.ledger_id == ledger_id)
            if year is not None:
                stmt = stmt.where(Budget.budget_year == year)
            if month is not None:
                stmt = stmt.where(Budget.budget_month == month)
            stmt = stmt.order_by(Budget.account_code, Budget.budget_month)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_by_account(self, ledger_id: int, account_code: str, year: int):
        """Return budget rows for a specific account in a given year."""
        async with get_db() as session:
            stmt = select(Budget).where(
                and_(
                    Budget.ledger_id == ledger_id,
                    Budget.account_code == account_code,
                    Budget.budget_year == year,
                )
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def set_budget(
        self,
        ledger_id: int,
        account_code: str,
        account_name: str,
        year: int,
        month: int,
        amount: float,
        description: str = "",
    ):
        """Insert or update a budget row (upsert by unique key)."""
        from datetime import datetime

        async with get_db() as session:
            stmt = select(Budget).where(
                and_(
                    Budget.ledger_id == ledger_id,
                    Budget.account_code == account_code,
                    Budget.budget_year == year,
                    Budget.budget_month == month if month is not None else Budget.budget_month.is_(None),
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if existing:
                existing.budget_amount = amount
                existing.account_name = account_name
                existing.description = description
                existing.updated_at = now
            else:
                budget = Budget(
                    ledger_id=ledger_id,
                    account_code=account_code,
                    account_name=account_name,
                    budget_year=year,
                    budget_month=month,
                    budget_amount=amount,
                    description=description,
                    created_at=now,
                    updated_at=now,
                )
                session.add(budget)

            await session.flush()
            if existing:
                return existing
            await session.refresh(budget)
            return budget

    # ── Budget Execution ────────────────────────────────────────────────

    async def get_execution(self, ledger_id: int, year: int, month: int) -> list[dict]:
        """Return budget-vs-actual execution rows for a given period.

        Each dict contains: id, account_code, account_name, budget_amount,
        actual_amount, variance, variance_pct, is_over_budget.
        """
        async with get_db() as session:
            # 1. Fetch monthly budgets
            budget_stmt = select(Budget).where(
                and_(
                    Budget.ledger_id == ledger_id,
                    Budget.budget_year == year,
                    Budget.budget_month == month,
                )
            )
            budget_result = await session.execute(budget_stmt)
            budgets = budget_result.scalars().all()

            if not budgets:
                return []

            # 2. Compute actual debit per account from posted vouchers
            actual_subq = (
                select(
                    JournalEntry.account_code,
                    func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .where(
                    and_(
                        Voucher.ledger_id == ledger_id,
                        Voucher.status == "posted",
                        func.strftime("%Y", Voucher.date) == str(year),
                        func.strftime("%m", Voucher.date) == f"{month:02d}",
                    )
                )
                .group_by(JournalEntry.account_code)
                .subquery()
            )

            # 3. Build result list
            results = []
            for b in budgets:
                actual_stmt = select(actual_subq.c.total_debit).where(
                    actual_subq.c.account_code == b.account_code
                )
                actual_result = await session.execute(actual_stmt)
                actual = actual_result.scalar() or 0

                budget_amount = b.budget_amount or 0
                variance = actual - budget_amount
                variance_pct = (variance / budget_amount * 100) if budget_amount > 0 else 0
                is_over = actual > budget_amount if budget_amount > 0 else False

                results.append({
                    "id": b.id,
                    "account_code": b.account_code,
                    "account_name": b.account_name,
                    "budget_amount": budget_amount,
                    "actual_amount": actual,
                    "variance": variance,
                    "variance_pct": round(variance_pct, 2),
                    "is_over_budget": is_over,
                })

            return results

    async def get_summary(self, ledger_id: int, year: int, month: int) -> dict:
        """Return aggregated budget summary for a period."""
        execution = await self.get_execution(ledger_id, year, month)
        total_budget = sum(e["budget_amount"] for e in execution)
        total_actual = sum(e["actual_amount"] for e in execution)
        over_budget_count = sum(1 for e in execution if e["is_over_budget"])
        return {
            "total_budget": total_budget,
            "total_actual": total_actual,
            "total_variance": total_actual - total_budget,
            "over_budget_count": over_budget_count,
            "item_count": len(execution),
        }

    async def check_exceeded(
        self,
        ledger_id: int,
        account_code: str,
        year: int,
        month: int,
        additional_amount: float = 0,
    ) -> dict:
        """Check whether adding *additional_amount* would exceed the budget.

        Returns a dict with has_budget, budget_amount, actual_amount,
        projected, exceeded, remaining.
        """
        async with get_db() as session:
            # Fetch the budget row
            budget_stmt = select(Budget).where(
                and_(
                    Budget.ledger_id == ledger_id,
                    Budget.account_code == account_code,
                    Budget.budget_year == year,
                    Budget.budget_month == month,
                )
            )
            budget_result = await session.execute(budget_stmt)
            budget = budget_result.scalar_one_or_none()

            if not budget or not budget.budget_amount or budget.budget_amount <= 0:
                return {"has_budget": False, "exceeded": False}

            # Compute actual debit from posted vouchers
            actual_stmt = (
                select(func.coalesce(func.sum(JournalEntry.debit), 0))
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .where(
                    and_(
                        Voucher.ledger_id == ledger_id,
                        Voucher.status == "posted",
                        JournalEntry.account_code == account_code,
                        func.strftime("%Y", Voucher.date) == str(year),
                        func.strftime("%m", Voucher.date) == f"{month:02d}",
                    )
                )
            )
            actual_result = await session.execute(actual_stmt)
            actual = actual_result.scalar() or 0

            projected = actual + additional_amount
            budget_amount = budget.budget_amount
            return {
                "has_budget": True,
                "budget_amount": budget_amount,
                "actual_amount": actual,
                "projected": projected,
                "exceeded": projected > budget_amount,
                "remaining": budget_amount - projected,
            }

    # ── BudgetExecution records ─────────────────────────────────────────

    async def add_execution(
        self,
        ledger_id: int,
        budget_id: int | None,
        account_code: str,
        year: int,
        month: int,
        actual_amount: float,
    ):
        """Insert a BudgetExecution snapshot row."""
        from datetime import datetime

        async with get_db() as session:
            exec_record = BudgetExecution(
                ledger_id=ledger_id,
                budget_id=budget_id,
                account_code=account_code,
                budget_year=year,
                budget_month=month,
                actual_amount=actual_amount,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            session.add(exec_record)
            await session.flush()
            return exec_record

    async def get_execution_history(
        self, ledger_id: int, account_code: str, year: int
    ):
        """Return BudgetExecution history for an account in a given year."""
        async with get_db() as session:
            stmt = select(BudgetExecution).where(
                and_(
                    BudgetExecution.ledger_id == ledger_id,
                    BudgetExecution.account_code == account_code,
                    BudgetExecution.budget_year == year,
                )
            ).order_by(BudgetExecution.budget_month)
            result = await session.execute(stmt)
            return result.scalars().all()
