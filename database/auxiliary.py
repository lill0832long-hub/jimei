"""Database module: auxiliary domain"""

from .connection import get_conn, release_conn, transaction, DB_PATH, clear_query_cache

def create_auxiliary(ledger_id, aux_type, code, name, parent_id=None):
    """创建辅助核算项目"""
    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO auxiliary_categories (ledger_id, aux_type, code, name, parent_id)
            VALUES (?,?,?,?,?)
        """, (ledger_id, aux_type, code, name, parent_id))
        aux_id = cur.lastrowid
        conn.commit()
    finally:
        release_conn(conn)
    clear_query_cache()
    return aux_id

def get_auxiliaries(ledger_id, aux_type=None):
    """获取辅助核算列表"""
    conn = get_conn()
    try:
        if aux_type:
            rows = conn.execute(
                "SELECT * FROM auxiliary_categories WHERE ledger_id = ? AND aux_type = ? AND is_active = 1 ORDER BY code",
                (ledger_id, aux_type)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM auxiliary_categories WHERE ledger_id = ? AND is_active = 1 ORDER BY aux_type, code",
                (ledger_id,)).fetchall()
    finally:
        release_conn(conn)
    return [dict(r) for r in rows]

def update_auxiliary(aux_id, code=None, name=None, is_active=None):
    """更新辅助核算项目"""
    conn = get_conn()
    try:
        updates = []
        params = []
        if code is not None:
            updates.append("code = ?")
            params.append(code)
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)
        if not updates:
            release_conn(conn)
            return
        params.append(aux_id)
        conn.execute(f"UPDATE auxiliary_categories SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    finally:
        release_conn(conn)
    clear_query_cache()

def delete_auxiliary(aux_id):
    """删除辅助核算项目（检查是否被引用）"""
    conn = get_conn()
    try:
        ref = conn.execute("SELECT COUNT(*) as cnt FROM voucher_entry_auxiliaries WHERE aux_id = ?", (aux_id,)).fetchone()['cnt']
        if ref > 0:
            release_conn(conn)
            return False, f"该辅助核算项目已被 {ref} 条凭证分录引用，无法删除"
        conn.execute("DELETE FROM auxiliary_categories WHERE id = ?", (aux_id,))
        conn.commit()
    finally:
        release_conn(conn)
    clear_query_cache()
    return True, "删除成功"

def save_aux_mapping(entry_id, aux_type, aux_id, aux_name=None):
    """保存凭证分录与辅助核算的关联"""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM voucher_entry_auxiliaries WHERE entry_id = ? AND aux_type = ?",
                     (entry_id, aux_type))
        if aux_id:
            conn.execute(
                "INSERT INTO voucher_entry_auxiliaries (entry_id, aux_type, aux_id, aux_name) VALUES (?,?,?,?)",
                (entry_id, aux_type, aux_id, aux_name))
        conn.commit()
    finally:
        release_conn(conn)
    clear_query_cache()

def get_aux_mapping(entry_id):
    """获取凭证分录的辅助核算关联"""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM voucher_entry_auxiliaries WHERE entry_id = ?", (entry_id,)).fetchall()
    finally:
        release_conn(conn)
    return [dict(r) for r in rows]

def get_aux_balance(ledger_id, aux_type, year=None, month=None):
    """辅助核算余额表：按辅助核算项汇总借贷方"""
    conn = get_conn()
    try:
        date_filter = ""
        params = [ledger_id, aux_type]
        if year:
            date_filter += " AND strftime('%Y', v.date) = ?"
            params.append(str(year))
        if month:
            date_filter += " AND strftime('%m', v.date) = ?"
            params.append(f"{month:02d}")

        rows = conn.execute(
            "SELECT ac.id as aux_id, ac.code as aux_code, ac.name as aux_name, ac.aux_type, "
            "COALESCE(SUM(CASE WHEN je.amount > 0 THEN je.amount ELSE 0 END), 0) as total_debit, "
            "COALESCE(SUM(CASE WHEN je.amount < 0 THEN ABS(je.amount) ELSE 0 END), 0) as total_credit "
            "FROM auxiliary_categories ac "
            "LEFT JOIN voucher_entry_auxiliaries vea ON vea.aux_id = ac.id AND vea.aux_type = ac.aux_type "
            "LEFT JOIN journal_entries je ON je.id = vea.entry_id "
            "LEFT JOIN vouchers v ON v.id = je.voucher_id AND v.ledger_id = ? "
            "WHERE ac.ledger_id = ? AND ac.aux_type = ? AND ac.is_active = 1 " + date_filter + " "
            "GROUP BY ac.id, ac.code, ac.name, ac.aux_type ORDER BY ac.code",
            params).fetchall()
    finally:
        release_conn(conn)
    return [dict(r) for r in rows]

def multi_aux_search(ledger_id, aux_filters, year=None, month=None):
    """多维交叉查询：aux_filters = [(aux_type, aux_id), ...]"""
    conn = get_conn()
    try:
        if not aux_filters:
            return []

        joins = []
        where_parts = ["v.ledger_id = ?"]
        params = [ledger_id]
        date_filter = ""

        for i, (atype, aid) in enumerate(aux_filters):
            alias = f"vea{i}"
            joins.append(f"INNER JOIN voucher_entry_auxiliaries {alias} ON {alias}.entry_id = je.id")
            where_parts.append(f"{alias}.aux_type = ? AND {alias}.aux_id = ?")
            params.extend([atype, aid])

        if year:
            date_filter += " AND strftime('%Y', v.date) = ?"
            params.append(str(year))
        if month:
            date_filter += " AND strftime('%m', v.date) = ?"
            params.append(f"{month:02d}")

        join_str = " ".join(joins)
        where_str = " AND ".join(where_parts)

        sql = (
            "SELECT DISTINCT v.voucher_no, v.date, v.summary, v.total_debit, v.total_credit, v.status "
            "FROM vouchers v "
            "INNER JOIN journal_entries je ON je.voucher_id = v.id "
            + join_str + " "
            "WHERE " + where_str + " " + date_filter + " "
            "ORDER BY v.date DESC, v.voucher_no DESC"
        )
        rows = conn.execute(sql, params).fetchall()
    finally:
        release_conn(conn)
    return [dict(r) for r in rows]
