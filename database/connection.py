"""
AI 财务系统 — 数据库模块 v2
拆分后: database/connection.py — 核心连接与初始化
"""

import sqlite3
import os
import logging
import threading
import functools
from contextlib import contextmanager
from datetime import datetime, date
from enum import Enum

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "finance_v2.db")

# ── 连接池配置 ──
_DB_TIMEOUT = 30  # 连接超时（秒）
_pool_lock = threading.Lock()
_connection_pool = []
_pool_max_size = 5


def _create_connection():
    """创建一个新的数据库连接"""
    conn = sqlite3.connect(
        DB_PATH,
        timeout=_DB_TIMEOUT,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def get_conn():
    """从连接池获取数据库连接，池空时创建新连接"""
    with _pool_lock:
        if _connection_pool:
            conn = _connection_pool.pop()
            # 健康检查：验证连接是否可用
            try:
                conn.execute("SELECT 1")
                return conn
            except Exception:
                logger.warning("Pooled connection unhealthy, creating new one")
                try:
                    conn.close()
                except Exception:
                    pass
    # 池为空或连接不可用，创建新连接
    return _create_connection()


def release_conn(conn):
    """将连接归还到连接池，池满时关闭"""
    if conn is None:
        return
    with _pool_lock:
        if len(_connection_pool) < _pool_max_size:
            _connection_pool.append(conn)
        else:
            try:
                conn.close()
            except Exception:
                pass


def check_db_health():
    """数据库健康检查 — 返回 True 表示正常"""
    try:
        conn = get_conn()
        try:
            conn.execute("SELECT 1")
            return True
        finally:
            release_conn(conn)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


@contextmanager
def transaction(conn):
    """事务管理上下文管理器 — 自动 commit/rollback"""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def clear_query_cache():
    """清除所有查询缓存 — 在写操作后调用（当前无缓存函数，留作扩展用）"""
    pass

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # 账套表
    c.execute("""
        CREATE TABLE IF NOT EXISTS ledgers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT DEFAULT '默认公司',
            currency TEXT DEFAULT 'CNY',
            fiscal_year_start DATE,
            fiscal_year_end DATE,
            status TEXT DEFAULT 'active',
            settings TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 科目表
    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            sub_category TEXT,
            parent_code TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 凭证表
    c.execute("""
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            voucher_no TEXT UNIQUE NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            total_debit REAL DEFAULT 0,
            total_credit REAL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            attachment TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 凭证明细
    c.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            voucher_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            account_name TEXT NOT NULL,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            summary TEXT,
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE CASCADE,
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 期初余额
    c.execute("""
        CREATE TABLE IF NOT EXISTS opening_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            balance REAL DEFAULT 0,
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(ledger_id, account_code, year, month)
        )
    """)

    # 文档表
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT,
            file_size INTEGER,
            file_path TEXT,
            processing_status TEXT DEFAULT 'pending',
            ocr_text TEXT,
            extracted_data TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 审计日志
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            voucher_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 用户表
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            ledger_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE SET NULL
        )
    """)

    # 汇率表（Phase 10 升级：添加 source 字段）
    c.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            date TEXT NOT NULL,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(from_currency, to_currency, date)
        )
    """)

    # 汇率表添加 source 字段（兼容旧表）
    try:
        c.execute("ALTER TABLE exchange_rates ADD COLUMN source TEXT DEFAULT 'manual'")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE exchange_rates ADD COLUMN created_at TEXT DEFAULT (datetime('now','localtime'))")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE exchange_rates ADD COLUMN updated_at TEXT DEFAULT (datetime('now','localtime'))")
    except Exception:
        pass

    # 币种表（Phase 10 新增）
    c.execute("""
        CREATE TABLE IF NOT EXISTS currencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            symbol TEXT DEFAULT '',
            is_base INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 凭证表添加币种字段（兼容旧表）
    try:
        c.execute("ALTER TABLE vouchers ADD COLUMN currency TEXT DEFAULT 'CNY'")
    except Exception:
        pass

    # 凭证表添加法定字段（会计法规要求）
    try:
        c.execute("ALTER TABLE vouchers ADD COLUMN attachment_count INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE vouchers ADD COLUMN accountant TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE vouchers ADD COLUMN cashier TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE vouchers ADD COLUMN reviewer TEXT DEFAULT ''")
    except Exception:
        pass

    # 凭证明细添加外币字段（兼容旧表）
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN foreign_currency TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN foreign_amount REAL DEFAULT 0")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN exchange_rate REAL DEFAULT 1")
    except Exception:
        pass

    # AI 复合业务规则表 (Phase 7)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_rules_complex (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pattern TEXT NOT NULL,
            description TEXT,
            entries_json TEXT NOT NULL,
            priority INTEGER DEFAULT 50,
            is_active INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 索引
    c.execute("CREATE INDEX IF NOT EXISTS idx_er_from_to ON exchange_rates(from_currency, to_currency)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_rules_complex_pattern ON ai_rules_complex(pattern)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_rules_complex_priority ON ai_rules_complex(priority)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_currency_code ON currencies(code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_currency_active ON currencies(is_active)")

    # 初始化默认币种数据
    from .multi_currency import _init_default_currencies, _init_default_exchange_rates
    _init_default_currencies(c)

    # 初始化默认汇率数据
    _init_default_exchange_rates(c)

    # 创建默认管理员账户
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                  ("admin", "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9", "admin"))

    # 索引
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_ledger ON vouchers(ledger_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_date ON vouchers(date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_status ON vouchers(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_ledger ON journal_entries(ledger_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_voucher ON journal_entries(voucher_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_account ON journal_entries(account_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ob_ledger ON opening_balances(ledger_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_ledger ON audit_logs(ledger_id)")

    # 复合索引（Week 1 优化）
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_ledger_account ON journal_entries(ledger_id, account_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_ledger_voucher ON journal_entries(ledger_id, voucher_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_ledger_date ON vouchers(ledger_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_ledger_status ON vouchers(ledger_id, status)")

    # 初始化标准科目
    from .init_data import _init_chart_of_accounts, _init_missing_accounts
    _init_chart_of_accounts(c)

    # 补全缺失科目（Phase 1 迁移：从52个补到85+个）
    _init_missing_accounts(c)

    # 初始化复合业务规则 (Phase 7)
    from .ai import _init_complex_rules
    _init_complex_rules(c)

    # 创建默认账套
    c.execute("SELECT COUNT(*) FROM ledgers")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO ledgers (name, company, currency, fiscal_year_start, fiscal_year_end) VALUES (?,?,?,?,?)",
            ("默认账套", "我的公司", "CNY", f"{datetime.now().year}-01-01", f"{datetime.now().year}-12-31")
        )
        default_lid = c.lastrowid

    # ── P2-1: 审核流程数据库迁移 ──

    # audit_logs 添加 user_id 字段（记录谁操作的）
    try:
        c.execute("ALTER TABLE audit_logs ADD COLUMN user_id INTEGER")
    except Exception:
        pass

    # audit_logs 补齐会计组方案缺失字段 (2026-04-29)
    for _col in ["operator_name TEXT", "module TEXT", "target_table TEXT",
                 "target_id INTEGER", "old_value TEXT", "new_value TEXT",
                 "ip_address TEXT", "remark TEXT"]:
        try:
            c.execute(f"ALTER TABLE audit_logs ADD COLUMN {_col}")
        except Exception:
            pass

    # 凭证审核工作流表
    c.execute("""
        CREATE TABLE IF NOT EXISTS voucher_workflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id INTEGER NOT NULL,
            ledger_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            user_id INTEGER,
            comment TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE CASCADE,
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # ── P2-3: 发票管理数据库迁移 ──

    # 发票信息表
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            invoice_type TEXT NOT NULL DEFAULT 'input',
            invoice_code TEXT,
            invoice_no TEXT NOT NULL,
            invoice_date TEXT,
            seller_name TEXT,
            seller_tax_no TEXT,
            buyer_name TEXT,
            buyer_tax_no TEXT,
            total_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            total_with_tax REAL DEFAULT 0,
            status TEXT DEFAULT 'unverified',
            ocr_data TEXT,
            file_path TEXT,
            remark TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 发票-凭证关联表
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoice_voucher (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            voucher_id INTEGER NOT NULL,
            ledger_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE CASCADE,
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(invoice_id, voucher_id)
        )
    """)

    # ── P2-7: 定时自动凭证数据库迁移 ──

    # 凭证模板表
    c.execute("""
        CREATE TABLE IF NOT EXISTS voucher_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            voucher_type TEXT DEFAULT '记',
            entries TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 定时凭证任务表
    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            template_id INTEGER,
            name TEXT NOT NULL,
            cron_expression TEXT NOT NULL,
            next_run_at TEXT,
            last_run_at TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            FOREIGN KEY (template_id) REFERENCES voucher_templates(id) ON DELETE SET NULL
        )
    """)

    # ── P2-4: 预算管理数据库迁移 ──

    # 预算表
    c.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            account_name TEXT NOT NULL,
            budget_year INTEGER NOT NULL,
            budget_month INTEGER,
            budget_amount REAL NOT NULL DEFAULT 0,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 预算执行记录表
    c.execute("""
        CREATE TABLE IF NOT EXISTS budget_execution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            budget_id INTEGER,
            account_code TEXT NOT NULL,
            budget_year INTEGER NOT NULL,
            budget_month INTEGER NOT NULL,
            actual_amount REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE SET NULL
        )
    """)

    # ── P2-5: 现金流量表数据库迁移 ──

    # journal_entries 添加现金流分类字段
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN cash_flow_type TEXT DEFAULT ''")
    except Exception:
        pass

    # 现金流分类表
    c.execute("""
        CREATE TABLE IF NOT EXISTS cash_flow_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            parent_code TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(ledger_id, code)
        )
    """)

    # 初始化默认现金流分类（需在 cash_flow_categories 表创建后执行）
    c.execute("SELECT COUNT(*) FROM cash_flow_categories")
    if c.fetchone()[0] == 0:
        from .cash_flow import _init_default_cash_flow_categories
        c.execute("SELECT id FROM ledgers ORDER BY ID LIMIT 1")
        row = c.fetchone()
        if row:
            _init_default_cash_flow_categories(c, row[0])

    # ── P2-2: 增值税管理数据库迁移 ──

    # journal_entries 添加税务字段
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN tax_type TEXT DEFAULT ''")  # input/output/none
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN tax_rate REAL DEFAULT 0")   # 税率 0.13/0.09/0.06等
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN tax_amount REAL DEFAULT 0")  # 税额
    except Exception:
        pass

    # 增值税配置表
    c.execute("""
        CREATE TABLE IF NOT EXISTS tax_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            taxpayer_type TEXT DEFAULT 'general',
            default_tax_rate REAL DEFAULT 0.13,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(ledger_id)
        )
    """)

    # 税率表（预设常用税率）
    c.execute("""
        CREATE TABLE IF NOT EXISTS tax_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            rate REAL NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    release_conn(conn)
    clear_query_cache()

