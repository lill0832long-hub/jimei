"""Database module: dashboard domain"""

from .connection import get_conn, transaction, DB_PATH

def get_dashboard_kpi(ledger_id, year, month):
    """获取仪表盘 KPI 数据"""
    conn = get_conn()

    ar = conn.execute("""
        SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) as bal
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND je.account_code LIKE '1122%'
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) <= ?
    """, (ledger_id, str(year), month)).fetchone()
    ar_bal = ar["bal"] if ar else 0

    ap = conn.execute("""
        SELECT COALESCE(SUM(je.credit) - SUM(je.debit), 0) as bal
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND je.account_code LIKE '2202%'
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) <= ?
    """, (ledger_id, str(year), month)).fetchone()
    ap_bal = ap["bal"] if ap else 0

    bank = conn.execute("""
        SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) as bal
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND je.account_code LIKE '1002%'
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) <= ?
    """, (ledger_id, str(year), month)).fetchone()
    bank_bal = bank["bal"] if bank else 0

    rev = conn.execute("""
        SELECT COALESCE(SUM(je.credit) - SUM(je.debit), 0) as total
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN accounts a ON je.account_code = a.code
        WHERE je.ledger_id = ? AND a.category = '收入' AND a.is_active = 1
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) = ?
    """, (ledger_id, str(year), month)).fetchone()
    month_revenue = rev["total"] if rev else 0

    exp = conn.execute("""
        SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) as total
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN accounts a ON je.account_code = a.code
        WHERE je.ledger_id = ? AND a.category = '费用' AND a.is_active = 1
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) = ?
    """, (ledger_id, str(year), month)).fetchone()
    month_expense = exp["total"] if exp else 0

    cash_flow = conn.execute("""
        SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) as total
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND (je.account_code LIKE '1001%' OR je.account_code LIKE '1002%')
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) = ?
    """, (ledger_id, str(year), month)).fetchone()
    net_cash_flow = cash_flow["total"] if cash_flow else 0

    conn.close()
    return {
        "ar_balance": ar_bal,
        "ap_balance": ap_bal,
        "bank_balance": bank_bal,
        "month_revenue": month_revenue,
        "month_expense": month_expense,
        "month_profit": month_revenue - month_expense,
        "net_cash_flow": net_cash_flow,
    }

def get_monthly_trend(ledger_id, months=12):
    """获取最近 N 个月的收支趋势"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT strftime('%Y', v.date) as year,
               CAST(strftime('%m', v.date) AS INTEGER) as month,
               SUM(CASE WHEN a.category = '收入' THEN je.credit - je.debit ELSE 0 END) as revenue,
               SUM(CASE WHEN a.category = '费用' THEN je.debit - je.credit ELSE 0 END) as expense
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN accounts a ON je.account_code = a.code AND a.is_active = 1
        WHERE je.ledger_id = ? AND v.status = 'posted'
          AND a.category IN ('收入', '费用')
        GROUP BY year, month
        ORDER BY year DESC, month DESC
        LIMIT ?
    """, (ledger_id, months)).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    result.reverse()
    return result

def get_expense_breakdown(ledger_id, year, month):
    """获取费用占比数据"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT a.sub_category as category,
               SUM(je.debit - je.credit) as amount
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN accounts a ON je.account_code = a.code AND a.is_active = 1
        WHERE je.ledger_id = ? AND a.category = '费用'
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) = ?
        GROUP BY a.sub_category
        HAVING amount > 0
        ORDER BY amount DESC
    """, (ledger_id, str(year), month)).fetchall()
    conn.close()
    return [{"category": r["category"] or "其他", "amount": r["amount"]} for r in rows]

