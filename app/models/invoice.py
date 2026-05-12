"""发票 + 发票凭证关联模型"""
from sqlalchemy import Column, Integer, Text, Float, ForeignKey, Index, UniqueConstraint
from .base import Base
from .mixins import TimestampMixin, CreatedAtMixin


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    invoice_type = Column(Text, nullable=False, default="input")
    invoice_code = Column(Text)
    invoice_no = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_invoice_ledger", "ledger_id"),
        Index("idx_invoice_status", "status"),
    )
    invoice_date = Column(Text)
    seller_name = Column(Text)
    seller_tax_no = Column(Text)
    buyer_name = Column(Text)
    buyer_tax_no = Column(Text)
    total_amount = Column(Float, default=0)
    tax_amount = Column(Float, default=0)
    total_with_tax = Column(Float, default=0)
    status = Column(Text, default="unverified")
    ocr_data = Column(Text)
    file_path = Column(Text)
    remark = Column(Text)


class InvoiceVoucher(Base, CreatedAtMixin):
    __tablename__ = "invoice_voucher"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    voucher_id = Column(Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("invoice_id", "voucher_id"),
    )