def init_v3_tables():
    """初始化 v3 新增的数据表"""
    conn = get_conn()
    
    # 固定资产类别
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fa_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            default_life_months INTEGER,
            default_residual_rate REAL DEFAULT 0.05,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 固定资产卡片
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fixed_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            asset_code TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            category_id INTEGER,
            purchase_date TEXT,
            original_value INTEGER NOT NULL DEFAULT 0,
            residual_rate REAL DEFAULT 0.05,
            residual_value INTEGER DEFAULT 0,
            useful_life_months INTEGER NOT NULL DEFAULT 120,
            depreciation_method TEXT DEFAULT 'straight_line',
            accumulated_depreciation INTEGER DEFAULT 0,
            net_value INTEGER DEFAULT 0,
            department TEXT,
            employee TEXT,
            location TEXT,
            status TEXT DEFAULT 'in_use',
            source_type TEXT DEFAULT 'purchase',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 资产变动记录
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fa_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            change_date TEXT,
            old_value INTEGER,
            new_value INTEGER,
            reason TEXT,
            voucher_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 银行账户
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            account_no TEXT NOT NULL,
            bank_name TEXT,
            account_name TEXT,
            currency_code TEXT DEFAULT 'CNY',
            opening_balance INTEGER DEFAULT 0,
            current_balance INTEGER DEFAULT 0,
            subject_code TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 银行对账单
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            statement_date TEXT,
            transaction_date TEXT,
            summary TEXT,
            debit INTEGER DEFAULT 0,
            credit INTEGER DEFAULT 0,
            reference_no TEXT,
            is_matched INTEGER DEFAULT 0,
            matched_journal_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 辅助核算类别
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auxiliary_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            aux_type TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 凭证分录辅助核算关联
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voucher_entry_auxiliaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            aux_type TEXT NOT NULL,
            aux_id INTEGER NOT NULL,
            aux_name TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 期末结转记录
    conn.execute("""
        CREATE TABLE IF NOT EXISTS closing_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            period TEXT NOT NULL,
            close_type TEXT NOT NULL,
            voucher_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 汇率表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates_v3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            effective_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 现金盘点
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cash_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            check_date TEXT NOT NULL,
            book_balance INTEGER DEFAULT 0,
            actual_balance INTEGER DEFAULT 0,
            difference INTEGER DEFAULT 0,
            handler TEXT,
            remark TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 支票管理
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            check_no TEXT NOT NULL,
            issue_date TEXT,
            payee TEXT,
            amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'issued',
            voucher_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 凭证模板表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voucher_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'general',
            entries TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(ledger_id, name)
        )
    """)

    # 兼容旧表：添加新列
    for _col, _typ, _def in [
        ("is_system", "INTEGER", "0"),
        ("category", "TEXT", "'general'"),
        ("is_active", "INTEGER", "1"),
        ("updated_at", "TEXT", "datetime('now','localtime')"),
    ]:
        try:
            conn.execute(f"ALTER TABLE voucher_templates ADD COLUMN {_col} {_typ} DEFAULT {_def}")
        except Exception:
            pass

    conn.commit()
    release_conn(conn)
    clear_query_cache()

