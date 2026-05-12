"""SQLAlchemy 基础配置 — 异步引擎 + 会话管理"""

import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "finance_v2.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

_async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    def __repr__(self):
        cols = list(self.__table__.columns.keys())
        # Show up to 3 key fields (id + first 2 non-id columns)
        key_cols = ["id"] + [c for c in cols if c != "id"][:(3 if len(cols) > 3 else 2)]
        attrs = ", ".join(f"{c}={getattr(self, c, None)!r}" for c in key_cols if c in cols)
        return f"<{self.__class__.__name__}({attrs})>"


@asynccontextmanager
async def get_db():
    """异步数据库会话上下文管理器 — 自动 commit/rollback/close"""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """创建所有表（如果不存在）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库引擎"""
    await engine.dispose()
