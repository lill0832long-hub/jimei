"""凭证审核工作流模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import Base
from .mixins import CreatedAtMixin


class VoucherWorkflow(Base, CreatedAtMixin):
    __tablename__ = "voucher_workflow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    voucher_id = Column(Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    action = Column(Text, nullable=False)
    from_status = Column(Text)
    to_status = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    comment = Column(Text)

    __table_args__ = (
        Index("idx_voucher_wf_voucher", "voucher_id"),
        Index("idx_voucher_wf_ledger", "ledger_id"),
    )

    # Relationships
    voucher = relationship("Voucher", back_populates="workflows")
    ledger = relationship("Ledger")
