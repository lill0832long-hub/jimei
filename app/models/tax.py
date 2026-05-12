"""增值税配置 + 税率模型"""
from sqlalchemy import Column, Integer, Text, Float, ForeignKey, UniqueConstraint
from .base import Base
from .mixins import TimestampMixin, CreatedAtMixin, SoftDeleteMixin


class TaxConfig(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tax_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    taxpayer_type = Column(Text, default="general")
    default_tax_rate = Column(Float, default=0.13)

    __table_args__ = (
        UniqueConstraint("ledger_id"),
    )


class TaxRate(Base, CreatedAtMixin, SoftDeleteMixin):
    __tablename__ = "tax_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    rate = Column(Float, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    is_default = Column(Integer, default=0)
