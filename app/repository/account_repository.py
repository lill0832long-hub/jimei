"""Account repository — accounts, bank accounts, bank statements, auxiliary categories."""
from sqlalchemy import select, and_, or_, func, text
from app.models.account import Account
from app.models.voucher import Voucher, JournalEntry
from app.models.bank_account import BankAccount, BankStatement
from app.models.auxiliary import AuxiliaryCategory, VoucherEntryAuxiliary
from app.models.base import get_db
from .base import BaseRepository


class AccountRepository(BaseRepository):
    """科目管理"""

    model = Account

    async def get_all(self, category: str = None, active_only: bool = True):
        async with get_db() as session:
            stmt = select(Account)
            if category:
                stmt = stmt.where(Account.category == category)
            if active_only:
                stmt = stmt.where(Account.is_active == 1)
            stmt = stmt.order_by(Account.code)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_by_code(self, code: str):
        async with get_db() as session:
            stmt = select(Account).where(Account.code == code)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def search(self, keyword: str, limit: int = 10):
        async with get_db() as session:
            stmt = select(Account).where(
                (Account.code.contains(keyword)) | (Account.name.contains(keyword))
            ).where(Account.is_active == 1).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create(self, code, name, category, **kwargs):
        async with get_db() as session:
            account = Account(code=code, name=name, category=category, **kwargs)
            session.add(account)
            await session.flush()
            await session.refresh(account)
            return account

    async def get_defaults(self):
        """Get default chart of accounts (predefined accounts)."""
        async with get_db() as session:
            stmt = select(Account).where(Account.is_active == 1).order_by(Account.code)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def import_from_template(self, ledger_id: int, system_type: str = "small_business") -> int:
        """从模板导入预设科目. Returns count of newly imported accounts."""
        from database.account import get_default_accounts
        accounts = get_default_accounts(system_type)
        imported = 0
        async with get_db() as session:
            for acc in accounts:
                code, name, cat, sub, parent = acc
                existing = await session.execute(
                    select(Account).where(Account.code == code)
                )
                if existing.scalar_one_or_none():
                    continue
                account = Account(code=code, name=name, category=cat,
                                  sub_category=sub, parent_code=parent)
                session.add(account)
                imported += 1
            await session.flush()
        return imported

    async def get_suggestions(self, ledger_id: int, keyword: str, limit: int = 5) -> list:
        """根据摘要关键词推荐科目"""
        keyword_map = {
            "差旅": ["560201", "660201"],
            "办公": ["560202", "660202"],
            "工资": ["560203", "660203", "2211"],
            "折旧": ["560204", "660204", "1602"],
            "租金": ["5602", "6602"],
            "水电": ["5602", "6602"],
            "银行": ["1002", "5603", "6603"],
            "利息": ["5603", "6603"],
            "销售": ["5601", "6601"],
            "广告": ["5601", "6601"],
            "采购": ["1401", "1403", "5001", "6401"],
            "存货": ["1405", "5001", "6401"],
            "收入": ["5001", "6001"],
            "收款": ["1002", "1122"],
            "付款": ["1002", "2202"],
            "税费": ["2221", "5403", "6403"],
            "所得税": ["5801", "6801"],
            "固定资产": ["1601", "1602"],
            "借款": ["2001", "2501"],
        }
        matched_codes = set()
        for kw, codes in keyword_map.items():
            if kw in keyword:
                matched_codes.update(codes)
        if not matched_codes:
            return []
        async with get_db() as session:
            stmt = select(Account).where(
                Account.code.in_(list(matched_codes)),
                Account.is_active == 1,
            ).order_by(Account.code).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_avg_amount(self, ledger_id: int, account_code: str, months: int = 3):
        """获取某科目最近 N 个月的平均发生金额"""
        async with get_db() as session:
            stmt = select(
                func.avg(JournalEntry.debit + JournalEntry.credit).label("avg_amount")
            ).join(
                Voucher, JournalEntry.voucher_id == Voucher.id
            ).where(
                JournalEntry.ledger_id == ledger_id,
                JournalEntry.account_code == account_code,
                Voucher.status == "posted",
                Voucher.date >= text(f"date('now', '-{months} months')"),
            )
            result = await session.execute(stmt)
            row = result.fetchone()
            return row[0] if row and row[0] else 0

    async def count_journal_entries(self, account_code: str) -> int:
        """Count journal entries referencing an account code."""
        async with get_db() as session:
            stmt = select(func.count()).select_from(JournalEntry).where(
                JournalEntry.account_code == account_code
            )
            result = await session.execute(stmt)
            return result.scalar()


