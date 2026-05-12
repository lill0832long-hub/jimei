"""验收测试 — 完整业务流程 + 性能对比 + 异常场景"""
import asyncio
import os
import time
import sys

sys.path.insert(0, os.path.dirname(__file__))

TEST_DB = "test_integration.db"


async def setup_db():
    """Initialize a fresh test database."""
    from app.models.base import Base, engine, init_db, close_db
    # Override DB path for testing
    import app.models.base as bm
    bm.DB_PATH = TEST_DB
    bm.DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB}"
    bm.engine = bm.create_async_engine(
        bm.DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
    )
    bm._async_session_factory = bm.async_sessionmaker(
        bm.engine, class_=bm.AsyncSession, expire_on_commit=False
    )
    await init_db()
    return close_db


def cleanup_db():
    """Remove test database files."""
    for suffix in ["", "-shm", "-wal"]:
        path = TEST_DB + suffix
        if os.path.exists(path):
            os.remove(path)


# ═══════════════════════════════════════════════════════════════
# Test 1: 完整业务流程
# ═══════════════════════════════════════════════════════════════

async def test_full_workflow():
    """完整业务流程：创建账套 → 初始化科目 → 创建凭证 → 审核 → 结账"""
    from app.repository.ledger_repository import LedgerRepository
    from app.repository.account_repository import AccountRepository
    from app.repository.voucher_repository import VoucherRepository
    from app.repository.period_repository import PeriodRepository
    from app.repository.budget_repository import BudgetRepository
    from app.repository.tax_repository import TaxRepository
    from app.repository.auth_repository import AuthRepository
    from app.repository.report_repository import ReportRepository

    ledger_repo = LedgerRepository()
    account_repo = AccountRepository()
    voucher_repo = VoucherRepository()
    period_repo = PeriodRepository()
    budget_repo = BudgetRepository()
    tax_repo = TaxRepository()
    auth_repo = AuthRepository()
    report_repo = ReportRepository()

    results = []

    # ── Step 1: 创建账套 ──
    print("\n── Step 1: 创建账套 ──")
    ledger = await ledger_repo.create(
        name="测试账套", company="测试公司", currency="CNY"
    )
    assert ledger.id > 0, "账套创建失败"
    assert ledger.name == "测试账套"
    print(f"  [OK] 账套创建: id={ledger.id}, name={ledger.name}")
    results.append(("创建账套", True))

    # ── Step 2: 初始化科目 ──
    print("\n── Step 2: 初始化科目 ──")
    accounts_data = [
        ("1001", "库存现金", "资产"),
        ("1002", "银行存款", "资产"),
        ("1122", "应收账款", "资产"),
        ("2202", "应付账款", "负债"),
        ("3001", "实收资本", "权益"),
        ("6001", "主营业务收入", "收入"),
        ("6401", "主营业务成本", "费用"),
    ]
    created_accounts = []
    for code, name, category in accounts_data:
        acct = await account_repo.create(code=code, name=name, category=category)
        created_accounts.append(acct)
    assert len(created_accounts) == 7, f"科目创建数量不对: {len(created_accounts)}"
    print(f"  [OK] 创建 {len(created_accounts)} 个科目")
    results.append(("初始化科目", True))

    # ── Step 3: 设置期初余额 ──
    print("\n── Step 3: 设置期初余额 ──")
    ob = await period_repo.set_opening_balance(
        ledger_id=ledger.id, account_code="1001",
        year=2026, month=1, balance=100000
    )
    assert ob.balance == 100000
    print(f"  [OK] 库存现金期初余额: {ob.balance}")
    results.append(("设置期初余额", True))

    # ── Step 4: 创建凭证（多笔） ──
    print("\n── Step 4: 创建凭证 ──")
    vouchers = []

    # 凭证1: 收到投资款
    v1 = await voucher_repo.create_with_entries(
        ledger_id=ledger.id,
        date="2026-01-05",
        description="收到股东投资款",
        entries=[
            {"account_code": "1002", "account_name": "银行存款", "debit": 500000, "credit": 0},
            {"account_code": "3001", "account_name": "实收资本", "debit": 0, "credit": 500000},
        ],
    )
    vouchers.append(v1)
    assert v1.total_debit == 500000
    assert v1.total_credit == 500000
    print(f"  [OK] 凭证1: {v1.voucher_no}, debit={v1.total_debit}, credit={v1.total_credit}")

    # 凭证2: 采购付款
    v2 = await voucher_repo.create_with_entries(
        ledger_id=ledger.id,
        date="2026-01-10",
        description="支付供应商货款",
        entries=[
            {"account_code": "2202", "account_name": "应付账款", "debit": 30000, "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": 30000},
        ],
    )
    vouchers.append(v2)
    print(f"  [OK] 凭证2: {v2.voucher_no}")

    # 凭证3: 确认收入
    v3 = await voucher_repo.create_with_entries(
        ledger_id=ledger.id,
        date="2026-01-20",
        description="确认主营业务收入",
        entries=[
            {"account_code": "1122", "account_name": "应收账款", "debit": 113000, "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": 100000},
        ],
    )
    vouchers.append(v3)
    print(f"  [OK] 凭证3: {v3.voucher_no}")

    assert len(vouchers) == 3
    results.append(("创建凭证", True))

    # ── Step 5: 凭证审核流程 ──
    print("\n── Step 5: 凭证审核流程 ──")
    for v in vouchers:
        # 提交审核
        await voucher_repo.update_status(
            v.voucher_no, "pending_review", action="submit"
        )
        updated = await voucher_repo.get_by_no(ledger.id, v.voucher_no)
        assert updated.status == "pending_review", f"提交审核失败: {updated.status}"

        # 审核通过
        await voucher_repo.update_status(
            v.voucher_no, "approved", action="approve"
        )
        updated = await voucher_repo.get_by_no(ledger.id, v.voucher_no)
        assert updated.status == "approved", f"审核通过失败: {updated.status}"

        # 过账
        await voucher_repo.update_status(
            v.voucher_no, "posted", action="post"
        )
        updated = await voucher_repo.get_by_no(ledger.id, v.voucher_no)
        assert updated.status == "posted", f"过账失败: {updated.status}"

        print(f"  [OK] {v.voucher_no}: draft → pending_review → approved → posted")

    results.append(("凭证审核流程", True))

    # ── Step 6: 查询凭证列表 ──
    print("\n── Step 6: 查询凭证 ──")
    all_vouchers = await voucher_repo.get_all(ledger.id)
    assert len(all_vouchers) == 3, f"凭证数量不对: {len(all_vouchers)}"

    posted_vouchers = await voucher_repo.get_all(ledger.id, status="posted")
    assert len(posted_vouchers) == 3

    jan_vouchers = await voucher_repo.get_all(ledger.id, year=2026, month=1)
    assert len(jan_vouchers) == 3

    print(f"  [OK] 全部凭证: {len(all_vouchers)}, 已过账: {len(posted_vouchers)}, 1月: {len(jan_vouchers)}")
    results.append(("查询凭证", True))

    # ── Step 7: 科目余额表 ──
    print("\n── Step 7: 科目余额表 ──")
    balances = await report_repo.get_account_balances(ledger.id, 2026, 1)
    assert len(balances) > 0, "余额表为空"

    # 验证关键科目余额
    cash_balance = next((b for b in balances if b["account_code"] == "1001"), None)
    bank_balance = next((b for b in balances if b["account_code"] == "1002"), None)

    assert cash_balance is not None, "库存现金余额不存在"
    assert cash_balance["opening_balance"] == 100000, f"现金期初不对: {cash_balance['opening_balance']}"

    if bank_balance:
        # 银行存款: 期初0 + 收到投资500000 - 付款30000 = 470000
        expected_bank = 500000 - 30000  # 没有期初余额
        print(f"  银行存款: 期初={bank_balance['opening_balance']}, "
              f"借方={bank_balance['period_debit']}, "
              f"贷方={bank_balance['period_credit']}, "
              f"期末={bank_balance['closing_balance']}")
        assert bank_balance["closing_balance"] == expected_bank, \
            f"银行存款期末余额不对: 期望{expected_bank}, 实际{bank_balance['closing_balance']}"

    print(f"  [OK] 余额表: {len(balances)} 个科目")
    for b in balances:
        if b["period_debit"] > 0 or b["period_credit"] > 0 or b["opening_balance"] > 0:
            print(f"    {b['account_code']} {b['account_name']}: "
                  f"期初={b['opening_balance']:.2f}, "
                  f"借={b['period_debit']:.2f}, "
                  f"贷={b['period_credit']:.2f}, "
                  f"期末={b['closing_balance']:.2f}")
    results.append(("科目余额表", True))

    # ── Step 8: 预算管理 ──
    print("\n── Step 8: 预算管理 ──")
    budget = await budget_repo.set_budget(
        ledger.id, "6401", "主营业务成本", 2026, 1, 50000
    )
    assert budget.budget_amount == 50000

    budgets = await budget_repo.get_by_ledger(ledger.id, year=2026)
    assert len(budgets) == 1

    # 检查是否超支（费用类科目，用借方比较）
    check = await budget_repo.check_exceeded(ledger.id, "6401", 2026, 1, 0)
    assert check["has_budget"] is True
    print(f"  [OK] 预算设置: {budget.account_code} = {budget.budget_amount}")
    print(f"  [OK] 超支检查: {check}")
    results.append(("预算管理", True))

    # ── Step 9: 税务配置 ──
    print("\n── Step 9: 税务配置 ──")
    config = await tax_repo.set_config(ledger.id, taxpayer_type="general", default_tax_rate=0.13)
    assert config.taxpayer_type == "general"
    assert config.default_tax_rate == 0.13

    rate = await tax_repo.add_rate(ledger.id, 0.06, "服务税率", "服务类税率")
    assert rate.name == "服务税率"
    assert rate.rate == 0.06

    rates = await tax_repo.get_rates(ledger.id)
    assert len(rates) == 1

    print(f"  [OK] 税务配置: {config.taxpayer_type}, 默认税率={config.default_tax_rate}")
    print(f"  [OK] 税率: {len(rates)} 条")
    results.append(("税务配置", True))

    # ── Step 10: 用户管理 ──
    print("\n── Step 10: 用户管理 ──")
    user = await auth_repo.create(
        username="admin", password_hash="test_hash_123", role="admin", ledger_id=ledger.id
    )
    assert user.id > 0
    assert user.username == "admin"

    fetched = await auth_repo.get_by_username("admin")
    assert fetched is not None
    assert fetched.username == "admin"

    users = await auth_repo.get_all(ledger_id=ledger.id)
    assert len(users) == 1

    print(f"  [OK] 用户创建: {user.username}, role={user.role}")
    print(f"  [OK] 用户查询: {len(users)} 个")
    results.append(("用户管理", True))

    # ── Step 11: 期末结账 ──
    print("\n── Step 11: 期末结账 ──")
    # 检查期初状态
    status = await period_repo.get_period_status(ledger.id, 2026, 1)
    assert status == "open", f"期初状态应为open: {status}"

    # 结账
    ce = await period_repo.close_period(ledger.id, 2026, 1, voucher_id=None)
    assert ce.status == "completed"

    # 检查结账后状态
    status = await period_repo.get_period_status(ledger.id, 2026, 1)
    assert status == "closed", f"结账后状态应为closed: {status}"
    print(f"  [OK] 2026年1月已结账")

    # 反结账
    await period_repo.reverse_close_period(ledger.id, 2026, 1)
    status = await period_repo.get_period_status(ledger.id, 2026, 1)
    assert status == "open", f"反结账后状态应为open: {status}"
    print(f"  [OK] 2026年1月已反结账")
    results.append(("期末结账", True))

    # ── Step 12: 凭证冲销 ──
    print("\n── Step 12: 凭证冲销 ──")
    await voucher_repo.update_status(v1.voucher_no, "reversed", action="reverse")
    reversed_v = await voucher_repo.get_by_no(ledger.id, v1.voucher_no)
    assert reversed_v.status == "reversed"
    print(f"  [OK] {v1.voucher_no} 已冲销")
    results.append(("凭证冲销", True))

    return results


