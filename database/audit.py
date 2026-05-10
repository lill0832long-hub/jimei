"""Database module: audit domain"""

from .connection import get_conn, transaction, DB_PATH

def add_audit_log(ledger_id, action, detail, voucher_id=None, user_id=None,
                  operator_name=None, module=None, target_table=None, target_id=None,
                  old_value=None, new_value=None, ip_address=None, remark=None):
    """写入审计日志（支持完整字段）
    
    Args:
        ledger_id: 账套ID
        action: 操作类型 (create_voucher/delete_voucher/post_voucher/restore/...)
        detail: 操作描述
        voucher_id: 关联凭证ID
        user_id: 操作人ID
        operator_name: 操作人姓名
        module: 模块 (voucher/account/period/system/settings/...)
        target_table: 目标表名
        target_id: 目标记录ID
        old_value: 变更前值 (JSON字符串)
        new_value: 变更后值 (JSON字符串)
        ip_address: IP地址
        remark: 备注
    """
    import json as _json
    conn = get_conn()
    conn.execute(
        """INSERT INTO audit_logs 
           (ledger_id, action, detail, voucher_id, user_id, operator_name, module,
            target_table, target_id, old_value, new_value, ip_address, remark)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ledger_id, action, detail, voucher_id, user_id, operator_name, module,
         target_table, target_id,
         _json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
         _json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
         ip_address, remark)
    )
    conn.commit()
    conn.close()
    clear_query_cache()

def get_audit_logs(ledger_id, limit=50, module=None, action=None, start_date=None, end_date=None):
    """查询审计日志（支持多维度筛选）"""
    conn = get_conn()
    conditions = ["ledger_id = ?"]
    params = [ledger_id]
    if module:
        conditions.append("module = ?")
        params.append(module)
    if action:
        conditions.append("action = ?")
        params.append(action)
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date)
    params.append(limit)
    # SECURITY: conditions are all hardcoded strings, user input goes through parameterized query
    # No SQL injection risk. Do not modify conditions to include user input directly.
    where = " AND ".join(conditions)
    rows = conn.execute(
        f"SELECT * FROM audit_logs WHERE {where} ORDER BY created_at DESC LIMIT ?",
        params
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_workflow_log(ledger_id, voucher_id, action, from_status, to_status, user_id=None, comment=None):
    """记录审核工作流日志"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO voucher_workflow (voucher_id, ledger_id, action, from_status, to_status, user_id, comment) "
        "VALUES (?,?,?,?,?,?,?)",
        (voucher_id, ledger_id, action, from_status, to_status, user_id, comment)
    )
    conn.commit()
    conn.close()
    clear_query_cache()
