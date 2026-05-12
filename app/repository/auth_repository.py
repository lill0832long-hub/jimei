"""Auth repository — users and audit logs."""
from sqlalchemy import select, and_
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.base import get_db
from .base import BaseRepository


class AuthRepository(BaseRepository):
    model = User

    async def get_by_username(self, username: str):
        async with get_db() as session:
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int):
        async with get_db() as session:
            return await session.get(User, user_id)

    async def get_all(self, ledger_id: int = None):
        async with get_db() as session:
            stmt = select(User)
            if ledger_id is not None:
                stmt = stmt.where(User.ledger_id == ledger_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create(self, username: str, password_hash: str, role: str = "user", ledger_id: int = None, **kwargs):
        async with get_db() as session:
            user = User(
                username=username, password_hash=password_hash,
                role=role, ledger_id=ledger_id, **kwargs
            )
            session.add(user)
            await session.flush()
            await session.refresh(user)
            return user

    async def update(self, user_id: int, **kwargs):
        async with get_db() as session:
            user = await session.get(User, user_id)
            if user:
                for k, v in kwargs.items():
                    setattr(user, k, v)
            return user

    async def delete(self, user_id: int) -> bool:
        async with get_db() as session:
            user = await session.get(User, user_id)
            if user:
                await session.delete(user)
                return True
            return False


class AuditRepository(BaseRepository):
    model = AuditLog

    async def get_logs(self, ledger_id: int, limit: int = 50, module: str = None, action: str = None):
        async with get_db() as session:
            stmt = select(AuditLog).where(AuditLog.ledger_id == ledger_id)
            if module:
                stmt = stmt.where(AuditLog.module == module)
            if action:
                stmt = stmt.where(AuditLog.action == action)
            stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def add_log(self, ledger_id: int, action: str, **kwargs):
        async with get_db() as session:
            log = AuditLog(ledger_id=ledger_id, action=action, **kwargs)
            session.add(log)
            await session.flush()
            await session.refresh(log)
            return log