# ═══════════════════════════════════════════════════════════════
# Test 2: 性能对比
# ═══════════════════════════════════════════════════════════════

async def test_performance():
    """性能对比：批量创建凭证，测量吞吐"""
    from app.repository.ledger_repository import LedgerRepository
    from app.repository.voucher_repository import VoucherRepository
    from app.repository.report_repository import ReportRepository

    ledger_repo = LedgerRepository()
    voucher_repo = VoucherRepository()
    report_repo = ReportRepository()

    results = []

    # 创建测试账套
    ledger = await ledger_repo.create(name="性能测试账套")

    # ── 批量创建 100 笔凭证 ──
    print("\n── 性能测试: 批量创建 100 笔凭证 ──")
    start = time.perf_counter()
    for i in range(100):
        await voucher_repo.create_with_entries(
            ledger_id=ledger.id,
            date=f"2026-01-{((i % 28) + 1):02d}",
            description=f"性能测试凭证 #{i+1}",
            entries=[
                {"account_code": "1001", "account_name": "库存现金",
                 "debit": 1000 + i, "credit": 0},
                {"account_code": "6001", "account_name": "主营业务收入",
                 "debit": 0, "credit": 1000 + i},
            ],
        )
    create_elapsed = time.perf_counter() - start
    print(f"  [OK] 100 笔凭证创建: {create_elapsed:.2f}s ({100/create_elapsed:.1f} 笔/s)")
    results.append(("批量创建100笔", f"{create_elapsed:.2f}s", f"{100/create_elapsed:.1f} 笔/s"))

    # ── 查询全部凭证 ──
    start = time.perf_counter()
    all_v = await voucher_repo.get_all(ledger.id, limit=200)
    query_elapsed = time.perf_counter() - start
    assert len(all_v) == 100
    print(f"  [OK] 查询 {len(all_v)} 笔凭证: {query_elapsed:.4f}s")
    results.append(("查询100笔", f"{query_elapsed:.4f}s"))

    # ── 按条件查询 ──
    start = time.perf_counter()
    filtered = await voucher_repo.get_all(ledger.id, year=2026, month=1)
    filter_elapsed = time.perf_counter() - start
    print(f"  [OK] 按年月查询: {len(filtered)} 笔, {filter_elapsed:.4f}s")
    results.append(("按条件查询", f"{filter_elapsed:.4f}s"))

    # ── 余额表计算 ──
    start = time.perf_counter()
    balances = await report_repo.get_account_balances(ledger.id, 2026, 1)
    report_elapsed = time.perf_counter() - start
    print(f"  [OK] 余额表: {len(balances)} 个科目, {report_elapsed:.4f}s")
    results.append(("余额表计算", f"{report_elapsed:.4f}s"))

    # ── 搜索 ──
    start = time.perf_counter()
    search_results = await voucher_repo.search(ledger.id, keyword="性能测试")
    search_elapsed = time.perf_counter() - start
    print(f"  [OK] 搜索 '性能测试': {len(search_results)} 条, {search_elapsed:.4f}s")
    results.append(("关键词搜索", f"{search_elapsed:.4f}s"))

    return results


