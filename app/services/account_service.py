"""科目服务层 — 使用 Repository 模式"""
from app.services._utils import run_async, to_dict
import logging
from app.repository.account_repository import AccountRepository, BankAccountRepository, AuxiliaryRepository

logger = logging.getLogger(__name__)

_account_repo = AccountRepository()
_bank_repo = BankAccountRepository()
_aux_repo = AuxiliaryRepository()


# ── Private helpers for methods not yet migrated to repository pattern ──
# These delegate to the old database_v3 functions with a deprecation warning.
# TODO: migrate each to the repository pattern.

def _import_accounts_from_template(ledger_id, system_type):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("import_accounts_from_template: using deprecated database_v3 path", DeprecationWarning)
    from database.account import import_accounts_from_template
    return import_accounts_from_template(ledger_id, system_type)


def _get_account_suggestions(ledger_id, keyword, limit=5):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("get_account_suggestions: using deprecated database_v3 path", DeprecationWarning)
    from database.account import get_account_suggestions
    return get_account_suggestions(ledger_id, keyword, limit)


def _get_avg_amount_for_account(ledger_id, account_code, months=3):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("get_avg_amount_for_account: using deprecated database_v3 path", DeprecationWarning)
    from database.account import get_avg_amount_for_account
    return get_avg_amount_for_account(ledger_id, account_code, months)


def _get_account_ledger(ledger_id, account_code, year, month):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("get_account_ledger: using deprecated database_v3 path", DeprecationWarning)
    from database.ledger import get_account_ledger
    return get_account_ledger(ledger_id, account_code, year, month)


def _get_bank_reconciliation(bank_account_id, period):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("get_bank_reconciliation: using deprecated database_v3 path", DeprecationWarning)
    from database.account import get_bank_reconciliation
    return get_bank_reconciliation(bank_account_id, period)


def _import_bank_statement(bank_account_id, rows):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("import_bank_statement: using deprecated database_v3 path", DeprecationWarning)
    from database.account import import_bank_statement
    return import_bank_statement(bank_account_id, rows)


def _auto_match_bank_statement(bank_account_id):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("auto_match_bank_statement: using deprecated database_v3 path", DeprecationWarning)
    from database.account import auto_match_bank_statement
    return auto_match_bank_statement(bank_account_id)


def _match_bank_statement(stmt_id, journal_id):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("match_bank_statement: using deprecated database_v3 path", DeprecationWarning)
    from database.account import match_bank_statement
    return match_bank_statement(stmt_id, journal_id)


def _unmatch_bank_statement(stmt_id):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("unmatch_bank_statement: using deprecated database_v3 path", DeprecationWarning)
    from database.account import unmatch_bank_statement
    return unmatch_bank_statement(stmt_id)


def _parse_bank_csv(file_path):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("parse_bank_csv: using deprecated database_v3 path", DeprecationWarning)
    from database.classification import parse_bank_csv
    return parse_bank_csv(file_path)


def _save_aux_mapping(entry_id, aux_type, aux_id, aux_name=None):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("save_aux_mapping: using deprecated database_v3 path", DeprecationWarning)
    from database.auxiliary import save_aux_mapping
    return save_aux_mapping(entry_id, aux_type, aux_id, aux_name)


def _get_aux_mapping(entry_id):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("get_aux_mapping: using deprecated database_v3 path", DeprecationWarning)
    from database.auxiliary import get_aux_mapping
    return get_aux_mapping(entry_id)


def _get_aux_balance(ledger_id, aux_type, year=None, month=None):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("get_aux_balance: using deprecated database_v3 path", DeprecationWarning)
    from database.auxiliary import get_aux_balance
    return get_aux_balance(ledger_id, aux_type, year, month)


def _multi_aux_search(ledger_id, aux_filters, year=None, month=None):
    """TODO: migrate to repository pattern"""
    import warnings
    warnings.warn("multi_aux_search: using deprecated database_v3 path", DeprecationWarning)
    from database.auxiliary import multi_aux_search
    return multi_aux_search(ledger_id, aux_filters, year, month)


