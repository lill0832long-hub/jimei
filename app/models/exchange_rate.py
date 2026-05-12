"""汇率模型"""
from sqlalchemy import Column, Integer, Text, Float, Index, UniqueConstraint
from .base import Base
from .mixins import TimestampMixin


class ExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_currency = Column(Text, nullable=False)
    to_currency = Column(Text, nullable=False)
    rate = Column(Float, nullable=False)
    date = Column(Text, nullable=False)
    source = Column(Text, default="manual")

    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "date"),
        Index("idx_er_from_to", "from_currency", "to_currency"),
    )


class ExchangeRateV3(Base):
    __tablename__ = "exchange_rates_v3"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_currency = Column(Text, nullable=False)
    to_currency = Column(Text, nullable=False)
    rate = Column(Float, nullable=False)
    effective_date = Column(Text, nullable=False)
    created_at = Column(Text)
