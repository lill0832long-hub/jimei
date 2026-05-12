"""现金流分类模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, UniqueConstraint
from .base import Base
from .mixins import CreatedAtMixin, SoftDeleteMixin


class CashFlowCategory(Base, CreatedAtMixin, SoftDeleteMixin):
    __tablename__ = "cash_flow_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    code = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    parent_code = Column(Text)
    __table_args__ = (
        UniqueConstraint("ledger_id", "code"),
    )