class BankAccountRepository(BaseRepository):
    """银行账号管理"""

    model = BankAccount

    async def get_by_ledger(self, ledger_id: int):
        async with get_db() as session:
            stmt = select(BankAccount).where(
                and_(BankAccount.ledger_id == ledger_id, BankAccount.is_active == 1)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create(self, ledger_id: int, account_no: str, **kwargs):
        async with get_db() as session:
            acct = BankAccount(ledger_id=ledger_id, account_no=account_no, **kwargs)
            session.add(acct)
            await session.flush()
            await session.refresh(acct)
            return acct

    async def get_statements(self, bank_account_id: int):
        async with get_db() as session:
            stmt = select(BankStatement).where(
                BankStatement.bank_account_id == bank_account_id
            ).order_by(BankStatement.statement_date.desc())
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_unmatched_statements(self, bank_account_id: int):
        async with get_db() as session:
            stmt = select(BankStatement).where(
                and_(
                    BankStatement.bank_account_id == bank_account_id,
                    BankStatement.is_matched == 0,
                )
            ).order_by(BankStatement.statement_date)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def add_statement(self, bank_account_id: int, **kwargs):
        async with get_db() as session:
            stmt = BankStatement(bank_account_id=bank_account_id, **kwargs)
            session.add(stmt)
            await session.flush()
            await session.refresh(stmt)
            return stmt

    async def match_statement(self, statement_id: int, journal_id: int = None, voucher_no: str = None):
        """Match a bank statement to a journal entry.
        Provide either journal_id (direct) or voucher_no (will be resolved to a journal entry).
        """
        from app.models.voucher import Voucher, JournalEntry
        async with get_db() as session:
            if journal_id is None and voucher_no is not None:
                # Resolve voucher_no -> journal_entry id
                v_stmt = select(Voucher).where(Voucher.voucher_no == voucher_no)
                v_result = await session.execute(v_stmt)
                voucher = v_result.scalar_one_or_none()
                if voucher:
                    # Get the first journal entry for this voucher
                    je_stmt = select(JournalEntry).where(
                        JournalEntry.voucher_id == voucher.id
                    ).limit(1)
                    je_result = await session.execute(je_stmt)
                    je = je_result.scalar_one_or_none()
                    journal_id = je.id if je else None
            stmt = await session.get(BankStatement, statement_id)
            if stmt and journal_id is not None:
                stmt.is_matched = 1
                stmt.matched_journal_id = journal_id
            return stmt

    async def unmatch_statement(self, statement_id: int):
        async with get_db() as session:
            stmt = await session.get(BankStatement, statement_id)
            if stmt:
                stmt.is_matched = 0
                stmt.matched_journal_id = None
            return stmt

    async def import_statements(self, bank_account_id: int, rows: list) -> int:
        """导入银行对账单. rows: list of dicts with statement_date, transaction_date, summary, debit, credit, reference_no"""
        imported = 0
        async with get_db() as session:
            for row in rows:
                stmt = BankStatement(
                    bank_account_id=bank_account_id,
                    statement_date=row.get("statement_date"),
                    transaction_date=row.get("transaction_date"),
                    summary=row.get("summary", ""),
                    debit=int(row.get("debit") or 0),
                    credit=int(row.get("credit") or 0),
                    reference_no=row.get("reference_no", ""),
                )
                session.add(stmt)
                imported += 1
            await session.flush()
        return imported

    async def auto_match(self, bank_account_id: int) -> int:
        """自动银行对账（按金额+日期匹配）. Returns count of newly matched statements."""
        async with get_db() as session:
            stmt = select(BankStatement).where(
                and_(
                    BankStatement.bank_account_id == bank_account_id,
                    BankStatement.is_matched == 0,
                )
            ).order_by(BankStatement.transaction_date)
            result = await session.execute(stmt)
            statements = result.scalars().all()

            if not statements:
                return 0

            bank_acct = await session.get(BankAccount, bank_account_id)
            if not bank_acct:
                return 0
            ledger_id = bank_acct.ledger_id

            # Batch: collect all unique dates from statements
            dates = list({s.transaction_date for s in statements})

            # Batch: fetch all candidate journal entries for all dates in one query
            entry_stmt = select(JournalEntry, Voucher.date.label("vdate")).join(
                Voucher, JournalEntry.voucher_id == Voucher.id
            ).where(
                Voucher.ledger_id == ledger_id,
                Voucher.date.in_(dates),
            )
            entry_result = await session.execute(entry_stmt)
            all_entries = entry_result.all()

            # Build lookup: (date, debit, credit) -> entry
            entry_map = {}
            for row in all_entries:
                vdate = row.vdate
                entry = row[0]  # JournalEntry
                key = (vdate, int(entry.debit or 0), int(entry.credit or 0))
                if key not in entry_map:
                    entry_map[key] = entry

            # Match in memory
            matched = 0
            for s in statements:
                key = (s.transaction_date, int(s.debit or 0), int(s.credit or 0))
                entry = entry_map.get(key)
                if entry:
                    s.is_matched = 1
                    s.matched_journal_id = entry.id
                    matched += 1
            await session.flush()
            return matched

    async def get_reconciliation(self, bank_account_id: int) -> dict:
        """获取余额调节表数据"""
        async with get_db() as session:
            # 银行对账单余额
            bank_balance_stmt = select(
                func.coalesce(func.sum(BankStatement.debit - BankStatement.credit), 0).label("balance")
            ).where(BankStatement.bank_account_id == bank_account_id)
            bank_balance = (await session.execute(bank_balance_stmt)).scalar()

            # 企业账面余额
            bank_acct = await session.get(BankAccount, bank_account_id)
            book_balance = bank_acct.current_balance if bank_acct else 0

            # 银行已收企业未收
            bank_recv_stmt = select(
                func.coalesce(func.sum(BankStatement.debit), 0).label("total")
            ).where(
                BankStatement.bank_account_id == bank_account_id,
                BankStatement.is_matched == 0,
                BankStatement.debit > 0,
            )
            bank_recv = (await session.execute(bank_recv_stmt)).scalar()

            # 银行已付企业未付
            bank_pay_stmt = select(
                func.coalesce(func.sum(BankStatement.credit), 0).label("total")
            ).where(
                BankStatement.bank_account_id == bank_account_id,
                BankStatement.is_matched == 0,
                BankStatement.credit > 0,
            )
            bank_pay = (await session.execute(bank_pay_stmt)).scalar()

            adjusted_bank = bank_balance + bank_recv - bank_pay

            return {
                "bank_balance": bank_balance,
                "book_balance": book_balance,
                "bank_recv_not_book": bank_recv,
                "bank_pay_not_book": bank_pay,
                "adjusted_bank_balance": adjusted_bank,
                "difference": book_balance - adjusted_bank,
            }


class AuxiliaryRepository(BaseRepository):
    """辅助核算管理"""

    model = AuxiliaryCategory

    async def get_by_ledger(self, ledger_id: int, aux_type: str = None):
        async with get_db() as session:
            stmt = select(AuxiliaryCategory).where(
                AuxiliaryCategory.ledger_id == ledger_id
            )
            if aux_type:
                stmt = stmt.where(AuxiliaryCategory.aux_type == aux_type)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create(self, ledger_id: int, aux_type: str, code: str, name: str, **kwargs):
        async with get_db() as session:
            aux = AuxiliaryCategory(
                ledger_id=ledger_id, aux_type=aux_type,
                code=code, name=name, **kwargs
            )
            session.add(aux)
            await session.flush()
            await session.refresh(aux)
            return aux

    async def get_entry_auxiliaries(self, entry_id: int):
        """Get auxiliary mappings for a journal entry."""
        async with get_db() as session:
            stmt = select(VoucherEntryAuxiliary).where(
                VoucherEntryAuxiliary.entry_id == entry_id
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def save_entry_auxiliary(self, entry_id: int, aux_type: str, aux_id: int, aux_name: str = ""):
        async with get_db() as session:
            mapping = VoucherEntryAuxiliary(
                entry_id=entry_id, aux_type=aux_type,
                aux_id=aux_id, aux_name=aux_name,
            )
            session.add(mapping)
            await session.flush()
            return mapping

    async def save_aux_mapping(self, entry_id: int, aux_type: str, aux_id: int, aux_name: str = None):
        """Save auxiliary mapping for an entry — deletes existing mapping for same entry+type first."""
        async with get_db() as session:
            await session.execute(
                text("DELETE FROM voucher_entry_auxiliaries WHERE entry_id = :eid AND aux_type = :at"),
                {"eid": entry_id, "at": aux_type},
            )
            if aux_id:
                mapping = VoucherEntryAuxiliary(
                    entry_id=entry_id, aux_type=aux_type,
                    aux_id=aux_id, aux_name=aux_name or "",
                )
                session.add(mapping)
                await session.flush()
                return mapping
            return None

    async def get_aux_mapping(self, entry_id: int) -> list:
        """Get all auxiliary mappings for a journal entry, returned as list of dicts."""
        async with get_db() as session:
            stmt = select(VoucherEntryAuxiliary).where(
                VoucherEntryAuxiliary.entry_id == entry_id
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id, "entry_id": r.entry_id,
                    "aux_type": r.aux_type, "aux_id": r.aux_id, "aux_name": r.aux_name,
                }
                for r in rows
            ]

    async def get_aux_balance(self, ledger_id: int, aux_type: str, year: int = None, month: int = None) -> list:
        """Auxiliary balance report: aggregate debit/credit per auxiliary item."""
        date_filter = ""
        params = {"ledger_id": ledger_id, "aux_type": aux_type}
        if year is not None:
            date_filter += " AND strftime('%Y', v.date) = :year"
            params["year"] = str(year)
        if month is not None:
            date_filter += " AND strftime('%m', v.date) = :month"
            params["month"] = f"{month:02d}"
        sql = (
            "SELECT ac.id as aux_id, ac.code as aux_code, ac.name as aux_name, ac.aux_type, "
            "COALESCE(SUM(CASE WHEN je.amount > 0 THEN je.amount ELSE 0 END), 0) as total_debit, "
            "COALESCE(SUM(CASE WHEN je.amount < 0 THEN ABS(je.amount) ELSE 0 END), 0) as total_credit "
            "FROM auxiliary_categories ac "
            "LEFT JOIN voucher_entry_auxiliaries vea ON vea.aux_id = ac.id AND vea.aux_type = ac.aux_type "
            "LEFT JOIN journal_entries je ON je.id = vea.entry_id "
            "LEFT JOIN vouchers v ON v.id = je.voucher_id AND v.ledger_id = :ledger_id "
            "WHERE ac.ledger_id = :ledger_id AND ac.aux_type = :aux_type AND ac.is_active = 1 "
            + date_filter + " "
            "GROUP BY ac.id, ac.code, ac.name, ac.aux_type ORDER BY ac.code"
        )
        async with get_db() as session:
            result = await session.execute(text(sql), params)
            return [dict(r._mapping) for r in result]

    async def multi_aux_search(self, ledger_id: int, aux_filters: list, year: int = None, month: int = None) -> list:
        """Multi-dimensional cross query: aux_filters = [(aux_type, aux_id), ...]."""
        if not aux_filters:
            return []
        joins = []
        where_parts = ["v.ledger_id = :ledger_id"]
        params = {"ledger_id": ledger_id}
        date_filter = ""
        for i, (atype, aid) in enumerate(aux_filters):
            alias = f"vea{i}"
            joins.append(f"INNER JOIN voucher_entry_auxiliaries {alias} ON {alias}.entry_id = je.id")
            where_parts.append(f"{alias}.aux_type = :atype{i} AND {alias}.aux_id = :aid{i}")
            params[f"atype{i}"] = atype
            params[f"aid{i}"] = aid
        if year is not None:
            date_filter += " AND strftime('%Y', v.date) = :year"
            params["year"] = str(year)
        if month is not None:
            date_filter += " AND strftime('%m', v.date) = :month"
            params["month"] = f"{month:02d}"
        join_str = " ".join(joins)
        where_str = " AND ".join(where_parts)
        sql = (
            "SELECT DISTINCT v.voucher_no, v.date, v.summary, v.total_debit, v.total_credit, v.status "
            "FROM vouchers v "
            "INNER JOIN journal_entries je ON je.voucher_id = v.id "
            + join_str + " "
            "WHERE " + where_str + " " + date_filter + " "
            "ORDER BY v.date DESC, v.voucher_no DESC"
        )
        async with get_db() as session:
            result = await session.execute(text(sql), params)
            return [dict(r._mapping) for r in result]
