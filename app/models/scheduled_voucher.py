"""定时凭证任务模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from .base import Base
from .mixins import TimestampMixin, SoftDeleteMixin


class ScheduledVoucher(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "scheduled_vouchers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("idx_scheduled_voucher_ledger", "ledger_id"),
    )
    template_id = Column(Integer, ForeignKey("voucher_templates.id", ondelete="SET NULL"))
    name = Column(Text, nullable=False)
    cron_expression = Column(Text, nullable=False)
    next_run_at = Column(Text)
    last_run_at = Column(Text)
