"""认证服务层 — 封装 database_v3 的用户认证/审计日志相关操作"""
from database_v3 import (
    hash_password, verify_password, create_user, authenticate,
    get_users, update_user, delete_user, change_password, check_permission,
    get_audit_logs,
)


class AuthService:
    """用户认证与权限管理"""

    @staticmethod
    def hash_password(password):
        return hash_password(password)

    @staticmethod
    def verify_password(password, password_hash):
        return verify_password(password, password_hash)

    @staticmethod
    def create(username, password, role="user", ledger_id=None):
        return create_user(username, password, role, ledger_id)

    @staticmethod
    def authenticate(username, password):
        return authenticate(username, password)

    @staticmethod
    def get_all(ledger_id=None):
        return get_users(ledger_id)

    @staticmethod
    def update(user_id, **kwargs):
        return update_user(user_id, **kwargs)

    @staticmethod
    def delete(user_id):
        return delete_user(user_id)

    @staticmethod
    def change_password(user_id, new_password):
        return change_password(user_id, new_password)

    @staticmethod
    def check_permission(user, permission):
        return check_permission(user, permission)

    @staticmethod
    def get_audit_logs(ledger_id, limit=50, module=None, action=None, start_date=None, end_date=None):
        return get_audit_logs(ledger_id, limit=limit, module=module, action=action, start_date=start_date, end_date=end_date)
