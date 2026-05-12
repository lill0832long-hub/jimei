"""固定资产卡片 + 资产变动记录模型"""
from sqlalchemy import Column, Integer, Text, Float, ForeignKey, Index
from .base import Base
from .mixins import TimestampMixin, CreatedAtMixin


class FixedAsset(Base, TimestampMixin):
    __tablename__ = "fixed_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="CASCADE"), nullable=False)
    asset_code = Column(Text, nullable=False)
    asset_name = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("fa_categories.id"))
    purchase_date = Column(Text)
    original_value = Column(Integer, nullable=False, default=0)
    residual_rate = Column(Float, default=0.05)
    residual_value = Column(Integer, default=0)
    useful_life_months = Column(Integer, nullable=False, default=120)
    depreciation_method = Column(Text, default="straight_line")
    accumulated_depreciation = Column(Integer, default=0)
    net_value = Column(Integer, default=0)
    department = Column(Text)
    employee = Column(Text)
    location = Column(Text)
    status = Column(Text, default="in_use")
    source_type = Column(Text, default="purchase")

    __table_args__ = (
        Index("idx_fixed_asset_ledger", "ledger_id"),
    )


class FaChange(Base, CreatedAtMixin):
    __tablename__ = "fa_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False)
    change_type = Column(Text, nullable=False)
    change_date = Column(Text)
    old_value = Column(Integer)
    new_value = Column(Integer)
    reason = Column(Text)
    voucher_id = Column(Integer)
