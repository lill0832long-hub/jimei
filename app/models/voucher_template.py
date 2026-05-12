"""凭证模板模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, UniqueConstraint
from .base import Base
from .mixins import TimestampMixin, SoftDeleteMixin


class VoucherTemplate(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "voucher_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    voucher_type = Column(Text, default="记")
    category = Column(Text, default="general")
    entries = Column(Text, nullable=False)
    is_system = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("ledger_id", "name"),
    )
