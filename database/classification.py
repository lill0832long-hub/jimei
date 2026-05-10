"""Database module: classification domain"""

from .connection import get_conn, transaction, DB_PATH

def classify_transaction(ledger_id, summary, amount, direction, counterparty=""):
    """智能分类单笔交易"""
    text = f"{summary} {counterparty}"

    best_match = None
    best_score = 0
    for rule in CLASSIFICATION_RULES:
        score = 0
        for kw in rule["keywords"]:
            if kw in text:
                score += len(kw)
        if score > best_score:
            best_score = score
            best_match = rule

    if best_match and best_score > 0:
        confidence = min(0.5 + best_score * 0.1, 0.95)
        account_code = best_match["account_code"]
        account_name = best_match["account_name"]
        category = best_match["category"]
    else:
        hist_result = _match_history(ledger_id, summary, amount)
        if hist_result:
            account_code = hist_result["account_code"]
            account_name = hist_result["account_name"]
            category = "历史匹配"
            confidence = 0.85
        else:
            if direction == "debit":
                account_code = "6602"
                account_name = "管理费用-其他"
            else:
                account_code = "6001"
                account_name = "主营业务收入"
            category = "默认"
            confidence = 0.30

    is_anomaly, anomaly_reason = _detect_anomaly(ledger_id, amount)

    return {
        "account_code": account_code, "account_name": account_name,
        "confidence": confidence, "category": category,
        "is_anomaly": is_anomaly, "anomaly_reason": anomaly_reason,
    }

def _match_history(ledger_id, summary, amount):
    """根据摘要关键词匹配历史凭证科目"""
    conn = get_conn()
    keywords = summary[:10] if len(summary) >= 3 else summary
    rows = conn.execute("""
        SELECT je.account_code, je.account_name, COUNT(*) as freq
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND v.status = 'posted'
          AND je.summary LIKE ?
        GROUP BY je.account_code
        ORDER BY freq DESC LIMIT 1
    """, (ledger_id, f"%{keywords}%")).fetchall()
    conn.close()
    if rows:
        return {"account_code": rows[0]["account_code"], "account_name": rows[0]["account_name"]}
    return None

def _detect_anomaly(ledger_id, amount):
    """异常交易检测"""
    conn = get_conn()
    stats = conn.execute("""
        SELECT COALESCE(AVG(ABS(debit) + ABS(credit)), 0) as avg_amt,
               COUNT(*) as cnt
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND v.status = 'posted'
    """, (ledger_id,)).fetchone()
    avg = stats["avg_amt"] if stats else 0
    cnt = stats["cnt"] if stats else 0
    conn.close()
    if cnt >= 10 and abs(amount) > avg * 3 and avg > 0:
        return True, f"金额 ¥{abs(amount):,.2f} 超过平均值 ¥{avg:,.2f} 的3倍"
    return False, ""

def batch_classify(ledger_id, transactions):
    """批量分类银行流水"""
    results = []
    for txn in transactions:
        classification = classify_transaction(
            ledger_id,
            txn.get("summary", ""),
            txn.get("amount", 0),
            txn.get("direction", "debit"),
            txn.get("counterparty", "")
        )
        results.append({**txn, **classification})
    return results

