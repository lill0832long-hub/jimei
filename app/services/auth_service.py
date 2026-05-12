"""认证服务层 — 使用 Repository 模式"""
import asyncio
from app.repository.auth_repository import AuthRepository, AuditRepository

_auth_repo = AuthRepository()
_audit_repo = AuditRepository()


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


class AuthService:
    """用户认证与权限管理"""

    @staticmethod
    def hash_password(password):
        from database_v3 import hash_password
        return hash_password(password)

    @staticmethod
    def verify_password(password, password_hash):
        from database_v3 import verify_password
        return verify_password(password, password_hash)

    @staticmethod
    def create(username, password, role="user", ledger_id=None):
        from database_v3 import create_user
        return create_user(username, password, role, ledger_id)

    @staticmethod
    def authenticate(username, password):
        from database_v3 import authenticate
        return authenticate(username, password)

    @staticmethod
    def get_all(ledger_id=None):
        return _run(_auth_repo.get_all(ledger_id=ledger_id))

    @staticmethod
    def update(user_id, **kwargs):
        return _run(_auth_repo.update(user_id, **kwargs))

    @staticmethod
    def delete(user_id):
        return _run(_auth_repo.delete(user_id))

    @staticmethod
    def change_password(user_id, new_password):
        from database_v3 import change_password
        return change_password(user_id, new_password)

    @staticmethod
    def check_permission(user, permission):
        from database_v3 import check_permission
        return check_permission(user, permission)

    @staticmethod
    def get_audit_logs(ledger_id, limit=50, module=None, action=None, start_date=None, end_date=None):
        return _run(_audit_repo.get_logs(ledger_id, limit=limit, module=module, action=action))
