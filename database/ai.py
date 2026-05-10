"""Database module: ai domain"""

from .connection import get_conn, transaction, DB_PATH

def get_ai_rules_complex(active_only=True) -> list:
    """获取所有复合业务规则"""
    conn = get_conn()
    sql = "SELECT * FROM ai_rules_complex"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY priority DESC, id"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_ai_rules_complex(name, pattern, description, entries_json, priority=50):
    """添加复合业务规则"""
    import json
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO ai_rules_complex (name, pattern, description, entries_json, priority)
            VALUES (?,?,?,?,?)
        """, (name, pattern, description, json.dumps(entries_json, ensure_ascii=False), priority))
        conn.commit()
    finally:
        conn.close()

def delete_ai_rules_complex(rule_id):
    """删除复合业务规则"""
    conn = get_conn()
    conn.execute("DELETE FROM ai_rules_complex WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    clear_query_cache()

def toggle_ai_rules_complex(rule_id):
    """启用/禁用复合业务规则"""
    conn = get_conn()
    conn.execute("UPDATE ai_rules_complex SET is_active = 1 - is_active, updated_at = datetime('now','localtime') WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    clear_query_cache()

def query_db(sql, params=()):
    """执行查询并返回字典列表"""
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "finance_v2.db")
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _init_complex_rules(c):
    """初始化内置复合业务规则到 ai_rules_complex 表"""
    import json as _json
    c.execute("SELECT COUNT(*) FROM ai_rules_complex")
    if c.fetchone()[0] > 0:
        return

    builtin_rules = [
        {
            "name": "采购含运费",
            "pattern": "采购.*运费",
            "description": "采购材料并支付运费",
            "priority": 90,
            "entries": [
                {"account_code": "1403", "account_name": "原材料", "debit_key": "material", "credit": 0},
                {"account_code": "6601", "account_name": "销售费用-运费", "debit_key": "freight", "credit": 0},
                {"account_code": "222101", "account_name": "应交增值税(进项)", "debit_key": "vat", "credit": 0},
                {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit_key": "total"},
            ],
        },
        {
            "name": "销售含折扣",
            "pattern": "销售.*折扣",
            "description": "销售商品并给予折扣",
            "priority": 90,
            "entries": [
                {"account_code": "1002", "account_name": "银行存款", "debit_key": "cash", "credit": 0},
                {"account_code": "6601", "account_name": "销售费用-折扣", "debit_key": "discount", "credit": 0},
                {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit_key": "total"},
            ],
        },
        {
            "name": "工资发放代扣个税",
            "pattern": "发放工资.*个税",
            "description": "发放工资并代扣个人所得税",
            "priority": 85,
            "entries": [
                {"account_code": "2211", "account_name": "应付职工薪酬", "debit_key": "gross", "credit": 0},
                {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit_key": "net"},
                {"account_code": "222102", "account_name": "应交税费-个税", "debit": 0, "credit_key": "tax"},
            ],
        },
        {
            "name": "固定资产处置",
            "pattern": "处置.*固定资产",
            "description": "处置固定资产（报废/出售）",
            "priority": 80,
            "entries": [
                {"account_code": "1602", "account_name": "累计折旧", "debit_key": "accumulated", "credit": 0},
                {"account_code": "1601", "account_name": "固定资产清理", "debit_key": "net", "credit": 0},
                {"account_code": "1601", "account_name": "固定资产", "debit": 0, "credit_key": "original"},
                {"account_code": "1002", "account_name": "银行存款", "debit_key": "proceeds", "credit": 0},
            ],
        },
        {
            "name": "在建工程转固",
            "pattern": "在建工程.*完工",
            "description": "在建工程完工结转固定资产",
            "priority": 85,
            "entries": [
                {"account_code": "1601", "account_name": "固定资产", "debit_key": "amount", "credit": 0},
                {"account_code": "1604", "account_name": "在建工程", "debit": 0, "credit_key": "amount"},
            ],
        },
    ]

    for rule in builtin_rules:
        entries = rule.pop("entries")
        c.execute("""
            INSERT INTO ai_rules_complex (name, pattern, description, entries_json, priority)
            VALUES (?,?,?,?,?)
        """, (rule["name"], rule["pattern"], rule["description"],
              _json.dumps(entries, ensure_ascii=False), rule["priority"]))
