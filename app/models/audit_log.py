"""审计日志模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from .base import Base
from .mixins import CreatedAtMixin


class AuditLog(Base, CreatedAtMixin):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    action = Column(Text, nullable=False)
    detail = Column(Text)
    voucher_id = Column(Integer)
    user_id = Column(Integer)

    __table_args__ = (
        Index("idx_audit_ledger", "ledger_id"),
    )
    operator_name = Column(Text)
    module = Column(Text)
    target_table = Column(Text)
    target_id = Column(Integer)
    old_value = Column(Text)
    new_value = Column(Text)
    ip_address = Column(Text)
    remark = Column(Text)