# ═══════════════════════════════════════════════════════════════
# Test 3: 异常场景
# ═══════════════════════════════════════════════════════════════

async def test_edge_cases():
    """异常场景和边界情况测试"""
    from app.repository.ledger_repository import LedgerRepository
    from app.repository.account_repository import AccountRepository
    from app.repository.voucher_repository import VoucherRepository
    from app.repository.period_repository import PeriodRepository

    ledger_repo = LedgerRepository()
    account_repo = AccountRepository()
    voucher_repo = VoucherRepository()
    period_repo = PeriodRepository()

    results = []

    ledger = await ledger_repo.create(name="异常测试账套")

    # ── 1. 查询不存在的记录 ──
    print("\n── 异常测试 1: 查询不存在的记录 ──")
    result = await ledger_repo.get_by_id(99999)
    assert result is None, "不存在的记录应返回 None"
    print("  [OK] get_by_id(99999) → None")
    results.append(("查询不存在记录", True))

    # ── 2. 删除不存在的记录 ──
    print("\n── 异常测试 2: 删除不存在的记录 ──")
    deleted = await ledger_repo.delete(99999)
    assert deleted is False, "删除不存在记录应返回 False"
    print("  [OK] delete(99999) → False")
    results.append(("删除不存在记录", True))

    # ── 3. 更新不存在的记录 ──
    print("\n── 异常测试 3: 更新不存在的记录 ──")
    updated = await ledger_repo.update(99999, name="不存在")
    assert updated is None, "更新不存在记录应返回 None"
    print("  [OK] update(99999) → None")
    results.append(("更新不存在记录", True))

    # ── 4. 空凭证（0 条分录）──
    print("\n── 异常测试 4: 空分录凭证 ──")
    try:
        v = await voucher_repo.create_with_entries(
            ledger_id=ledger.id,
            date="2026-01-01",
            description="空分录",
            entries=[],
        )
        # 空分录应该能创建但 debit=credit=0
        assert v.total_debit == 0
        assert v.total_credit == 0
        print("  [OK] 空分录凭证: debit=0, credit=0")
        results.append(("空分录凭证", True))
    except Exception as e:
        print(f"  [FAIL] 空分录: {e}")
        results.append(("空分录凭证", False))

    # ── 5. 借贷不平衡的凭证 ──
    print("\n── 异常测试 5: 借贷不平衡凭证 ──")
    v_unbalanced = await voucher_repo.create_with_entries(
        ledger_id=ledger.id,
        date="2026-01-02",
        description="借贷不平衡",
        entries=[
            {"account_code": "1001", "account_name": "库存现金", "debit": 1000, "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": 500},
        ],
    )
    # 目前 repository 层不做借贷平衡校验，这是 service 层的职责
    # 这里只验证数据能正常写入
    assert v_unbalanced.total_debit == 1000
    assert v_unbalanced.total_credit == 500
    print(f"  [OK] 不平衡凭证已创建 (debit={v_unbalanced.total_debit}, credit={v_unbalanced.total_credit})")
    print("  [INFO] 借贷平衡校验应在 service 层实现")
    results.append(("借贷不平衡", True))

    # ── 6. 重复科目代码 ──
    print("\n── 异常测试 6: 重复科目代码 ──")
    await account_repo.create(code="9999", name="测试科目", category="资产")
    try:
        await account_repo.create(code="9999", name="重复科目", category="资产")
        print("  [WARN] 重复代码未报错（需要数据库唯一约束）")
        results.append(("重复科目代码", "未拦截"))
    except Exception as e:
        print(f"  [OK] 重复代码被拦截: {type(e).__name__}")
        results.append(("重复科目代码", True))

    # ── 7. 特殊字符输入 ──
    print("\n── 异常测试 7: 特殊字符 ──")
    v_special = await voucher_repo.create_with_entries(
        ledger_id=ledger.id,
        date="2026-01-03",
        description="特殊字符测试：中文'引号\"双引号<script>alert(1)</script>",
        entries=[
            {"account_code": "1001", "account_name": "库存现金", "debit": 100, "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": 100},
        ],
    )
    assert "<script>" in v_special.description  # 应原样存储，不做 XSS 过滤（那是前端的事）
    print(f"  [OK] 特殊字符正常存储")
    results.append(("特殊字符", True))

    # ── 8. 超大金额 ──
    print("\n── 异常测试 8: 超大金额 ──")
    v_large = await voucher_repo.create_with_entries(
        ledger_id=ledger.id,
        date="2026-01-04",
        description="超大金额测试",
        entries=[
            {"account_code": "1001", "account_name": "库存现金", "debit": 999999999.99, "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": 999999999.99},
        ],
    )
    assert v_large.total_debit == 999999999.99
    print(f"  [OK] 超大金额: {v_large.total_debit}")
    results.append(("超大金额", True))

    # ── 9. 跨月查询 ──
    print("\n── 异常测试 9: 跨月查询 ──")
    feb_vouchers = await voucher_repo.get_all(ledger.id, year=2026, month=2)
    assert len(feb_vouchers) == 0, "2月应无凭证"
    print(f"  [OK] 2月凭证: {len(feb_vouchers)} 笔")
    results.append(("跨月查询", True))

    # ── 10. 结账后再操作 ──
    print("\n── 异常测试 10: 重复结账 ──")
    await period_repo.close_period(ledger.id, 2026, 1)
    # 同一期间再次结账 — 目前允许多条记录
    await period_repo.close_period(ledger.id, 2026, 1)
    status = await period_repo.get_period_status(ledger.id, 2026, 1)
    assert status == "closed"
    print(f"  [OK] 重复结账后状态: {status}")
    results.append(("重复结账", True))

    return results


