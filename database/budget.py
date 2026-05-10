"""Database module: budget domain"""

from .connection import get_conn, transaction, DB_PATH

def get_budgets(ledger_id: int, year: int, month: int = None) -> list:
    """获取预算列表"""
    conn = get_conn()
    if month:
        rows = conn.execute(
            "SELECT * FROM budgets WHERE ledger_id = ? AND budget_year = ? AND budget_month = ? ORDER BY account_code",
            (ledger_id, year, month)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM budgets WHERE ledger_id = ? AND budget_year = ? ORDER BY account_code, budget_month",
            (ledger_id, year)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_budget(ledger_id: int, account_code: str, account_name: str, year: int, month: int, amount: float, description: str = ""):
    """设置/更新预算"""
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM budgets WHERE ledger_id = ? AND account_code = ? AND budget_year = ? AND budget_month = ?",
        (ledger_id, account_code, year, month)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE budgets SET budget_amount=?, account_name=?, description=?, updated_at=datetime('now','localtime') WHERE id=?",
            (amount, account_name, description, existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO budgets (ledger_id, account_code, account_name, budget_year, budget_month, budget_amount, description) VALUES (?,?,?,?,?,?,?)",
            (ledger_id, account_code, account_name, year, month, amount, description)
        )
    conn.commit()
    conn.close()
    clear_query_cache()

def get_budget_execution(ledger_id: int, year: int, month: int) -> list:
    """获取预算执行情况（预算 vs 实际）"""
    conn = get_conn()
    # 获取该月所有预算
    budgets = conn.execute(
        "SELECT * FROM budgets WHERE ledger_id = ? AND budget_year = ? AND budget_month = ?",
        (ledger_id, year, month)
    ).fetchall()

    results = []
    for b in budgets:
        # 计算实际发生额（借方合计）
        actual = conn.execute(
            "SELECT COALESCE(SUM(je.debit), 0) as total_debit "
            "FROM journal_entries je "
            "JOIN vouchers v ON je.voucher_id = v.id "
            "WHERE v.ledger_id = ? AND v.status = 'posted' "
            "AND je.account_code = ? "
            "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ?",
            (ledger_id, b["account_code"], str(year), f"{month:02d}")
        ).fetchone()["total_debit"]

        budget_amount = b["budget_amount"]
        variance = actual - budget_amount
        variance_pct = (variance / budget_amount * 100) if budget_amount > 0 else 0

        results.append({
            "id": b["id"],
            "account_code": b["account_code"],
            "account_name": b["account_name"],
            "budget_amount": budget_amount,
            "actual_amount": actual,
            "variance": variance,
            "variance_pct": variance_pct,
            "is_over_budget": actual > budget_amount if budget_amount > 0 else False,
        })

    conn.close()
    return results

def get_budget_summary(ledger_id: int, year: int, month: int) -> dict:
    """获取预算汇总"""
    execution = get_budget_execution(ledger_id, year, month)
    total_budget = sum(e["budget_amount"] for e in execution)
    total_actual = sum(e["actual_amount"] for e in execution)
    over_budget_count = sum(1 for e in execution if e["is_over_budget"])
    return {
        "total_budget": total_budget,
        "total_actual": total_actual,
        "total_variance": total_actual - total_budget,
        "over_budget_count": over_budget_count,
        "item_count": len(execution),
    }

def check_budget_exceeded(ledger_id: int, account_code: str, year: int, month: int, additional_amount: float = 0) -> dict:
    """检查是否超预算（凭证录入时调用）"""
    conn = get_conn()
    budget = conn.execute(
        "SELECT budget_amount FROM budgets WHERE ledger_id = ? AND account_code = ? AND budget_year = ? AND budget_month = ?",
        (ledger_id, account_code, year, month)
    ).fetchone()

    if not budget or budget["budget_amount"] <= 0:
        conn.close()
        return {"has_budget": False, "exceeded": False}

    actual = conn.execute(
        "SELECT COALESCE(SUM(je.debit), 0) as total_debit "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' "
        "AND je.account_code = ? "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ?",
        (ledger_id, account_code, str(year), f"{month:02d}")
    ).fetchone()["total_debit"]

    conn.close()

    projected = actual + additional_amount
    return {
        "has_budget": True,
        "budget_amount": budget["budget_amount"],
        "actual_amount": actual,
        "projected": projected,
        "exceeded": projected > budget["budget_amount"],
        "remaining": budget["budget_amount"] - projected,
    }
