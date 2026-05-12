"""Account repository — accounts, bank accounts, bank statements, auxiliary categories."""
from sqlalchemy import select, and_, func
from app.models.account import Account
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

    async def match_statement(self, statement_id: int, journal_id: int):
        async with get_db() as session:
            stmt = await session.get(BankStatement, statement_id)
            if stmt:
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
