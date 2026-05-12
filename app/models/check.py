"""支票管理模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from .base import Base
from .mixins import CreatedAtMixin


class Check(Base, CreatedAtMixin):
    __tablename__ = "checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False)
    check_no = Column(Text, nullable=False)
    issue_date = Column(Text)
    payee = Column(Text)
    amount = Column(Integer, default=0)
    status = Column(Text, default="issued")
    voucher_id = Column(Integer)

    __table_args__ = (
        Index("idx_check_bank_account", "bank_account_id"),
    )
