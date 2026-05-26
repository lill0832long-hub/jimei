"""Database module: multi_currency domain"""

import logging
from datetime import datetime
from .connection import get_conn, release_conn, transaction, DB_PATH, clear_query_cache

logger = logging.getLogger(__name__)

def _init_default_currencies(c):
    """Phase 10: 初始化默认币种数据"""
    c.execute("SELECT COUNT(*) FROM currencies")
    if c.fetchone()[0] > 0:
        return
    default_currencies = [
        ("CNY", "人民币", "¥", 1),
        ("USD", "美元", "$", 0),
        ("EUR", "欧元", "€", 0),
        ("JPY", "日元", "¥", 0),
        ("GBP", "英镑", "£", 0),
        ("HKD", "港币", "HK$", 0),
        ("AUD", "澳元", "A$", 0),
        ("CAD", "加元", "C$", 0),
        ("SGD", "新加坡元", "S$", 0),
        ("KRW", "韩元", "₩", 0),
        ("CHF", "瑞士法郎", "Fr", 0),
        ("TWD", "新台币", "NT$", 0),
    ]
    for code, name, symbol, is_base in default_currencies:
        c.execute("INSERT OR IGNORE INTO currencies (code, name, symbol, is_base) VALUES (?, ?, ?, ?)",
                  (code, name, symbol, is_base))

def _init_default_exchange_rates(c):
    """Phase 10: 初始化默认汇率数据（以CNY为基准）"""
    c.execute("SELECT COUNT(*) FROM exchange_rates")
    if c.fetchone()[0] > 0:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    default_rates = [
        ("USD", "CNY", 7.2456),
        ("EUR", "CNY", 7.8456),
        ("JPY", "CNY", 0.0485),
        ("GBP", "CNY", 9.1823),
        ("HKD", "CNY", 0.9275),
        ("AUD", "CNY", 4.7234),
        ("CAD", "CNY", 5.3123),
        ("SGD", "CNY", 5.3567),
        ("KRW", "CNY", 0.0054),
        ("CHF", "CNY", 8.1234),
        ("TWD", "CNY", 0.2234),
    ]
    for from_c, to_c, rate in default_rates:
        c.execute("INSERT OR IGNORE INTO exchange_rates (from_currency, to_currency, rate, date, source) VALUES (?, ?, ?, ?, 'system')",
                  (from_c, to_c, rate, today))

def set_exchange_rate(from_currency: str, to_currency: str, rate: float, date: str = None):
    """设置汇率"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO exchange_rates (from_currency, to_currency, rate, date)
            VALUES (?,?,?,?)
        """, (from_currency.upper(), to_currency.upper(), rate, date))
        conn.commit()
    finally:
        release_conn(conn)
    clear_query_cache()

def get_exchange_rate(from_currency: str, to_currency: str, date: str = None) -> float:
    """获取汇率，如果没有则返回1"""
    if from_currency.upper() == to_currency.upper():
        return 1.0
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        row = conn.execute("""
            SELECT rate FROM exchange_rates
            WHERE from_currency = ? AND to_currency = ?
              AND date <= ?
            ORDER BY date DESC LIMIT 1
        """, (from_currency.upper(), to_currency.upper(), date)).fetchone()
    finally:
        release_conn(conn)
    if not row:
        logger.warning("No exchange rate found for %s->%s on %s, using 1.0", from_currency, to_currency, date)
        return 1.0
    return row["rate"]

def convert_currency(amount: float, from_currency: str, to_currency: str, date: str = None) -> float:
    """货币转换"""
    rate = get_exchange_rate(from_currency, to_currency, date)
    return round(amount * rate, 2)
