"""Shared ORM mixins for SQLAlchemy models."""
from sqlalchemy import Column, Integer, Text


class TimestampMixin:
    """Adds created_at and updated_at timestamp columns."""
    created_at = Column(Text)
    updated_at = Column(Text)


class CreatedAtMixin:
    """Adds only created_at (for child/transactional models that don't need updated_at)."""
    created_at = Column(Text)


class SoftDeleteMixin:
    """Adds is_active flag for soft-delete pattern."""
    is_active = Column(Integer, default=1)
