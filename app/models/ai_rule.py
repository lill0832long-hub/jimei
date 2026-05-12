"""AI 业务规则模型"""
from sqlalchemy import Column, Integer, Text, Index
from .base import Base
from .mixins import TimestampMixin, SoftDeleteMixin


class AiRuleComplex(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ai_rules_complex"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    pattern = Column(Text, nullable=False)
    description = Column(Text)
    entries_json = Column(Text, nullable=False)
    priority = Column(Integer, default=50)
    usage_count = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_ai_rules_complex_pattern", "pattern"),
        Index("idx_ai_rules_complex_priority", "priority"),
    )
