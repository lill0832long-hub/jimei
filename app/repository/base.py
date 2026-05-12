"""Repository base class with common CRUD operations."""
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import get_db
from app.models import Base


class BaseRepository:
    """Base repository providing common async CRUD operations."""

    model = None  # Override in subclass

    def __init__(self, session: AsyncSession = None):
        self._session = session
        self._owns_session = session is None

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def _get_session(self) -> AsyncSession:
        """Get or create a session."""
        if self._session is not None:
            return self._session
        # Return the context manager's session
        return get_db()

    async def get_by_id(self, id: int):
        async with get_db() as session:
            return await session.get(self.model, id)

    async def get_all(self, *, ledger_id: int = None, limit: int = 100, offset: int = 0):
        async with get_db() as session:
            stmt = select(self.model)
            if ledger_id is not None and hasattr(self.model, 'ledger_id'):
                stmt = stmt.where(self.model.ledger_id == ledger_id)
            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create(self, **kwargs):
        async with get_db() as session:
            obj = self.model(**kwargs)
            session.add(obj)
            await session.flush()
            await session.refresh(obj)
            return obj

    async def update(self, id: int, **kwargs):
        async with get_db() as session:
            obj = await session.get(self.model, id)
            if obj:
                for k, v in kwargs.items():
                    setattr(obj, k, v)
                await session.flush()
            return obj

    async def delete(self, id: int) -> bool:
        async with get_db() as session:
            obj = await session.get(self.model, id)
            if obj:
                await session.delete(obj)
                return True
            return False

    async def count(self, *, ledger_id: int = None):
        async with get_db() as session:
            stmt = select(func.count()).select_from(self.model)
            if ledger_id is not None and hasattr(self.model, 'ledger_id'):
                stmt = stmt.where(self.model.ledger_id == ledger_id)
            result = await session.execute(stmt)
            return result.scalar()
