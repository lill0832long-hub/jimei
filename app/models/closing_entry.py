"""期末结转记录模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from .base import Base
from .mixins import CreatedAtMixin


class ClosingEntry(Base, CreatedAtMixin):
    __tablename__ = "closing_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    period = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_closing_ledger", "ledger_id"),
        Index("idx_closing_period", "period"),
    )
    close_type = Column(Text, nullable=False)
    voucher_id = Column(Integer)
    status = Column(Text, default="pending")
