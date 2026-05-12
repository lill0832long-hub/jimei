"""账套模型"""
from sqlalchemy import Column, Integer, Text, String
from sqlalchemy.orm import relationship
from .base import Base
from .mixins import TimestampMixin


class Ledger(Base, TimestampMixin):
    __tablename__ = "ledgers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    company = Column(Text, default="默认公司")
    currency = Column(Text, default="CNY")
    fiscal_year_start = Column(Text)
    fiscal_year_end = Column(Text)
    status = Column(Text, default="active")
    settings = Column(Text)

    # Relationships
    vouchers = relationship("Voucher", back_populates="ledger", cascade="all, delete-orphan")
    users = relationship("User", back_populates="ledger")
