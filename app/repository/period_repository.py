"""Period management repository."""
import calendar
from sqlalchemy import select, and_, text
from app.models.closing_entry import ClosingEntry
from app.models.opening_balance import OpeningBalance
from app.models.voucher import Voucher, JournalEntry
from app.models.base import get_db
from .base import BaseRepository


class PeriodRepository(BaseRepository):
    """期间管理 — opening balances and period closing."""

    async def get_period_status(self, ledger_id: int, year: int, month: int) -> dict:
        """Get period closing status as a dict with closed, voucher_no, closed_at keys."""
        period_str = f"{year:04d}-{month:02d}"
        async with get_db() as session:
            stmt = select(ClosingEntry).where(
                and_(
                    ClosingEntry.ledger_id == ledger_id,
                    ClosingEntry.period == period_str,
                    ClosingEntry.status == "completed",
                )
            )
            result = await session.execute(stmt)
            entry = result.first()
            if entry:
                row = entry[0]
                return {
                    "closed": True,
                    "voucher_no": row.voucher_id or "",
                    "closed_at": str(row.created_at) if row.created_at else "",
                }
            return {"closed": False, "voucher_no": "", "closed_at": ""}

    async def get_opening_balance(self, ledger_id: int, account_code: str, year: int, month: int):
        async with get_db() as session:
            stmt = select(OpeningBalance).where(
                and_(
                    OpeningBalance.ledger_id == ledger_id,
                    OpeningBalance.account_code == account_code,
                    OpeningBalance.year == year,
                    OpeningBalance.month == month,
                )
            )
            result = await session.execute(stmt)
            ob = result.scalar_one_or_none()
            return ob.balance if ob else 0

    async def set_opening_balance(self, ledger_id: int, account_code: str, year: int, month: int, balance: float):
        async with get_db() as session:
            stmt = select(OpeningBalance).where(
                and_(
                    OpeningBalance.ledger_id == ledger_id,
                    OpeningBalance.account_code == account_code,
                    OpeningBalance.year == year,
                    OpeningBalance.month == month,
                )
            )
            result = await session.execute(stmt)
            ob = result.scalar_one_or_none()
            if ob:
                ob.balance = balance
            else:
                ob = OpeningBalance(
                    ledger_id=ledger_id, account_code=account_code,
                    year=year, month=month, balance=balance,
                )
                session.add(ob)
                await session.flush()
            return ob

    async def get_close_period_checklist(self, ledger_id: int, year: int, month: int) -> list:
        """Get period-end closing checklist (items with name/status/description)."""
        period_str = f"{year}-{month:02d}"
        async with get_db() as session:
            items = []

            # 1. Check for unposted vouchers
            unposted = await session.execute(
                text("SELECT COUNT(*) as cnt FROM vouchers WHERE ledger_id=:lid AND status!='posted'"),
                {"lid": ledger_id},
            )
            unposted_cnt = unposted.fetchone()[0]
            items.append({
                "name": "所有凭证已过账",
                "ok": unposted_cnt == 0,
                "desc": f"有 {unposted_cnt} 张凭证未过账" if unposted_cnt else "所有凭证已过账",
            })

            # 2. Check debit-credit balance
            imbalance = await session.execute(
                text(
                    "SELECT v.id, v.voucher_no, v.total_debit, v.total_credit "
                    "FROM vouchers v WHERE v.ledger_id=:lid AND v.status='posted' "
                    "AND ABS(v.total_debit - v.total_credit) > 0.01"
                ),
                {"lid": ledger_id},
            )
            imb_rows = imbalance.fetchall()
            items.append({
                "name": "借贷平衡检查",
                "ok": len(imb_rows) == 0,
                "desc": f"{len(imb_rows)} 张凭证借贷不平衡" if imb_rows else "全部平衡",
            })

            # 3. Check income/expense account balances
            revenue = await session.execute(
                text(
                    "SELECT COALESCE(SUM(je.credit - je.debit), 0) as bal "
                    "FROM journal_entries je JOIN vouchers v ON je.voucher_id=v.id "
                    "WHERE v.ledger_id=:lid AND v.status='posted' "
                    "AND je.account_code LIKE '6%' AND strftime('%Y-%m', v.date) <= :period"
                ),
                {"lid": ledger_id, "period": period_str},
            )
            rev_bal = revenue.fetchone()[0]
            items.append({
                "name": "损益科目余额",
                "ok": True,
                "desc": f"收入类余额 {rev_bal:,.2f}，将结转至本年利润",
            })

            # 4. Check period status
            period_status = await self.get_period_status(ledger_id, year, month)
            items.append({
                "name": "期间状态",
                "ok": not period_status.get("closed", False),
                "desc": f"当前状态: {'已结账' if period_status.get('closed') else '未结账'}",
            })

            return items

    async def close_period(self, ledger_id: int, year: int, month: int,
                           user_id: int = None, operator_name: str = None) -> str:
        """
        Period-end profit/loss transfer: transfer all income/expense balances to '本年利润'.
        Creates a closing voucher. Returns voucher_no, or None if nothing to transfer.
        """
        async with get_db() as session:
            # Check if already closed
            existing = await session.execute(
                text(
                    "SELECT id FROM vouchers WHERE ledger_id = :lid "
                    "AND description LIKE :pattern AND status = 'posted'"
                ),
                {"lid": ledger_id, "pattern": f"%结转{year}年{month}月损益%"},
            )
            if existing.fetchone():
                raise ValueError(f"{year}年{month}月已执行过损益结转")

            # Calculate income/expense net amounts
            income_expense = await session.execute(
                text("""
                    SELECT a.code, a.name, a.category,
                           COALESCE(SUM(je.debit), 0) AS total_dr,
                           COALESCE(SUM(je.credit), 0) AS total_cr
                    FROM accounts a
                    LEFT JOIN journal_entries je ON je.account_code = a.code AND je.ledger_id = :lid
                    LEFT JOIN vouchers v ON je.voucher_id = v.id AND v.status = 'posted'
                        AND strftime('%Y', v.date) = :year AND CAST(strftime('%m', v.date) AS INTEGER) = :month
                    WHERE a.category IN ('收入', '费用') AND a.is_active = 1
                    GROUP BY a.code
                    ORDER BY a.category DESC, a.code
                """),
                {"lid": ledger_id, "year": str(year), "month": month},
            )

            entries = []
            total_income = 0
            total_expense = 0

            for row in income_expense:
                r = dict(row._mapping)
                dr = r["total_dr"]
                cr = r["total_cr"]
                if r["category"] == "收入":
                    net = round(cr - dr, 2)
                    if abs(net) > 0.001:
                        entries.append({
                            "account_code": r["code"], "account_name": r["name"],
                            "debit": net, "credit": 0,
                            "summary": f"结转{year}年{month}月收入",
                        })
                        total_income += net
                elif r["category"] == "费用":
                    net = round(dr - cr, 2)
                    if abs(net) > 0.001:
                        entries.append({
                            "account_code": r["code"], "account_name": r["name"],
                            "debit": 0, "credit": net,
                            "summary": f"结转{year}年{month}月费用",
                        })
                        total_expense += net

            net_profit = total_income - total_expense

            if abs(net_profit) > 0.001:
                if net_profit > 0:
                    entries.append({
                        "account_code": "4103", "account_name": "本年利润",
                        "debit": 0, "credit": round(net_profit, 2),
                        "summary": f"结转{year}年{month}月利润",
                    })
                else:
                    entries.append({
                        "account_code": "4103", "account_name": "本年利润",
                        "debit": round(-net_profit, 2), "credit": 0,
                        "summary": f"结转{year}年{month}月亏损",
                    })

            if not entries:
                return None

            # Verify debit-credit balance
            total_dr = sum(e["debit"] for e in entries)
            total_cr = sum(e["credit"] for e in entries)
            if abs(total_dr - total_cr) > 0.01:
                raise ValueError(f"结转凭证借贷不平衡：借方 {total_dr} != 贷方 {total_cr}")

            # Build voucher
            last_day = calendar.monthrange(year, month)[1]
            date_str = f"{year}-{month:02d}-{last_day:02d}"
            prefix = f"JZ{date_str.replace('-', '')}"
            count_result = await session.execute(
                text("SELECT COUNT(*) FROM vouchers WHERE voucher_no LIKE :prefix AND ledger_id = :lid"),
                {"prefix": prefix + "%", "lid": ledger_id},
            )
            count = count_result.fetchone()[0]
            voucher_no = f"{prefix}{count + 1:04d}"

            # Create voucher
            v_result = await session.execute(
                text(
                    "INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status) "
                    "VALUES (:lid, :vno, :date, :desc, :td, :tc, 'posted')"
                ),
                {
                    "lid": ledger_id, "vno": voucher_no, "date": date_str,
                    "desc": f"结转{year}年{month}月损益",
                    "td": total_dr, "tc": total_cr,
                },
            )
            # Get the new voucher ID
            v_id_result = await session.execute(
                text("SELECT id FROM vouchers WHERE voucher_no = :vno AND ledger_id = :lid"),
                {"vno": voucher_no, "lid": ledger_id},
            )
            voucher_id = v_id_result.fetchone()[0]

            for e in entries:
                await session.execute(
                    text(
                        "INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary) "
                        "VALUES (:lid, :vid, :acode, :aname, :dr, :cr, :summary)"
                    ),
                    {
                        "lid": ledger_id, "vid": voucher_id,
                        "acode": e["account_code"], "aname": e["account_name"],
                        "dr": e["debit"], "cr": e["credit"], "summary": e["summary"],
                    },
                )

            # Record closing entry
            period_str = f"{year:04d}-{month:02d}"
            ce = ClosingEntry(
                ledger_id=ledger_id, period=period_str,
                close_type="month_end", voucher_id=voucher_id, status="completed",
            )
            session.add(ce)

            return voucher_no

    async def reverse_close_period(self, ledger_id: int, year: int, month: int) -> dict:
        """Reverse a period close. Returns dict with success/message."""
        period_str = f"{year:04d}-{month:02d}"
        async with get_db() as session:
            # Check if next period is closed
            if month < 12:
                next_period = f"{year:04d}-{month + 1:02d}"
            else:
                next_period = f"{year + 1:04d}-01"

            next_closed = await session.execute(
                text(
                    "SELECT COUNT(*) as cnt FROM closing_entries "
                    "WHERE ledger_id = :lid AND period = :period AND status = 'completed'"
                ),
                {"lid": ledger_id, "period": next_period},
            )
            if next_closed.fetchone()[0] > 0:
                return {"success": False, "message": f"下一期间 {next_period} 已结账，无法反结账"}

            # Find and delete closing vouchers
            v_rows = await session.execute(
                text(
                    "SELECT id FROM vouchers WHERE ledger_id = :lid "
                    "AND description LIKE :pattern AND status = 'posted'"
                ),
                {"lid": ledger_id, "pattern": f"%结转{year}年{month}月损益%"},
            )
            for v_row in v_rows:
                vid = v_row[0]
                await session.execute(
                    text("DELETE FROM journal_entries WHERE voucher_id = :vid"),
                    {"vid": vid},
                )
                await session.execute(
                    text("DELETE FROM vouchers WHERE id = :vid"),
                    {"vid": vid},
                )

            # Delete closing entries
            await session.execute(
                text("DELETE FROM closing_entries WHERE ledger_id = :lid AND period = :period"),
                {"lid": ledger_id, "period": period_str},
            )

            return {"success": True, "message": f"{year}年{month}月反结账成功"}
