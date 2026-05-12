"""银行账户 + 银行对账单模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from .base import Base
from .mixins import CreatedAtMixin, SoftDeleteMixin


class BankAccount(Base, CreatedAtMixin, SoftDeleteMixin):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    account_no = Column(Text, nullable=False)
    bank_name = Column(Text)
    account_name = Column(Text)
    currency_code = Column(Text, default="CNY")
    opening_balance = Column(Integer, default=0)
    current_balance = Column(Integer, default=0)
    subject_code = Column(Text)

    __table_args__ = (
        Index("idx_bank_account_ledger", "ledger_id"),
    )


class BankStatement(Base, CreatedAtMixin):
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False)
    statement_date = Column(Text)
    transaction_date = Column(Text)
    summary = Column(Text)
    debit = Column(Integer, default=0)
    credit = Column(Integer, default=0)
    reference_no = Column(Text)
    is_matched = Column(Integer, default=0)
    matched_journal_id = Column(Integer)

    __table_args__ = (
        Index("idx_bank_stmt_account", "bank_account_id"),
    )
