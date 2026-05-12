"""认证服务层 — 使用 Repository 模式"""
import asyncio
import bcrypt
import hashlib
from app.repository.auth_repository import AuthRepository, AuditRepository

_auth_repo = AuthRepository()
_audit_repo = AuditRepository()

# ── 角色与权限常量 ──
ROLE_ADMIN = "admin"
ROLE_ACCOUNTANT = "accountant"
ROLE_REVIEWER = "reviewer"
ROLE_POSTER = "poster"
ROLE_VIEWER = "viewer"

PERMISSIONS = {
    "create_voucher": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "edit_voucher": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "delete_voucher": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "submit_review": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "approve_voucher": {ROLE_ADMIN, ROLE_REVIEWER},
    "reject_voucher": {ROLE_ADMIN, ROLE_REVIEWER},
    "post_voucher": {ROLE_ADMIN, ROLE_POSTER},
    "reverse_voucher": {ROLE_ADMIN, ROLE_POSTER},
    "manage_users": {ROLE_ADMIN},
    "manage_settings": {ROLE_ADMIN},
    "view_reports": {ROLE_ADMIN, ROLE_ACCOUNTANT, ROLE_REVIEWER, ROLE_POSTER, ROLE_VIEWER},
    "export_data": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_ledger": {ROLE_ADMIN},
    "manage_budget": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_tax": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_period": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_fixed_asset": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_invoice": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_cash_flow": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_auxiliary": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_bank_account": {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "manage_ai_rules": {ROLE_ADMIN},
    "view_audit_log": {ROLE_ADMIN},
    "backup_restore": {ROLE_ADMIN},
}


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _to_dict(obj):
    """Convert SQLAlchemy model instance(s) to dict(s)."""
    if obj is None:
        return None
    if isinstance(obj, (list, tuple)):
        return [_to_dict(item) for item in obj]
    if hasattr(obj, "__table__"):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    if isinstance(obj, dict):
        return obj
    return obj


class AuthService:
    """用户认证与权限管理"""

    @staticmethod
    def hash_password(password):
        """使用 bcrypt 哈希密码"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    @staticmethod
    def verify_password(password, password_hash):
        """验证密码 — 支持 bcrypt 和旧版 SHA-256/SHA-1"""
        # bcrypt hashes start with $2b$/$2a$/$2y$
        if password_hash.startswith("$2"):
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        # legacy SHA-256 hash (64 hex chars)
        if len(password_hash) == 64:
            return hashlib.sha256(password.encode()).hexdigest() == password_hash
        # legacy SHA-1 hash (40 hex chars)
        return hashlib.sha1(password.encode()).hexdigest() == password_hash

    @staticmethod
    def create(username, password, role="user", ledger_id=None):
        password_hash = AuthService.hash_password(password)
        return _run(_auth_repo.create(
            username=username, password_hash=password_hash,
            role=role, ledger_id=ledger_id
        ))

    @staticmethod
    def authenticate(username, password):
        user = _run(_auth_repo.get_by_username(username=username))
        if user is None:
            return None
        # 检查用户是否激活
        if hasattr(user, 'is_active') and not user.is_active:
            return None
        if AuthService.verify_password(password, user.password_hash):
            return {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "ledger_id": user.ledger_id,
                "is_active": user.is_active if hasattr(user, 'is_active') else 1,
                "created_at": user.created_at if hasattr(user, 'created_at') else None,
            }
        return None

    @staticmethod
    def get_all(ledger_id=None):
        return _to_dict(_run(_auth_repo.get_all(ledger_id=ledger_id)))

    @staticmethod
    def update(user_id, **kwargs):
        return _to_dict(_run(_auth_repo.update(user_id, **kwargs)))

    @staticmethod
    def delete(user_id):
        return _to_dict(_run(_auth_repo.delete(user_id)))

    @staticmethod
    def change_password(user_id, new_password):
        password_hash = AuthService.hash_password(new_password)
        return _to_dict(_run(_auth_repo.update(user_id, password_hash=password_hash)))

    @staticmethod
    def check_permission(user, permission):
        if not user:
            return False
        role = user.get("role", ROLE_VIEWER)
        if role == ROLE_ADMIN:
            return True
        return role in PERMISSIONS.get(permission, set())

    @staticmethod
    def get_audit_logs(ledger_id, limit=50, module=None, action=None, start_date=None, end_date=None):
        return _to_dict(_run(_audit_repo.get_logs(ledger_id, limit=limit, module=module, action=action)))
