"""辅助核算类别 + 凭证分录辅助核算关联模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import Base
from .mixins import CreatedAtMixin, SoftDeleteMixin


class AuxiliaryCategory(Base, CreatedAtMixin, SoftDeleteMixin):
    __tablename__ = "auxiliary_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("idx_aux_cat_ledger", "ledger_id"),
    )
    aux_type = Column(Text, nullable=False)
    code = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    parent_id = Column(Integer)


class VoucherEntryAuxiliary(Base, CreatedAtMixin):
    __tablename__ = "voucher_entry_auxiliaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    aux_type = Column(Text, nullable=False)
    aux_id = Column(Integer, nullable=False)
    aux_name = Column(Text)

    __table_args__ = (
        Index("idx_aux_entry", "entry_id"),
    )

    # Relationships
    entry = relationship("JournalEntry", back_populates="auxiliaries")