def init_system_templates(ledger_id):
    """初始化系统内置凭证模板"""
    import json
    templates = [
        {
            "name": "收款-客户回款",
            "description": "收到客户货款",
            "entries": [
                {"account_code": "1002", "account_name": "银行存款", "direction": "debit", "summary": "收到货款"},
                {"account_code": "1122", "account_name": "应收账款", "direction": "credit", "summary": "收到货款"}
            ]
        },
        {
            "name": "付款-供应商结算",
            "description": "支付供应商货款",
            "entries": [
                {"account_code": "2202", "account_name": "应付账款", "direction": "debit", "summary": "支付货款"},
                {"account_code": "1002", "account_name": "银行存款", "direction": "credit", "summary": "支付货款"}
            ]
        },
        {
            "name": "费用报销-差旅",
            "description": "员工差旅费报销",
            "entries": [
                {"account_code": "6602", "account_name": "管理费用-差旅费", "direction": "debit", "summary": "差旅费报销"},
                {"account_code": "1001", "account_name": "库存现金", "direction": "credit", "summary": "差旅费报销"}
            ]
        },
        {
            "name": "工资发放",
            "description": "发放员工工资",
            "entries": [
                {"account_code": "2211", "account_name": "应付职工薪酬", "direction": "debit", "summary": "发放工资"},
                {"account_code": "1002", "account_name": "银行存款", "direction": "credit", "summary": "发放工资"}
            ]
        },
        {
            "name": "采购入库",
            "description": "采购商品入库",
            "entries": [
                {"account_code": "1405", "account_name": "库存商品", "direction": "debit", "summary": "采购入库"},
                {"account_code": "2202", "account_name": "应付账款", "direction": "credit", "summary": "采购入库"}
            ]
        },
        {
            "name": "销售确认收入",
            "description": "确认销售收入",
            "entries": [
                {"account_code": "1122", "account_name": "应收账款", "direction": "debit", "summary": "确认收入"},
                {"account_code": "6001", "account_name": "主营业务收入", "direction": "credit", "summary": "确认收入"}
            ]
        },
        {
            "name": "折旧计提",
            "description": "月末计提折旧",
            "entries": [
                {"account_code": "6602", "account_name": "管理费用-折旧费", "direction": "debit", "summary": "计提折旧"},
                {"account_code": "1602", "account_name": "累计折旧", "direction": "credit", "summary": "计提折旧"}
            ]
        },
        {
            "name": "月末结转损益",
            "description": "期末损益结转",
            "entries": [
                {"account_code": "6001", "account_name": "主营业务收入", "direction": "debit", "summary": "结转收入"},
                {"account_code": "3131", "account_name": "本年利润", "direction": "credit", "summary": "结转收入"},
                {"account_code": "3131", "account_name": "本年利润", "direction": "debit", "summary": "结转费用"},
                {"account_code": "6401", "account_name": "主营业务成本", "direction": "credit", "summary": "结转费用"}
            ]
        }
    ]
    conn = get_conn()
    for t in templates:
        conn.execute(
            "INSERT INTO voucher_templates (ledger_id, name, description, entries, is_system) VALUES (?,?,?,?,1)",
            (ledger_id, t["name"], t["description"], json.dumps(t["entries"], ensure_ascii=False))
        )
    conn.commit()
    release_conn(conn)
    clear_query_cache()
