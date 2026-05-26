"""Dashboard repository — async queries for dashboard KPIs and charts."""
from sqlalchemy import select, func, and_, case
from app.models.base import get_db
from app.models.voucher import Voucher, JournalEntry
from app.models.account import Account


class DashboardRepository:
    """Read-only queries for dashboard data."""

    async def get_dashboard_kpi(self, ledger_id: int, year: int, month: int) -> dict:
        """Get dashboard KPI data."""
        async with get_db() as session:
            year_str = str(year)
            month_int = month
            month_str = f"{month:02d}"
            date_prefix = f"{year_str}-{month_str}"

            # AR balance (account_code LIKE '1122%')
            ar_stmt = (
                select(
                    func.coalesce(func.sum(JournalEntry.debit) - func.sum(JournalEntry.credit), 0).label("bal")
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        JournalEntry.account_code.like("1122%"),
                        Voucher.status == "posted",
                        func.substr(Voucher.date, 1, 4) == year_str,
                        func.cast(func.substr(Voucher.date, 6, 2), db_integer()) <= month_int,
                    )
                )
            )
            ar_result = await session.execute(ar_stmt)
            ar_bal = ar_result.scalar() or 0

            # AP balance (account_code LIKE '2202%')
            ap_stmt = (
                select(
                    func.coalesce(func.sum(JournalEntry.credit) - func.sum(JournalEntry.debit), 0).label("bal")
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        JournalEntry.account_code.like("2202%"),
                        Voucher.status == "posted",
                        func.substr(Voucher.date, 1, 4) == year_str,
                        func.cast(func.substr(Voucher.date, 6, 2), db_integer()) <= month_int,
                    )
                )
            )
            ap_result = await session.execute(ap_stmt)
            ap_bal = ap_result.scalar() or 0

            # Bank balance (account_code LIKE '1002%')
            bank_stmt = (
                select(
                    func.coalesce(func.sum(JournalEntry.debit) - func.sum(JournalEntry.credit), 0).label("bal")
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        JournalEntry.account_code.like("1002%"),
                        Voucher.status == "posted",
                        func.substr(Voucher.date, 1, 4) == year_str,
                        func.cast(func.substr(Voucher.date, 6, 2), db_integer()) <= month_int,
                    )
                )
            )
            bank_result = await session.execute(bank_stmt)
            bank_bal = bank_result.scalar() or 0

            # Monthly revenue
            rev_stmt = (
                select(
                    func.coalesce(func.sum(JournalEntry.credit) - func.sum(JournalEntry.debit), 0).label("total")
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .join(Account, JournalEntry.account_code == Account.code)
                .where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        Account.category == "收入",
                        Account.is_active == 1,
                        Voucher.status == "posted",
                        func.substr(Voucher.date, 1, 4) == year_str,
                        func.cast(func.substr(Voucher.date, 6, 2), db_integer()) == month_int,
                    )
                )
            )
            rev_result = await session.execute(rev_stmt)
            month_revenue = rev_result.scalar() or 0

            # Monthly expense
            exp_stmt = (
                select(
                    func.coalesce(func.sum(JournalEntry.debit) - func.sum(JournalEntry.credit), 0).label("total")
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .join(Account, JournalEntry.account_code == Account.code)
                .where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        Account.category == "费用",
                        Account.is_active == 1,
                        Voucher.status == "posted",
                        func.substr(Voucher.date, 1, 4) == year_str,
                        func.cast(func.substr(Voucher.date, 6, 2), db_integer()) == month_int,
                    )
                )
            )
            exp_result = await session.execute(exp_stmt)
            month_expense = exp_result.scalar() or 0

            # Net cash flow
            cash_stmt = (
                select(
                    func.coalesce(func.sum(JournalEntry.debit) - func.sum(JournalEntry.credit), 0).label("total")
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        (
                            JournalEntry.account_code.like("1001%")
                            | JournalEntry.account_code.like("1002%")
                        ),
                        Voucher.status == "posted",
                        func.substr(Voucher.date, 1, 4) == year_str,
                        func.cast(func.substr(Voucher.date, 6, 2), db_integer()) == month_int,
                    )
                )
            )
            cash_result = await session.execute(cash_stmt)
            net_cash_flow = cash_result.scalar() or 0

            return {
                "ar_balance": ar_bal,
                "ap_balance": ap_bal,
                "bank_balance": bank_bal,
                "month_revenue": month_revenue,
                "month_expense": month_expense,
                "month_profit": month_revenue - month_expense,
                "net_cash_flow": net_cash_flow,
            }

    async def get_monthly_trend(self, ledger_id: int, months: int = 12) -> list:
        """Get monthly revenue/expense trend for the last N months."""
        async with get_db() as session:
            stmt = (
                select(
                    func.substr(Voucher.date, 1, 4).label("year"),
                    func.cast(func.substr(Voucher.date, 6, 2), db_integer()).label("month"),
                    func.coalesce(
                        func.sum(
                            case(
                                (Account.category == "收入", JournalEntry.credit - JournalEntry.debit),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("revenue"),
                    func.coalesce(
                        func.sum(
                            case(
                                (Account.category == "费用", JournalEntry.debit - JournalEntry.credit),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("expense"),
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .join(
                    Account,
                    and_(
                        JournalEntry.account_code == Account.code,
                        Account.is_active == 1,
                    ),
                )
                .where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        Voucher.status == "posted",
                        Account.category.in_(["收入", "费用"]),
                    )
                )
                .group_by(func.substr(Voucher.date, 1, 4), func.substr(Voucher.date, 6, 2))
                .order_by(func.substr(Voucher.date, 1, 4).desc(), func.substr(Voucher.date, 6, 2).desc())
                .limit(months)
            )
            result = await session.execute(stmt)
            rows = result.all()
            result_list = [
                {"year": r.year, "month": r.month, "revenue": r.revenue, "expense": r.expense}
                for r in rows
            ]
            result_list.reverse()
            return result_list

    async def get_expense_breakdown(self, ledger_id: int, year: int, month: int) -> list:
        """Get expense breakdown by sub-category."""
        async with get_db() as session:
            year_str = str(year)
            month_int = month

            stmt = (
                select(
                    Account.sub_category.label("category"),
                    func.sum(JournalEntry.debit - JournalEntry.credit).label("amount"),
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .join(
                    Account,
                    and_(
                        JournalEntry.account_code == Account.code,
                        Account.is_active == 1,
                    ),
                )
                .where(
                    and_(
                        JournalEntry.ledger_id == ledger_id,
                        Account.category == "费用",
                        Voucher.status == "posted",
                        func.substr(Voucher.date, 1, 4) == year_str,
                        func.cast(func.substr(Voucher.date, 6, 2), db_integer()) == month_int,
                    )
                )
                .group_by(Account.sub_category)
                .having(func.sum(JournalEntry.debit - JournalEntry.credit) > 0)
                .order_by(func.sum(JournalEntry.debit - JournalEntry.credit).desc())
            )
            result = await session.execute(stmt)
            rows = result.all()
            return [{"category": r.category or "其他", "amount": r.amount} for r in rows]

    async def get_period_compare_income(self, ledger_id: int, periods: list) -> dict:
        """Multi-period income comparison.
        periods: [(year, month), ...]
        Returns: {periods: [...], items: [{name, code, values, changes}], summary: {...}}
        """
        from app.repository.report_repository import ReportRepository
        report_repo = ReportRepository()
        results = []
        for year, month in periods:
            inc = await report_repo.get_income_statement_data(ledger_id, year, month)
            rev_dict = {}
            exp_dict = {}
            for r in inc.get("rows", []):
                if r.get("type") == "revenue_item":
                    rev_dict[r["code"]] = r.get("month", 0)
                elif r.get("type") == "expense_item":
                    exp_dict[r["code"]] = r.get("month", 0)
            results.append({
                "year": year, "month": month,
                "label": f"{year}-{month:02d}",
                "revenues": rev_dict,
                "expenses": exp_dict,
                "total_revenue": inc.get("total_revenue", 0),
                "total_expense": inc.get("total_expense", inc.get("total_revenue", 0) - inc.get("net_profit", 0)),
                "net_profit": inc.get("net_profit", 0),
            })

        all_rev_codes = set()
        all_exp_codes = set()
        for r in results:
            all_rev_codes.update(r["revenues"].keys())
            all_exp_codes.update(r["expenses"].keys())

        # Batch fetch account names
        all_codes = all_rev_codes | all_exp_codes
        code_names = {}
        if all_codes:
            async with get_db() as session:
                stmt = select(Account.code, Account.name).where(Account.code.in_(all_codes))
                result = await session.execute(stmt)
                for row in result.all():
                    code_names[row.code] = row.name

        items = []
        for code in sorted(all_rev_codes):
            values = [r["revenues"].get(code, 0) for r in results]
            changes = []
            for i in range(1, len(values)):
                if values[i - 1] != 0:
                    changes.append((values[i] - values[i - 1]) / values[i - 1] * 100)
                else:
                    changes.append(None)
            items.append({"code": code, "name": code_names.get(code, code), "type": "revenue",
                          "values": values, "changes": changes})
        for code in sorted(all_exp_codes):
            values = [r["expenses"].get(code, 0) for r in results]
            changes = []
            for i in range(1, len(values)):
                if values[i - 1] != 0:
                    changes.append((values[i] - values[i - 1]) / values[i - 1] * 100)
                else:
                    changes.append(None)
            items.append({"code": code, "name": code_names.get(code, code), "type": "expense",
                          "values": values, "changes": changes})

        return {
            "periods": [r["label"] for r in results],
            "items": items,
            "summary": {
                "total_revenue": [r["total_revenue"] for r in results],
                "total_expense": [r["total_expense"] for r in results],
                "net_profit": [r["net_profit"] for r in results],
            }
        }

    async def get_period_compare_balance(self, ledger_id: int, periods: list) -> dict:
        """Multi-period balance sheet comparison.
        periods: [(year, month), ...]
        Returns: {periods: [...], items: [{name, code, category, values, changes}], summary: {...}}
        """
        from app.repository.report_repository import ReportRepository
        report_repo = ReportRepository()
        results = []
        for year, month in periods:
            bs = await report_repo.get_balance_sheet_data(ledger_id, year, month)
            asset_items = {r["code"]: r.get("end", 0) for r in bs.get("assets", []) if r.get("code") and r["code"] not in ("1003", "1601N")}
            liab_items = {r["code"]: r.get("end", 0) for r in bs.get("liabilities", []) if r.get("code")}
            eq_items = {r["code"]: r.get("end", 0) for r in bs.get("equity", []) if r.get("code")}
            results.append({
                "year": year, "month": month,
                "label": f"{year}-{month:02d}",
                "assets": bs.get("total_assets", 0),
                "liabilities": bs.get("total_liab", 0),
                "equity": bs.get("total_equity", 0),
                "asset_items": asset_items,
                "liab_items": liab_items,
                "equity_items": eq_items,
            })

        all_codes = set()
        for r in results:
            all_codes.update(r["asset_items"].keys())
            all_codes.update(r["liab_items"].keys())
            all_codes.update(r["equity_items"].keys())

        # Batch fetch account names and categories
        code_meta = {}
        if all_codes:
            async with get_db() as session:
                stmt = select(Account.code, Account.name, Account.category).where(Account.code.in_(all_codes))
                result = await session.execute(stmt)
                for row in result.all():
                    code_meta[row.code] = {"name": row.name, "category": row.category}

        items = []
        for code in sorted(all_codes):
            values = []
            for r in results:
                v = r["asset_items"].get(code, 0) + r["liab_items"].get(code, 0) + r["equity_items"].get(code, 0)
                values.append(v)
            changes = []
            for i in range(1, len(values)):
                if values[i - 1] != 0:
                    changes.append((values[i] - values[i - 1]) / values[i - 1] * 100)
                else:
                    changes.append(None)
            meta = code_meta.get(code, {"name": code, "category": "unknown"})
            items.append({"code": code, "name": meta["name"], "category": meta["category"],
                          "values": values, "changes": changes})

        return {
            "periods": [r["label"] for r in results],
            "items": items,
            "summary": {
                "assets": [r["assets"] for r in results],
                "liabilities": [r["liabilities"] for r in results],
                "equity": [r["equity"] for r in results],
            }
        }


def db_integer():
    """SQLite INTEGER type for CAST expressions."""
    from sqlalchemy import Integer
    return Integer