class AccountService:
    """科目与银行账号管理"""

    # ── 科目 ──
    @staticmethod
    def get_all(ledger_id=None, active_only=True):
        return to_dict(run_async(_account_repo.get_all(active_only=active_only)))

    @staticmethod
    def add(ledger_id, code, name, category, **kwargs):
        """创建科目 — 验证编码唯一性"""
        if not code or not str(code).strip():
            raise ValueError("科目编码不能为空")
        if not name or not str(name).strip():
            raise ValueError("科目名称不能为空")

        # 检查编码唯一性
        existing = to_dict(run_async(_account_repo.search(str(code).strip(), limit=1)))
        if existing:
            # search 可能返回模糊匹配，精确比较编码
            matched = [a for a in existing if a.get("code") == str(code).strip()]
            if matched:
                raise ValueError(f"科目编码 '{code}' 已存在")

        logger.info(f"Creating account code={code}, name={name}, category={category}")
        return to_dict(run_async(_account_repo.create(code=code, name=name, category=category, **kwargs)))

    @staticmethod
    def update_account(account_id, **kwargs):
        """更新科目 — 验证父科目存在"""
        parent_code = kwargs.get("parent_code")
        if parent_code is not None and str(parent_code).strip():
            parent_code = str(parent_code).strip()
            # 验证父科目存在
            parent = to_dict(run_async(_account_repo.search(parent_code, limit=5)))
            if parent:
                parent_matched = [a for a in parent if a.get("code") == parent_code]
            else:
                parent_matched = []
            if not parent_matched:
                raise ValueError(f"父科目编码 '{parent_code}' 不存在")

            # 不能将自己设为自己的父科目
            account = to_dict(run_async(_account_repo.get_by_id(account_id))) if hasattr(_account_repo, "get_by_id") else None
            if account and account.get("code") == parent_code:
                raise ValueError("不能将科目自身设为父科目")

        logger.info(f"Updating account {account_id}")
        return to_dict(run_async(_account_repo.update(account_id, **kwargs)))

    @staticmethod
    def delete_account(account_id):
        """删除科目 — 检查是否有关联凭证"""
        # 检查该科目是否在凭证明细中被引用
        account = to_dict(run_async(_account_repo.get_by_id(account_id))) if hasattr(_account_repo, "get_by_id") else None
        if account:
            account_code = account.get("code")
            if account_code:
                from database.connection import get_conn
                conn = get_conn()
                try:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM journal_entries WHERE account_code = ?",
                        (account_code,)
                    )
                    count = cursor.fetchone()[0]
                    if count > 0:
                        raise PermissionError(
                            f"科目 '{account_code}' 已被 {count} 条凭证明细引用，无法删除"
                        )
                finally:
                    conn.close()

        logger.info(f"Deleting account {account_id}")
        return to_dict(run_async(_account_repo.delete(account_id)))

    @staticmethod
    def search(keyword, limit=10):
        return to_dict(run_async(_account_repo.search(keyword, limit=limit)))

    @staticmethod
    def get_defaults():
        return to_dict(run_async(_account_repo.get_defaults()))

    @staticmethod
    def import_from_template(ledger_id, template_name):
        return _import_accounts_from_template(ledger_id, template_name)

    @staticmethod
    def get_suggestions(ledger_id, account_code):
        return _get_account_suggestions(ledger_id, account_code)

    @staticmethod
    def get_avg_amount(ledger_id, account_code):
        return _get_avg_amount_for_account(ledger_id, account_code)

    @staticmethod
    def get_ledger(ledger_id, account_code, year=None, month=None):
        return _get_account_ledger(ledger_id, account_code, year, month)

    # ── 银行账号 ──
    @staticmethod
    def create_bank_account(ledger_id, **kwargs):
        return to_dict(run_async(_bank_repo.create(ledger_id=ledger_id, **kwargs)))

    @staticmethod
    def get_bank_accounts(ledger_id):
        return to_dict(run_async(_bank_repo.get_by_ledger(ledger_id)))

    @staticmethod
    def update_bank_account(account_id, **kwargs):
        return to_dict(run_async(_bank_repo.update(account_id, **kwargs)))

    @staticmethod
    def delete_bank_account(account_id):
        return to_dict(run_async(_bank_repo.delete(account_id)))

    # ── 银行对账 ──
    @staticmethod
    def get_bank_reconciliation(ledger_id, account_id, year, month):
        return _get_bank_reconciliation(account_id, f"{year}-{month}")

    @staticmethod
    def get_bank_statements(ledger_id, account_id):
        return to_dict(run_async(_bank_repo.get_statements(account_id)))

    @staticmethod
    def get_unmatched(ledger_id, account_id):
        return to_dict(run_async(_bank_repo.get_unmatched_statements(account_id)))

    @staticmethod
    def import_bank_statement(ledger_id, account_id, file_path):
        return _import_bank_statement(account_id, file_path)

    @staticmethod
    def auto_match(ledger_id, account_id):
        return _auto_match_bank_statement(account_id)

    @staticmethod
    def match_statement(ledger_id, statement_id, voucher_no):
        return _match_bank_statement(statement_id, voucher_no)

    @staticmethod
    def unmatch_statement(ledger_id, statement_id):
        return _unmatch_bank_statement(statement_id)

    @staticmethod
    def parse_bank_csv(file_path):
        return _parse_bank_csv(file_path)

    # ── 辅助核算 ──
    @staticmethod
    def create_auxiliary(ledger_id, name, category):
        if not name or not str(name).strip():
            raise ValueError("辅助核算名称不能为空")
        return to_dict(run_async(_aux_repo.create(ledger_id=ledger_id, aux_type=category, code=name, name=name)))

    @staticmethod
    def get_auxiliaries(ledger_id, category=None):
        return to_dict(run_async(_aux_repo.get_by_ledger(ledger_id, aux_type=category)))

    @staticmethod
    def update_auxiliary(aux_id, **kwargs):
        return to_dict(run_async(_aux_repo.update(aux_id, **kwargs)))

    @staticmethod
    def delete_auxiliary(aux_id):
        return to_dict(run_async(_aux_repo.delete(aux_id)))

    @staticmethod
    def save_aux_mapping(ledger_id, aux_type, aux_id, voucher_no):
        return _save_aux_mapping(voucher_no, aux_type, aux_id)

    @staticmethod
    def get_aux_mapping(ledger_id, voucher_no):
        return _get_aux_mapping(voucher_no)

    @staticmethod
    def get_aux_balance(ledger_id, aux_type, aux_id, year, month):
        return _get_aux_balance(ledger_id, aux_type, year, month)

    @staticmethod
    def multi_aux_search(ledger_id, **kwargs):
        return _multi_aux_search(ledger_id, kwargs.get("aux_filters"), kwargs.get("year"), kwargs.get("month"))