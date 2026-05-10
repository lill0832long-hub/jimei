"""Database module: backup domain"""

from .connection import get_conn, transaction, DB_PATH

def backup_database(ledger_id: int, backup_dir: str) -> str:
    """按账套备份数据为JSON文件，返回文件路径"""
    import json
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ledger = get_ledger(ledger_id)
    if not ledger:
        raise ValueError("账套不存在")

    conn = get_conn()
    vouchers = conn.execute("SELECT * FROM vouchers WHERE ledger_id = ?", (ledger_id,)).fetchall()
    entries = conn.execute("SELECT * FROM journal_entries WHERE ledger_id = ?", (ledger_id,)).fetchall()
    ob = conn.execute("SELECT * FROM opening_balances WHERE ledger_id = ?", (ledger_id,)).fetchall()
    audit = conn.execute("SELECT * FROM audit_logs WHERE ledger_id = ?", (ledger_id,)).fetchall()
    conn.close()

    data = {
        "version": "2.0",
        "backup_time": datetime.now().isoformat(),
        "ledger": dict(ledger),
        "vouchers": [dict(v) for v in vouchers],
        "journal_entries": [dict(e) for e in entries],
        "opening_balances": [dict(o) for o in ob],
        "audit_logs": [dict(a) for a in audit],
    }

    fname = "backup_ledger{}_{}.json".format(ledger_id, ts)
    fpath = os.path.join(backup_dir, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fpath

def backup_full_database(backup_dir: str) -> str:
    """完整数据库备份（直接复制SQLite文件），返回文件路径"""
    import shutil
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"full_backup_{ts}.db"
    fpath = os.path.join(backup_dir, fname)
    shutil.copy2(DB_PATH, fpath)
    return fpath

def restore_database(backup_dir: str, target_ledger_id: int = None) -> dict:
    """从JSON备份恢复账套数据
    如果 target_ledger_id 为 None，创建新账套
    如果指定 target_ledger_id，恢复到已有账套（追加模式，跳过已存在凭证）
    返回: {"ledger_id": int, "vouchers_restored": int, "skipped": int}
    """
    import json
    # Find the backup file
    files = [f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.json')]
    if not files:
        raise ValueError("备份目录中没有找到备份文件")
    files.sort(reverse=True)
    fpath = os.path.join(backup_dir, files[0])

    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    vouchers = data.get("vouchers", [])
    entries = data.get("journal_entries", [])
    ob_records = data.get("opening_balances", [])

    if target_ledger_id is None:
        # Create new ledger
        ledger_info = data.get("ledger", {})
        new_id = create_ledger(
            name=ledger_info.get("name", "恢复账套") + "_恢复",
            company=ledger_info.get("company", "未知公司"),
            currency=ledger_info.get("currency", "CNY"),
        )
        target_ledger_id = new_id

    # Restore opening balances
    for ob in ob_records:
        try:
            set_opening_balance(target_ledger_id, ob["account_code"], ob["year"], ob["month"], ob["balance"])
        except Exception:
            pass

    # Restore vouchers (skip existing voucher_no)
    restored = 0
    skipped = 0
    conn = get_conn()
    for v in vouchers:
        existing = conn.execute("SELECT id FROM vouchers WHERE voucher_no = ?", (v["voucher_no"],)).fetchone()
        if existing:
            skipped += 1
            continue
        v_entries = [e for e in entries if e.get("voucher_id") == v["id"]]
        try:
            create_voucher(
                target_ledger_id,
                v["date"],
                v["description"],
                [{"account_code": e["account_code"], "account_name": e["account_name"],
                  "debit": e["debit"], "credit": e["credit"], "summary": e.get("summary", "")}
                 for e in v_entries],
                status=v.get("status", "posted")
            )
            restored += 1
        except Exception:
            skipped += 1
    conn.close()

    return {"ledger_id": target_ledger_id, "vouchers_restored": restored, "skipped": skipped}
