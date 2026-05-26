"""Database module: ledger domain"""

from .connection import get_conn, transaction, DB_PATH, clear_query_cache

def create_ledger(name, company="默认公司", currency="CNY", fiscal_start=None, fiscal_end=None, settings=None):
    """创建新账套"""
    import json
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO ledgers (name, company, currency, fiscal_year_start, fiscal_year_end, settings) VALUES (?,?,?,?,?,?)",
            (name, company, currency,
             fiscal_start or f"{datetime.now().year}-01-01",
             fiscal_end or f"{datetime.now().year}-12-31",
             json.dumps(settings) if settings else None)
        )
        ledger_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    clear_query_cache()
    return ledger_id

def get_ledgers():
    """获取所有账套"""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM ledgers ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]

def get_ledger(ledger_id):
    """获取单个账套"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM ledgers WHERE id = ?", (ledger_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None

def update_ledger(ledger_id, **kwargs):
    """更新账套信息"""
    import json
    allowed = {"name", "company", "currency", "fiscal_year_start", "fiscal_year_end", "status", "settings"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if "settings" in updates and isinstance(updates["settings"], dict):
        updates["settings"] = json.dumps(updates["settings"])
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn = get_conn()
    try:
        conn.execute(f"UPDATE ledgers SET {set_clause}, updated_at = datetime('now','localtime') WHERE id = ?",
                     list(updates.values()) + [ledger_id])
        conn.commit()
    finally:
        conn.close()
    clear_query_cache()

def delete_ledger(ledger_id):
    """删除账套（级联删除所有相关数据）"""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM audit_logs WHERE ledger_id = ?", (ledger_id,))
        conn.execute("DELETE FROM journal_entries WHERE ledger_id = ?", (ledger_id,))
        conn.execute("DELETE FROM vouchers WHERE ledger_id = ?", (ledger_id,))
        conn.execute("DELETE FROM opening_balances WHERE ledger_id = ?", (ledger_id,))
        conn.execute("DELETE FROM documents WHERE ledger_id = ?", (ledger_id,))
        conn.execute("DELETE FROM ledgers WHERE id = ?", (ledger_id,))
        conn.commit()
    finally:
        conn.close()
    clear_query_cache()

def backup_ledger_to_json(ledger_id: int, backup_dir: str) -> str:
    """将指定账套数据备份为JSON文件，返回文件路径"""
    import json
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"backup_ledger{ledger_id}_{ts}.json"
    fpath = os.path.join(backup_dir, fname)

    conn = get_conn()
    try:
        ledger = conn.execute("SELECT * FROM ledgers WHERE id = ?", (ledger_id,)).fetchone()
        if not ledger:
            conn.close()
            raise ValueError("账套不存在")

        vouchers = conn.execute("SELECT * FROM vouchers WHERE ledger_id = ?", (ledger_id,)).fetchall()
        entries = conn.execute("SELECT * FROM journal_entries WHERE ledger_id = ?", (ledger_id,)).fetchall()
        openings = conn.execute("SELECT * FROM opening_balances WHERE ledger_id = ?", (ledger_id,)).fetchall()
        audits = conn.execute("SELECT * FROM audit_logs WHERE ledger_id = ?", (ledger_id,)).fetchall()
    finally:
        conn.close()

    data = {
        "version": "2.0",
        "type": "ledger_backup",
        "created_at": datetime.now().isoformat(),
        "ledger": dict(ledger),
        "vouchers": [dict(v) for v in vouchers],
        "journal_entries": [dict(e) for e in entries],
        "opening_balances": [dict(o) for o in openings],
        "audit_logs": [dict(a) for a in audits],
    }

    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fpath

def restore_ledger_from_json(fpath: str, target_ledger_id: int = None, user_id: int = None, operator_name: str = None) -> int:
    """从JSON备份恢复账套，返回账套ID"""
    import json
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = get_conn()
    try:
        # 创建或获取账套
        if target_ledger_id is None:
            # 创建新账套
            ledger_name = data["ledger"]["name"] + " (恢复)"
            cur = conn.execute(
                "INSERT INTO ledgers (name, company, currency, fiscal_year_start, fiscal_year_end, status) VALUES (?,?,?,?,?,'active')",
                (ledger_name, data["ledger"].get("company", "未知"), data["ledger"].get("currency", "CNY"),
                 data["ledger"].get("fiscal_year_start", f"{datetime.now().year}-01-01"),
                 data["ledger"].get("fiscal_year_end", f"{datetime.now().year}-12-31"))
            )
            new_ledger_id = cur.lastrowid
        else:
            new_ledger_id = target_ledger_id

        # 恢复期初余额
        for ob in data.get("opening_balances", []):
            conn.execute("""
                INSERT OR IGNORE INTO opening_balances (ledger_id, account_code, year, month, balance)
                VALUES (?,?,?,?,?)
            """, (new_ledger_id, ob["account_code"], ob["year"], ob["month"], ob["balance"]))

        # 恢复凭证（跳过已存在的凭证号）
        existing_nos = set(r["voucher_no"] for r in conn.execute(
            "SELECT voucher_no FROM vouchers WHERE ledger_id = ?", (new_ledger_id,)).fetchall())

        for v in data.get("vouchers", []):
            if v["voucher_no"] in existing_nos:
                continue
            conn.execute("""
                INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status, currency, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (new_ledger_id, v["voucher_no"], v["date"], v.get("description", ""),
                  v.get("total_debit", 0), v.get("total_credit", 0), v.get("status", "posted"),
                  v.get("currency", "CNY"), v.get("created_at", datetime.now().isoformat()),
                  v.get("updated_at", datetime.now().isoformat())))

            # 获取新插入的凭证ID
            new_vid = conn.execute("SELECT id FROM vouchers WHERE voucher_no = ?", (v["voucher_no"],)).fetchone()["id"]
            old_vid = v["id"]

            # 恢复该凭证的明细
            for je in data.get("journal_entries", []):
                if je.get("voucher_id") == old_vid or je.get("voucher_id") == v["id"]:
                    conn.execute("""
                        INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary, foreign_currency, foreign_amount, exchange_rate)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (new_ledger_id, new_vid, je["account_code"], je["account_name"],
                          je.get("debit", 0), je.get("credit", 0), je.get("summary", ""),
                          je.get("foreign_currency", ""), je.get("foreign_amount", 0), je.get("exchange_rate", 1)))

        # 审计日志
        add_audit_log(
            ledger_id=new_ledger_id,
            action="restore",
            detail=f"从备份文件 {os.path.basename(fpath)} 恢复",
            module="system",
            target_table="ledgers",
            user_id=user_id,
            operator_name=operator_name,
            remark=f"备份文件:{os.path.basename(fpath)}",
            conn=conn,
        )

        conn.commit()
        return new_ledger_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_general_ledger(ledger_id, account_code=None, year=None, month=None):
    """获取总分类账：所有科目（或指定科目）在期间内的凭证分录明细，按日期排序"""
    conn = get_conn()
    try:
        date_filter = ""
        params = [ledger_id]

        if account_code:
            date_filter += " AND je.account_code = ?"
            params.append(account_code)
        if year:
            date_filter += " AND strftime('%Y', v.date) = ?"
            params.append(str(year))
        if month:
            date_filter += " AND strftime('%m', v.date) = ?"
            params.append(f"{month:02d}")

        rows = conn.execute("""
            SELECT je.id, je.debit, je.credit, je.summary,
                   je.account_code, je.account_name,
                   v.voucher_no, v.date, v.description as voucher_desc, v.status
            FROM journal_entries je
            JOIN vouchers v ON je.voucher_id = v.id
            WHERE je.ledger_id = ? """ + date_filter + """
              AND v.status = 'posted'
            ORDER BY v.date, v.voucher_no, je.id
        """, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_aux_ledger(ledger_id, aux_type, aux_id, year=None, month=None):
    """辅助核算明细账：按辅助核算项查看凭证分录"""
    conn = get_conn()
    try:
        date_filter = ""
        params = [aux_id, aux_type, ledger_id]
        if year:
            date_filter += " AND strftime('%Y', v.date) = ?"
            params.append(str(year))
        if month:
            date_filter += " AND strftime('%m', v.date) = ?"
            params.append(f"{month:02d}")

        rows = conn.execute(
            "SELECT v.voucher_no, v.date, v.summary as voucher_summary, "
            "je.account_code, je.account_name, je.amount, je.summary as entry_summary, "
            "vea.aux_type, vea.aux_name, v.status "
            "FROM voucher_entry_auxiliaries vea "
            "INNER JOIN journal_entries je ON je.id = vea.entry_id "
            "INNER JOIN vouchers v ON v.voucher_no = je.voucher_no "
            "WHERE vea.aux_id = ? AND vea.aux_type = ? AND v.ledger_id = ? " + date_filter + " "
            "ORDER BY v.date, v.voucher_no",
            params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]

def get_account_ledger(ledger_id, account_code, year, month):
    """获取科目明细账：返回指定科目在期间内的所有凭证分录及余额"""
    conn = get_conn()
    try:
        acct = conn.execute("SELECT code, name, category FROM accounts WHERE code=? AND is_active=1", (account_code,)).fetchone()
        if not acct:
            conn.close()
            return None
        acct = dict(acct)
        opening = get_opening_balance(ledger_id, account_code, year, month)
        entries = conn.execute("""
            SELECT je.id, je.debit, je.credit, je.summary,
                   v.voucher_no, v.date, v.description as voucher_desc, v.status
            FROM journal_entries je
            JOIN vouchers v ON je.voucher_id = v.id
            WHERE je.ledger_id = ? AND je.account_code = ?
              AND strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) <= ?
              AND v.status = 'posted'
            ORDER BY v.date, v.voucher_no, je.id
        """, (ledger_id, account_code, str(year), month)).fetchall()
    finally:
        conn.close()
    bal = opening
    rows = []
    for e in entries:
        d = dict(e)
        bal += d["debit"] - d["credit"]
        d["balance"] = round(bal, 2)
        rows.append(d)
    return {
        "account": acct,
        "opening_balance": round(opening, 2),
        "closing_balance": round(bal, 2),
        "entries": rows,
        "period": f"{year}-{month:02d}",
    }