def get_classification_rules(ledger_id):
    """获取用户历史分类规则"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT je.account_code, je.account_name, je.summary, COUNT(*) as freq
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND v.status = 'posted'
        GROUP BY je.account_code, je.summary
        HAVING freq >= 2
        ORDER BY freq DESC LIMIT 50
    """, (ledger_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def parse_bank_csv(file_content, encoding="utf-8"):
    """解析银行流水 CSV 文件，支持常见银行格式"""
    import csv, io
    text = file_content.decode(encoding) if isinstance(file_content, bytes) else file_content
    lines = text.strip().split("\n")
    if not lines:
        return []
    delimiter = "\t" if "\t" in lines[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    transactions = []
    col_mapping = {
        "date": ["交易日期", "日期", "transaction_date", "日期时间", "记账日期", "交易时间", "时间"],
        "summary": ["摘要", "交易摘要", "备注", "description", "用途", "交易说明", "对方户名摘要", "摘要说明"],
        "amount": ["金额", "交易金额", "amount", "发生额", "金额(元)"],
        "direction": ["借贷", "收支", "direction", "收/支", "交易类型", "借方贷方"],
        "debit": ["借方", "支出", "debit", "借方金额", "支出金额"],
        "credit": ["贷方", "收入", "credit", "贷方金额", "收入金额"],
        "counterparty": ["对方户名", "对方账号", "交易对手", "counterparty", "户名", "对方名称", "收/付款人"],
        "balance": ["余额", "账户余额", "balance", "当前余额"],
    }
    def find_col(row, candidates):
        for c in candidates:
            for key in row.keys():
                if c in key.strip():
                    return key
        return None
    for row in reader:
        if not any(row.values()):
            continue
        date_col = find_col(row, col_mapping["date"])
        summary_col = find_col(row, col_mapping["summary"])
        amount_col = find_col(row, col_mapping["amount"])
        direction_col = find_col(row, col_mapping["direction"])
        debit_col = find_col(row, col_mapping["debit"])
        credit_col = find_col(row, col_mapping["credit"])
        counterparty_col = find_col(row, col_mapping["counterparty"])
        balance_col = find_col(row, col_mapping["balance"])
        txn = {}
        if date_col and row.get(date_col, "").strip():
            txn["date"] = row[date_col].strip()
        else:
            continue
        txn["summary"] = row[summary_col].strip() if summary_col and row.get(summary_col) else ""
        txn["counterparty"] = row[counterparty_col].strip() if counterparty_col and row.get(counterparty_col) else ""
        amount = 0
        direction = "debit"
        if amount_col and row.get(amount_col, "").strip():
            amt_str = row[amount_col].strip().replace(",", "").replace("¥", "").replace("￥", "")
            try:
                amount = abs(float(amt_str))
                direction = "credit" if float(amt_str) > 0 else "debit"
            except ValueError:
                amount = 0
        elif debit_col or credit_col:
            debit_val = 0
            credit_val = 0
            if debit_col and row.get(debit_col, "").strip():
                try:
                    debit_val = abs(float(row[debit_col].strip().replace(",", "").replace("¥", "")))
                except ValueError:
                    pass
            if credit_col and row.get(credit_col, "").strip():
                try:
                    credit_val = abs(float(row[credit_col].strip().replace(",", "").replace("¥", "")))
                except ValueError:
                    pass
            if debit_val > 0:
                amount = debit_val
                direction = "debit"
            elif credit_val > 0:
                amount = credit_val
                direction = "credit"
        if direction_col and row.get(direction_col, "").strip():
            d = row[direction_col].strip()
            if d in ("借", "收", "收入", "CR", "贷方", "存入"):
                direction = "credit"
            elif d in ("贷", "支", "支出", "DR", "借方", "取出"):
                direction = "debit"
        txn["amount"] = amount
        txn["direction"] = direction
        if balance_col and row.get(balance_col, "").strip():
            try:
                txn["balance"] = float(row[balance_col].strip().replace(",", "").replace("¥", ""))
            except ValueError:
                txn["balance"] = 0
        else:
            txn["balance"] = 0
        if amount > 0:
            transactions.append(txn)
    return transactions

def save_classified_transactions(ledger_id, transactions):
    """将分类后的交易保存为草稿凭证，返回凭证号列表"""
    from datetime import date
    voucher_nos = []
    for txn in transactions:
        date_str = txn.get("date", date.today().isoformat())
        summary = txn.get("summary", "")
        amount = txn.get("amount", 0)
        account_code = txn.get("account_code", "6602")
        account_name = txn.get("account_name", "管理费用-其他")
        if txn.get("direction") == "credit":
            entries = [
                {"account_code": "1002", "account_name": "银行存款", "debit": amount, "credit": 0, "summary": summary},
                {"account_code": account_code, "account_name": account_name, "debit": 0, "credit": amount, "summary": summary},
            ]
        else:
            entries = [
                {"account_code": account_code, "account_name": account_name, "debit": amount, "credit": 0, "summary": summary},
                {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": amount, "summary": summary},
            ]
        try:
            vn = create_voucher(ledger_id, date_str, f"银行流水导入-{summary}", entries, status="draft")
            voucher_nos.append(vn)
        except Exception:
            pass
    return voucher_nos
