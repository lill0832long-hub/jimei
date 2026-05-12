"""预算 + 预算执行记录模型"""
from sqlalchemy import Column, Integer, Text, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import Base
from .mixins import TimestampMixin, CreatedAtMixin


class Budget(Base, TimestampMixin):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("idx_budget_ledger", "ledger_id"),
    )
    account_code = Column(Text, nullable=False)
    account_name = Column(Text, nullable=False)
    budget_year = Column(Integer, nullable=False)
    budget_month = Column(Integer)
    budget_amount = Column(Float, nullable=False, default=0)
    description = Column(Text)


class BudgetExecution(Base, CreatedAtMixin):
    __tablename__ = "budget_execution"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="SET NULL"))
    account_code = Column(Text, nullable=False)
    budget_year = Column(Integer, nullable=False)
    budget_month = Column(Integer, nullable=False)
    actual_amount = Column(Float, nullable=False, default=0)

    __table_args__ = (
        Index("idx_budget_exec_ledger", "ledger_id"),
    )
