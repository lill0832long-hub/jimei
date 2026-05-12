"""凭证 + 凭证明细模型"""
from sqlalchemy import Column, Integer, Text, String, Float, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from .base import Base
from .mixins import TimestampMixin, CreatedAtMixin


class Voucher(Base, TimestampMixin):
    __tablename__ = "vouchers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    voucher_no = Column(Text, unique=True, nullable=False)
    date = Column(Text, nullable=False)
    description = Column(Text)
    total_debit = Column(Float, default=0)
    total_credit = Column(Float, default=0)
    status = Column(Text, default="draft")
    attachment = Column(Text)
    currency = Column(Text, default="CNY")
    attachment_count = Column(Integer, default=0)
    accountant = Column(Text, default="")
    cashier = Column(Text, default="")
    reviewer = Column(Text, default="")

    __table_args__ = (
        Index("idx_voucher_ledger", "ledger_id"),
        Index("idx_voucher_date", "date"),
        Index("idx_voucher_status", "status"),
        Index("idx_voucher_ledger_date", "ledger_id", "date"),
        Index("idx_voucher_ledger_status", "ledger_id", "status"),
    )

    # Relationships
    ledger = relationship("Ledger", back_populates="vouchers")
    journal_entries = relationship("JournalEntry", back_populates="voucher", cascade="all, delete-orphan")
    workflows = relationship("VoucherWorkflow", back_populates="voucher", cascade="all, delete-orphan")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    voucher_id = Column(Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False)
    account_code = Column(Text, nullable=False)
    account_name = Column(Text, nullable=False)
    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    summary = Column(Text)
    foreign_currency = Column(Text)
    foreign_amount = Column(Float, default=0)
    exchange_rate = Column(Float, default=1)
    cash_flow_type = Column(Text)
    tax_type = Column(Text)
    tax_rate = Column(Float, default=0)
    tax_amount = Column(Float, default=0)

    __table_args__ = (
        Index("idx_je_ledger", "ledger_id"),
        Index("idx_je_voucher", "voucher_id"),
        Index("idx_je_account", "account_code"),
        Index("idx_je_ledger_account", "ledger_id", "account_code"),
        Index("idx_je_ledger_voucher", "ledger_id", "voucher_id"),
    )

    # Relationships
    ledger = relationship("Ledger")
    voucher = relationship("Voucher", back_populates="journal_entries")
    auxiliaries = relationship("VoucherEntryAuxiliary", back_populates="entry", cascade="all, delete-orphan")
