"""期初余额模型"""
from sqlalchemy import Column, Integer, Text, Float, ForeignKey, Index, UniqueConstraint
from .base import Base


class OpeningBalance(Base):
    __tablename__ = "opening_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    account_code = Column(Text, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    balance = Column(Float, default=0)

    __table_args__ = (
        UniqueConstraint("ledger_id", "account_code", "year", "month"),
        Index("idx_ob_ledger", "ledger_id"),
    )
