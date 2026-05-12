"""测试 SQLAlchemy Model — 验证数据库初始化 + 基本 CRUD"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DB_PATH = os.path.join(os.path.dirname(__file__), "test_finance.db")
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

from app.models.base import Base
from app.models import Ledger, User, Account, Voucher, JournalEntry


async def test():
    engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("[OK] 数据库初始化成功")
    print(f"[OK] 共 {len(Base.metadata.tables)} 张表")

    async with Session() as session:
        # 创建账套
        ledger = Ledger(name="测试账套", company="测试公司")
        session.add(ledger)
        await session.commit()
        await session.refresh(ledger)
        print(f"[OK] 创建账套: id={ledger.id}")

        # 创建用户
        user = User(username="admin", password_hash="test_hash", role="admin", ledger_id=ledger.id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"[OK] 创建用户: id={user.id}")

        # 创建科目
        acct = Account(code="1001", name="库存现金", category="资产")
        session.add(acct)
        await session.commit()
        print(f"[OK] 创建科目: code={acct.code}")

        # 创建凭证
        voucher = Voucher(ledger_id=ledger.id, voucher_no="PZ001", date="2026-05-12", status="draft")
        session.add(voucher)
        await session.commit()
        await session.refresh(voucher)
        print(f"[OK] 创建凭证: id={voucher.id}, no={voucher.voucher_no}")

        # 创建分录
        entry = JournalEntry(ledger_id=ledger.id, voucher_id=voucher.id,
                             account_code="1001", account_name="库存现金",
                             debit=1000, credit=0, summary="测试")
        session.add(entry)
        await session.commit()
        print(f"[OK] 创建分录: id={entry.id}")

        # 查询验证
        result = await session.execute(select(Ledger))
        ledgers = result.scalars().all()
        print(f"[OK] 查询账套: {len(ledgers)} 个")

        result = await session.execute(select(Voucher))
        vouchers = result.scalars().all()
        print(f"[OK] 查询凭证: {len(vouchers)} 个")

        result = await session.execute(select(JournalEntry))
        entries = result.scalars().all()
        print(f"[OK] 查询分录: {len(entries)} 个")

    await engine.dispose()
    os.remove(DB_PATH)
    print("[OK] 测试数据库已清理")
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(test())
