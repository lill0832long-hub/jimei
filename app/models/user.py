"""用户模型"""
from sqlalchemy import Column, Integer, Text, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base
from .mixins import TimestampMixin, SoftDeleteMixin


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, default="user")
    ledger_id = Column(Integer, ForeignKey("ledgers.id", ondelete="SET NULL"))

    # Relationships
    ledger = relationship("Ledger", back_populates="users")