# ═══════════════════════════════════════════════════════════════
# Main entry
# ═══════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("  验收测试 — Week 1 & Week 2")
    print("=" * 60)

    close_db = await setup_db()

    all_passed = True

    # Test 1: 完整业务流程
    print("\n" + "=" * 60)
    print("  测试 1: 完整业务流程")
    print("=" * 60)
    try:
        results = await test_full_workflow()
        for name, passed in results:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}")
            if not passed:
                all_passed = False
    except Exception as e:
        print(f"  [FAIL] 业务流程测试异常: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    # Test 2: 性能对比
    print("\n" + "=" * 60)
    print("  测试 2: 性能对比")
    print("=" * 60)
    try:
        results = await test_performance()
        for r in results:
            print(f"  [OK] {r[0]}: {r[1]}" + (f" ({r[2]})" if len(r) > 2 else ""))
    except Exception as e:
        print(f"  [FAIL] 性能测试异常: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    # Test 3: 异常场景
    print("\n" + "=" * 60)
    print("  测试 3: 异常场景")
    print("=" * 60)
    try:
        results = await test_edge_cases()
        for name, passed in results:
            status = "PASS" if passed else "WARN" if passed == "未拦截" else "FAIL"
            print(f"  [{status}] {name}")
            if passed is False:
                all_passed = False
    except Exception as e:
        print(f"  [FAIL] 异常测试异常: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    # Cleanup
    await close_db()
    cleanup_db()

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("  全部测试通过!")
    else:
        print("  部分测试未通过，请检查上方输出")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

