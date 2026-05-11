"""Database module: auth domain"""

from .connection import get_conn, transaction, DB_PATH, clear_query_cache

def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(password: str, password_hash: str) -> bool:
    import bcrypt, hashlib
    # bcrypt hashes start with $2b$/$2a$/$2y$
    if password_hash.startswith("$2"):
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    # legacy SHA-256 hash (64 hex chars)
    if len(password_hash) == 64:
        return hashlib.sha256(password.encode()).hexdigest() == password_hash
    # legacy SHA-1 hash (40 hex chars)
    return hashlib.sha1(password.encode()).hexdigest() == password_hash

def create_user(username: str, password: str, role: str = "user", ledger_id: int = None):
    """创建用户"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, ledger_id) VALUES (?,?,?,?)",
            (username, hash_password(password), role, ledger_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"用户名 {username} 已存在")
    finally:
        conn.close()

def authenticate(username: str, password: str) -> dict:
    """验证用户登录，返回用户信息（bcrypt 验证）"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1",
        (username,)
    ).fetchone()
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        return dict(row)
    return None

def get_users(ledger_id: int = None) -> list:
    """获取用户列表"""
    conn = get_conn()
    if ledger_id:
        rows = conn.execute("SELECT id, username, role, ledger_id, is_active, created_at FROM users WHERE ledger_id = ? ORDER BY created_at", (ledger_id,)).fetchall()
    else:
        rows = conn.execute("SELECT id, username, role, ledger_id, is_active, created_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user(user_id: int, **kwargs):
    """更新用户信息"""
    allowed = {"role", "is_active", "ledger_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn = get_conn()
    conn.execute(f"UPDATE users SET {set_clause}, updated_at = datetime('now','localtime') WHERE id = ?",
                 list(updates.values()) + [user_id])
    conn.commit()
    conn.close()
    clear_query_cache()

def delete_user(user_id: int):
    """删除用户"""
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    clear_query_cache()

def change_password(user_id: int, new_password: str):
    """修改密码"""
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                 (hash_password(new_password), user_id))
    conn.commit()
    conn.close()
    clear_query_cache()

def check_permission(user: dict, permission: str) -> bool:
    """检查用户是否有指定权限"""
    if not user:
        return False
    role = user.get("role", ROLE_VIEWER)
    if role == ROLE_ADMIN:
        return True
    return role in PERMISSIONS.get(permission, set())
