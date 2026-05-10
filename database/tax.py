"""Database module: tax domain"""

from .connection import get_conn, transaction, DB_PATH

def get_tax_config(ledger_id: int) -> dict:
    """获取账套增值税配置"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM tax_config WHERE ledger_id = ?", (ledger_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def set_tax_config(ledger_id: int, taxpayer_type: str = "general", default_tax_rate: float = 0.13):
    """设置账套增值税配置"""
    conn = get_conn()
    existing = conn.execute("SELECT id FROM tax_config WHERE ledger_id = ?", (ledger_id,)).fetchone()
    if existing:
        conn.execute("UPDATE tax_config SET taxpayer_type=?, default_tax_rate=?, updated_at=datetime('now','localtime') WHERE ledger_id=?",
                     (taxpayer_type, default_tax_rate, ledger_id))
    else:
        conn.execute("INSERT INTO tax_config (ledger_id, taxpayer_type, default_tax_rate) VALUES (?,?,?)",
                     (ledger_id, taxpayer_type, default_tax_rate))
    conn.commit()
    conn.close()
    clear_query_cache()

def get_tax_rates(ledger_id: int) -> list:
    """获取账套税率列表"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tax_rates WHERE ledger_id = ? AND is_active = 1 ORDER BY rate ASC", (ledger_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_tax_rate(ledger_id: int, rate: float, name: str, description: str = "", is_default: int = 0):
    """添加税率"""
    conn = get_conn()
    if is_default:
        conn.execute("UPDATE tax_rates SET is_default = 0 WHERE ledger_id = ?", (ledger_id,))
    conn.execute("INSERT INTO tax_rates (ledger_id, rate, name, description, is_default) VALUES (?,?,?,?,?)",
                 (ledger_id, rate, name, description, is_default))
    conn.commit()
    conn.close()
    clear_query_cache()

def get_tax_summary(ledger_id: int, year: int, month: int) -> dict:
    """获取增值税汇总数据（进项/销项税额统计）"""
    conn = get_conn()
    # 进项税额（借方分录中的税额）
    input_tax = conn.execute(
        "SELECT COALESCE(SUM(je.tax_amount), 0) as total_input_tax "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' AND je.tax_type = 'input' "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ?",
        (ledger_id, str(year), f"{month:02d}")
    ).fetchone()["total_input_tax"]

    # 销项税额（贷方分录中的税额）
    output_tax = conn.execute(
        "SELECT COALESCE(SUM(je.tax_amount), 0) as total_output_tax "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' AND je.tax_type = 'output' "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ?",
        (ledger_id, str(year), f"{month:02d}")
    ).fetchone()["total_output_tax"]

    config = get_tax_config(ledger_id)
    conn.close()

    return {
        "input_tax": input_tax,
        "output_tax": output_tax,
        "tax_payable": output_tax - input_tax,
        "taxpayer_type": config.get("taxpayer_type", "general") if config else "general",
        "default_rate": config.get("default_tax_rate", 0.13) if config else 0.13,
    }

def get_tax_detail(ledger_id: int, year: int, month: int, tax_type: str = "input") -> list:
    """获取进项/销项税额明细"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT je.account_code, je.account_name, je.tax_rate, je.tax_amount, "
        "v.voucher_no, v.date, v.description "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' AND je.tax_type = ? "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ? "
        "ORDER BY v.date ASC",
        (ledger_id, tax_type, str(year), f"{month:02d}")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
