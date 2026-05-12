"""科目模型"""
from sqlalchemy import Column, Integer, Text
from .base import Base
from .mixins import CreatedAtMixin, SoftDeleteMixin


class Account(Base, CreatedAtMixin, SoftDeleteMixin):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    sub_category = Column(Text)
    parent_code = Column(Text)
