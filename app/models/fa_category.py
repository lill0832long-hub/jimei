"""固定资产类别模型"""
from sqlalchemy import Column, Integer, Text, Float, ForeignKey
from .base import Base
from .mixins import CreatedAtMixin


class FaCategory(Base, CreatedAtMixin):
    __tablename__ = "fa_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    default_life_months = Column(Integer)
    default_residual_rate = Column(Float, default=0.05)
