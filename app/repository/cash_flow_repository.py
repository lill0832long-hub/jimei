"""Cash flow repository — async queries for cash flow statements and categories."""
import math

from sqlalchemy import select, func, case, and_, literal_column
from app.models.base import get_db
from app.models.voucher import Voucher, JournalEntry
from app.models.account import Account
from app.models.cash_flow_category import CashFlowCategory
from app.repository.base import BaseRepository


class CashFlowRepository(BaseRepository):
    """Cash flow data repository.

    Extends BaseRepository for basic CRUD on CashFlowCategory.
    Custom async methods for cash flow statement generation.
    """

    model = CashFlowCategory

    async def get_cash_flow_categories(self, ledger_id: int) -> list:
        """Get all active cash flow categories for a ledger."""
        async with get_db() as session:
            stmt = (
                select(CashFlowCategory)
                .where(
                    and_(
                        CashFlowCategory.ledger_id == ledger_id,
                        CashFlowCategory.is_active == 1,
                    )
                )
                .order_by(CashFlowCategory.category, CashFlowCategory.code)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._category_to_dict(r) for r in rows]

    async def add_cash_flow_category(
        self, ledger_id: int, code: str, name: str, category: str, parent_code: str = None
    ):
        """Add or replace a cash flow category (INSERT OR REPLACE)."""
        async with get_db() as session:
            # Try to find existing
            stmt = select(CashFlowCategory).where(
                and_(
                    CashFlowCategory.ledger_id == ledger_id,
                    CashFlowCategory.code == code,
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.name = name
                existing.category = category
                existing.parent_code = parent_code
                existing.is_active = 1
            else:
                obj = CashFlowCategory(
                    ledger_id=ledger_id,
                    code=code,
                    name=name,
                    category=category,
                    parent_code=parent_code,
                )
                session.add(obj)
            await session.flush()

    async def init_cash_flow_categories(self, ledger_id: int):
        """Initialize default cash flow categories for a ledger."""
        default_categories = [
            ("OI01", "销售商品/提供劳务收到的现金", "operating_inflow"),
            ("OI02", "收到的税费返还", "operating_inflow"),
            ("OI03", "其他经营活动现金流入", "operating_inflow"),
            ("OO01", "购买商品/接受劳务支付的现金", "operating_outflow"),
            ("OO02", "支付给职工的现金", "operating_outflow"),
            ("OO03", "支付的税费", "operating_outflow"),
            ("OO04", "其他经营活动现金流出", "operating_outflow"),
            ("II01", "收回投资收到的现金", "investing_inflow"),
            ("II02", "取得投资收益收到的现金", "investing_inflow"),
            ("II03", "处置固定资产收回的现金", "investing_inflow"),
            ("IO01", "购建固定资产支付的现金", "investing_outflow"),
            ("IO02", "投资支付的现金", "investing_outflow"),
            ("FI01", "吸收投资收到的现金", "financing_inflow"),
            ("FI02", "借款收到的现金", "financing_inflow"),
            ("FO01", "偿还债务支付的现金", "financing_outflow"),
            ("FO02", "分配利润支付的现金", "financing_outflow"),
        ]
        for code, name, category in default_categories:
            await self.add_cash_flow_category(ledger_id, code, name, category)

    async def get_cash_flow_statement(
        self, ledger_id: int, year: int, month: int, method: str = "direct"
    ) -> dict:
        """Generate cash flow statement.

        method: 'direct' for direct method, 'indirect' for indirect method.
        """
        async with get_db() as session:
            year_str = str(year)
            month_str = f"{month:02d}"

            # ── Investing & financing: same for both methods ──
            cf_stmt = (
                select(
                    JournalEntry.cash_flow_type,
                    func.coalesce(
                        func.sum(case((JournalEntry.debit > 0, JournalEntry.debit), else_=0)), 0
                    ).label("total_debit"),
                    func.coalesce(
                        func.sum(case((JournalEntry.credit > 0, JournalEntry.credit), else_=0)), 0
                    ).label("total_credit"),
                )
                .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                .where(
                    and_(
                        Voucher.ledger_id == ledger_id,
                        Voucher.status == "posted",
                        JournalEntry.cash_flow_type != "",
                        func.substr(Voucher.date, 1, 4) == year_str,
                        func.substr(Voucher.date, 6, 2) == month_str,
                    )
                )
                .group_by(JournalEntry.cash_flow_type)
            )
            cf_result = await session.execute(cf_stmt)
            rows_cf = cf_result.all()

            investing_inflow = 0.0
            investing_outflow = 0.0
            financing_inflow = 0.0
            financing_outflow = 0.0
            detail_rows = []

            for row in rows_cf:
                cf_type = row.cash_flow_type
                if cf_type.startswith("investing_"):
                    if "inflow" in cf_type:
                        investing_inflow += row.total_debit
                    else:
                        investing_outflow += row.total_credit
                elif cf_type.startswith("financing_"):
                    if "inflow" in cf_type:
                        financing_inflow += row.total_debit
                    else:
                        financing_outflow += row.total_credit

            # If no cash flow type data, infer from accounts
            has_invest_fin = any(
                r.cash_flow_type.startswith(("investing_", "financing_")) for r in rows_cf
            )
            if not has_invest_fin:
                inferred = await self._infer_cash_flow(session, ledger_id, year, month)
                for d in inferred:
                    if d["type"] == "investing_inflow":
                        investing_inflow += max(d["net"], 0)
                    elif d["type"] == "investing_outflow":
                        investing_outflow += abs(min(d["net"], 0))
                    elif d["type"] == "financing_inflow":
                        financing_inflow += max(d["net"], 0)
                    elif d["type"] == "financing_outflow":
                        financing_outflow += abs(min(d["net"], 0))

            if method == "indirect":
                # ── Indirect method: operating from net profit ──
                # 1. Net profit
                np_stmt = (
                    select(
                        func.coalesce(
                            func.sum(
                                case(
                                    (Account.category == "收入", JournalEntry.credit - JournalEntry.debit),
                                    else_=0,
                                )
                            ),
                            0,
                        )
                        - func.coalesce(
                            func.sum(
                                case(
                                    (Account.category == "费用", JournalEntry.debit - JournalEntry.credit),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("np")
                    )
                    .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                    .join(Account, Account.code == JournalEntry.account_code)
                    .where(
                        and_(
                            Voucher.ledger_id == ledger_id,
                            Voucher.status == "posted",
                            func.substr(Voucher.date, 1, 4) == year_str,
                            func.substr(Voucher.date, 6, 2) == month_str,
                        )
                    )
                )
                np_result = await session.execute(np_stmt)
                np_row = np_result.one()
                net_profit = round(np_row.np or 0, 2)

                # 2. Depreciation
                dep_stmt = (
                    select(func.coalesce(func.sum(JournalEntry.debit), 0).label("total"))
                    .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                    .where(
                        and_(
                            Voucher.ledger_id == ledger_id,
                            Voucher.status == "posted",
                            func.substr(Voucher.date, 1, 4) == year_str,
                            func.substr(Voucher.date, 6, 2) == month_str,
                            (
                                JournalEntry.account_name.like("%折旧%")
                                | JournalEntry.account_code.in_(["1602", "1702"])
                            ),
                        )
                    )
                )
                dep_result = await session.execute(dep_stmt)
                depreciation = round(dep_result.scalar() or 0, 2)

                # 3. Amortization
                amo_stmt = (
                    select(func.coalesce(func.sum(JournalEntry.debit), 0).label("total"))
                    .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                    .where(
                        and_(
                            Voucher.ledger_id == ledger_id,
                            Voucher.status == "posted",
                            func.substr(Voucher.date, 1, 4) == year_str,
                            func.substr(Voucher.date, 6, 2) == month_str,
                            (
                                JournalEntry.account_name.like("%摊销%")
                                | (JournalEntry.account_code == "1801")
                            ),
                        )
                    )
                )
                amo_result = await session.execute(amo_stmt)
                amortization = round(amo_result.scalar() or 0, 2)

                # 4. Investment income
                inv_stmt = (
                    select(
                        func.coalesce(func.sum(JournalEntry.credit - JournalEntry.debit), 0).label("total")
                    )
                    .join(Voucher, JournalEntry.voucher_id == Voucher.id)
                    .where(
                        and_(
                            Voucher.ledger_id == ledger_id,
                            Voucher.status == "posted",
                            func.substr(Voucher.date, 1, 4) == year_str,
                            func.substr(Voucher.date, 6, 2) == month_str,
                            JournalEntry.account_name.like("%投资收益%"),
                        )
                    )
                )
                inv_result = await session.execute(inv_stmt)
                invest_income = round(inv_result.scalar() or 0, 2)

                # 5. Indirect calculation
                operating_cf = net_profit + depreciation + amortization - invest_income
                operating_inflow = max(operating_cf, 0)
                operating_outflow = abs(min(operating_cf, 0))

                detail_rows.append(
                    {
                        "type": "indirect_net_profit",
                        "name": "净利润",
                        "section": "operating",
                        "debit": net_profit,
                        "credit": 0,
                        "net": net_profit,
                    }
                )
                if depreciation > 0:
                    detail_rows.append(
                        {
                            "type": "indirect_depreciation",
                            "name": "加：折旧费用",
                            "section": "operating",
                            "debit": depreciation,
                            "credit": 0,
                            "net": depreciation,
                        }
                    )
                if amortization > 0:
                    detail_rows.append(
                        {
                            "type": "indirect_amortization",
                            "name": "加：摊销费用",
                            "section": "operating",
                            "debit": amortization,
                            "credit": 0,
                            "net": amortization,
                        }
                    )
                if invest_income != 0:
                    detail_rows.append(
                        {
                            "type": "indirect_invest_income",
                            "name": "减：投资收益",
                            "section": "operating",
                            "debit": 0,
                            "credit": invest_income,
                            "net": -invest_income,
                        }
                    )

                net_operating = operating_cf

                # Add investing/financing detail rows for indirect method too
                for row in rows_cf:
                    cf_type = row.cash_flow_type
                    if cf_type.startswith(("investing_", "financing_")):
                        net = row.total_debit - row.total_credit
                        name_map = {
                            "investing_inflow": "投资活动现金流入",
                            "investing_outflow": "投资活动现金流出",
                            "financing_inflow": "筹资活动现金流入",
                            "financing_outflow": "筹资活动现金流出",
                        }
                        detail_rows.append(
                            {
                                "type": cf_type,
                                "name": name_map.get(cf_type, cf_type),
                                "section": cf_type.split("_")[0],
                                "debit": row.total_debit,
                                "credit": row.total_credit,
                                "net": net,
                            }
                        )

            else:
                # ── Direct method: operating from cash flow types ──
                operating_inflow = 0.0
                operating_outflow = 0.0
                for row in rows_cf:
                    cf_type = row.cash_flow_type
                    if cf_type == "operating_inflow":
                        operating_inflow += row.total_debit
                    elif cf_type == "operating_outflow":
                        operating_outflow += row.total_credit

                # If no operating cash flow data, infer from accounts
                if operating_inflow == 0 and operating_outflow == 0:
                    for d in await self._infer_cash_flow(session, ledger_id, year, month):
                        if d["type"] == "operating_inflow":
                            operating_inflow += max(d["net"], 0)
                        elif d["type"] == "operating_outflow":
                            operating_outflow += abs(min(d["net"], 0))
                        detail_rows.append(d)

                # Add operating detail
                for row in rows_cf:
                    cf_type = row.cash_flow_type
                    if cf_type.startswith("operating_"):
                        net = row.total_debit - row.total_credit
                        name = "经营活动现金流入" if "inflow" in cf_type else "经营活动现金流出"
                        detail_rows.append(
                            {
                                "type": cf_type,
                                "name": name,
                                "section": "operating",
                                "debit": row.total_debit,
                                "credit": row.total_credit,
                                "net": net,
                            }
                        )

                net_operating = operating_inflow - operating_outflow

            net_investing = investing_inflow - investing_outflow
            net_financing = financing_inflow - financing_outflow
            net_cash_change = net_operating + net_investing + net_financing

            return {
                "method": method,
                "year": year,
                "month": month,
                "operating": {
                    "inflow": operating_inflow,
                    "outflow": operating_outflow,
                    "net": net_operating,
                },
                "investing": {
                    "inflow": investing_inflow,
                    "outflow": investing_outflow,
                    "net": net_investing,
                },
                "financing": {
                    "inflow": financing_inflow,
                    "outflow": financing_outflow,
                    "net": net_financing,
                },
                "net_cash_change": net_cash_change,
                "detail": detail_rows,
            }

    async def _infer_cash_flow(self, session, ledger_id: int, year: int, month: int) -> list:
        """Infer cash flow categories from account codes (simplified)."""
        cash_accounts = ["1001", "1002", "1012"]
        year_str = str(year)
        month_str = f"{month:02d}"

        stmt = (
            select(
                JournalEntry.account_code,
                JournalEntry.account_name,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            )
            .join(Voucher, JournalEntry.voucher_id == Voucher.id)
            .where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    Voucher.status == "posted",
                    JournalEntry.account_code.in_(cash_accounts),
                    func.substr(Voucher.date, 1, 4) == year_str,
                    func.substr(Voucher.date, 6, 2) == month_str,
                )
            )
            .group_by(JournalEntry.account_code, JournalEntry.account_name)
        )
        result = await session.execute(stmt)
        rows = result.all()

        result_list = []
        for row in rows:
            net = row.total_debit - row.total_credit
            if net > 0:
                result_list.append(
                    {
                        "type": "operating_inflow",
                        "name": "经营活动现金流入",
                        "section": "operating",
                        "debit": row.total_debit,
                        "credit": row.total_credit,
                        "net": net,
                    }
                )
            else:
                result_list.append(
                    {
                        "type": "operating_outflow",
                        "name": "经营活动现金流出",
                        "section": "operating",
                        "debit": row.total_debit,
                        "credit": row.total_credit,
                        "net": net,
                    }
                )
        return result_list

    @staticmethod
    def _category_to_dict(obj) -> dict:
        """Convert CashFlowCategory ORM object to dict matching old sqlite3 format."""
        return {
            "id": obj.id,
            "ledger_id": obj.ledger_id,
            "code": obj.code,
            "name": obj.name,
            "category": obj.category,
            "parent_code": obj.parent_code,
            "is_active": obj.is_active,
            "created_at": obj.created_at,
        }

    async def get_cash_flow_detail(self, ledger_id: int, cf_type: str, year: int, month: int) -> list:
        """Get detailed journal entries for a specific cash flow type."""
        async with get_db() as session:
            date_str = f"{year}-{month:02d}"
            stmt = (
                select(
                    Voucher.voucher_no,
                    Voucher.date,
                    Voucher.description,
                    Account.code.label("acct_code"),
                    Account.name.label("acct_name"),
                    JournalEntry.debit,
                    JournalEntry.credit,
                )
                .join(JournalEntry, JournalEntry.voucher_id == Voucher.id)
                .join(Account, Account.code == JournalEntry.account_code)
                .where(
                    and_(
                        Voucher.ledger_id == ledger_id,
                        JournalEntry.cash_flow_type == cf_type,
                        func.strftime("%Y-%m", Voucher.date) == date_str,
                        Voucher.status == "posted",
                    )
                )
                .order_by(Voucher.date.desc())
                .limit(50)
            )
            result = await session.execute(stmt)
            rows = result.all()
            return [dict(r._mapping) for r in rows]
