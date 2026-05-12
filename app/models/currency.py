"""币种模型"""
from sqlalchemy import Column, Integer, Text, Boolean, Index
from .base import Base
from .mixins import TimestampMixin, SoftDeleteMixin


class Currency(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "currencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    symbol = Column(Text, default="")
    is_base = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_currency_code", "code"),
        Index("idx_currency_active", "is_active"),
    )
