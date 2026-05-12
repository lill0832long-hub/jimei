"""现金盘点模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from .base import Base
from .mixins import CreatedAtMixin


class CashCheck(Base, CreatedAtMixin):
    __tablename__ = "cash_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("idx_cash_check_ledger", "ledger_id"),
    )
    check_date = Column(Text, nullable=False)
    book_balance = Column(Integer, default=0)
    actual_balance = Column(Integer, default=0)
    difference = Column(Integer, default=0)
    handler = Column(Text)
    remark = Column(Text)
