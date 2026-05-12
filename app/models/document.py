"""文档模型"""
from sqlalchemy import Column, Integer, Text, ForeignKey, Index
from .base import Base
from .mixins import CreatedAtMixin


class Document(Base, CreatedAtMixin):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(Text, nullable=False)
    file_type = Column(Text)
    file_size = Column(Integer)
    file_path = Column(Text)
    processing_status = Column(Text, default="pending")
    ocr_text = Column(Text)
    extracted_data = Column(Text)

    __table_args__ = (
        Index("idx_document_ledger", "ledger_id"),
    )