def get_period_compare_income(ledger_id: int, periods: list) -> dict:
    """多期间利润对比
    periods: [(year, month), ...]
    返回: {periods: [...], items: [{name, code, values: [amount, ...], changes: [%...]}]}
    """
    results = []
    for year, month in periods:
        inc = get_income_statement(ledger_id, year, month)
        # 从 rows 中提取收入/费用项（level > 0 的明细项）
        rev_dict = {}
        exp_dict = {}
        for r in inc["rows"]:
            if r["type"] in ("revenue_item",):
                rev_dict[r["code"]] = r["month"]
            elif r["type"] in ("expense_item",):
                exp_dict[r["code"]] = r["month"]
        results.append({
            "year": year, "month": month,
            "label": f"{year}-{month:02d}",
            "revenues": rev_dict,
            "expenses": exp_dict,
            "total_revenue": inc["total_revenue"],
            "total_expense": inc.get("total_expense", inc.get("total_revenue", 0) - inc.get("net_profit", 0)),
            "net_profit": inc["net_profit"],
        })

    all_rev_codes = set()
    all_exp_codes = set()
    for r in results:
        all_rev_codes.update(r["revenues"].keys())
        all_exp_codes.update(r["expenses"].keys())

    conn = get_conn()
    code_names = {}
    for code in all_rev_codes | all_exp_codes:
        row = conn.execute("SELECT name FROM accounts WHERE code=?", (code,)).fetchone()
        code_names[code] = row["name"] if row else code
    conn.close()

    items = []
    for code in sorted(all_rev_codes):
        values = [r["revenues"].get(code, 0) for r in results]
        changes = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                changes.append((values[i] - values[i-1]) / values[i-1] * 100)
            else:
                changes.append(None)
        items.append({"code": code, "name": code_names[code], "type": "revenue",
                       "values": values, "changes": changes})
    for code in sorted(all_exp_codes):
        values = [r["expenses"].get(code, 0) for r in results]
        changes = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                changes.append((values[i] - values[i-1]) / values[i-1] * 100)
            else:
                changes.append(None)
        items.append({"code": code, "name": code_names[code], "type": "expense",
                       "values": values, "changes": changes})

    return {
        "periods": [r["label"] for r in results],
        "items": items,
        "summary": {
            "total_revenue": [r["total_revenue"] for r in results],
            "total_expense": [r["total_expense"] for r in results],
            "net_profit": [r["net_profit"] for r in results],
        }
    }

def get_period_compare_balance(ledger_id: int, periods: list) -> dict:
    """多期间资产负债对比 — 适配新资产负债表格式"""
    results = []
    for year, month in periods:
        bs = get_balance_sheet(ledger_id, year, month)
        asset_items = {r["code"]: r["end"] for r in bs["assets"] if r["code"] and r["code"] not in ("1003", "1601N")}
        liab_items = {r["code"]: r["end"] for r in bs["liabilities"] if r["code"]}
        eq_items = {r["code"]: r["end"] for r in bs["equity"] if r["code"]}
        results.append({
            "year": year, "month": month,
            "label": f"{year}-{month:02d}",
            "assets": bs["total_assets"],
            "liabilities": bs["total_liab"],
            "equity": bs["total_equity"],
            "asset_items": asset_items,
            "liab_items": liab_items,
            "equity_items": eq_items,
        })

    all_codes = set()
    for r in results:
        all_codes.update(r["asset_items"].keys())
        all_codes.update(r["liab_items"].keys())
        all_codes.update(r["equity_items"].keys())

    conn = get_conn()
    code_names = {}
    for code in all_codes:
        row = conn.execute("SELECT name, category FROM accounts WHERE code=?", (code,)).fetchone()
        if row:
            code_names[code] = {"name": row["name"], "category": row["category"]}
        else:
            code_names[code] = {"name": code, "category": "unknown"}
    conn.close()

    items = []
    for code in sorted(all_codes):
        values = []
        for r in results:
            v = r["asset_items"].get(code, 0) + r["liab_items"].get(code, 0) + r["equity_items"].get(code, 0)
            values.append(v)
        changes = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                changes.append((values[i] - values[i-1]) / values[i-1] * 100)
            else:
                changes.append(None)
        items.append({"code": code, "name": code_names[code]["name"],
                       "category": code_names[code]["category"],
                       "values": values, "changes": changes})

    return {
        "periods": [r["label"] for r in results],
        "items": items,
        "summary": {
            "assets": [r["assets"] for r in results],
            "liabilities": [r["liabilities"] for r in results],
            "equity": [r["equity"] for r in results],
        }
    }
