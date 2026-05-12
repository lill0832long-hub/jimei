"""科目服务层 — 使用 Repository 模式"""
import asyncio
from app.repository.account_repository import AccountRepository, BankAccountRepository, AuxiliaryRepository

_account_repo = AccountRepository()
_bank_repo = BankAccountRepository()
_aux_repo = AuxiliaryRepository()


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


class AccountService:
    """科目与银行账号管理"""

    # ── 科目 ──
    @staticmethod
    def get_all(ledger_id=None, active_only=True):
        return _run(_account_repo.get_all(active_only=active_only))

    @staticmethod
    def add(ledger_id, code, name, category, **kwargs):
        return _run(_account_repo.create(code=code, name=name, category=category, **kwargs))

    @staticmethod
    def search(keyword, limit=10):
        return _run(_account_repo.search(keyword, limit=limit))

    @staticmethod
    def get_defaults():
        return _run(_account_repo.get_defaults())

    @staticmethod
    def import_from_template(ledger_id, template_name):
        # Template import requires raw SQL for bulk insert - keep old impl for now
        from database_v3 import import_accounts_from_template
        return import_accounts_from_template(ledger_id, template_name)

    @staticmethod
    def get_suggestions(ledger_id, account_code):
        from database_v3 import get_account_suggestions
        return get_account_suggestions(ledger_id, account_code)

    @staticmethod
    def get_avg_amount(ledger_id, account_code):
        from database_v3 import get_avg_amount_for_account
        return get_avg_amount_for_account(ledger_id, account_code)

    @staticmethod
    def get_ledger(ledger_id, account_code, year=None, month=None):
        from database_v3 import get_account_ledger
        return get_account_ledger(ledger_id, account_code, year, month)

    # ── 银行账号 ──
    @staticmethod
    def create_bank_account(ledger_id, **kwargs):
        return _run(_bank_repo.create(ledger_id=ledger_id, **kwargs))

    @staticmethod
    def get_bank_accounts(ledger_id):
        return _run(_bank_repo.get_by_ledger(ledger_id))

    @staticmethod
    def update_bank_account(account_id, **kwargs):
        return _run(_bank_repo.update(account_id, **kwargs))

    @staticmethod
    def delete_bank_account(account_id):
        return _run(_bank_repo.delete(account_id))

    # ── 银行对账 ──
    @staticmethod
    def get_bank_reconciliation(ledger_id, account_id, year, month):
        from database_v3 import get_bank_reconciliation
        return get_bank_reconciliation(ledger_id, account_id, year, month)

    @staticmethod
    def get_bank_statements(ledger_id, account_id):
        return _run(_bank_repo.get_statements(account_id))

    @staticmethod
    def get_unmatched(ledger_id, account_id):
        return _run(_bank_repo.get_unmatched_statements(account_id))

    @staticmethod
    def import_bank_statement(ledger_id, account_id, file_path):
        from database_v3 import import_bank_statement
        return import_bank_statement(ledger_id, account_id, file_path)

    @staticmethod
    def auto_match(ledger_id, account_id):
        from database_v3 import auto_match_bank_statement
        return auto_match_bank_statement(ledger_id, account_id)

    @staticmethod
    def match_statement(ledger_id, statement_id, voucher_no):
        from database_v3 import match_bank_statement
        return match_bank_statement(ledger_id, statement_id, voucher_no)

    @staticmethod
    def unmatch_statement(ledger_id, statement_id):
        from database_v3 import unmatch_bank_statement
        return unmatch_bank_statement(ledger_id, statement_id)

    @staticmethod
    def parse_bank_csv(file_path):
        from database_v3 import parse_bank_csv
        return parse_bank_csv(file_path)

    # ── 辅助核算 ──
    @staticmethod
    def create_auxiliary(ledger_id, name, category):
        return _run(_aux_repo.create(ledger_id=ledger_id, aux_type=category, code=name, name=name))

    @staticmethod
    def get_auxiliaries(ledger_id, category=None):
        return _run(_aux_repo.get_by_ledger(ledger_id, aux_type=category))

    @staticmethod
    def update_auxiliary(aux_id, **kwargs):
        return _run(_aux_repo.update(aux_id, **kwargs))

    @staticmethod
    def delete_auxiliary(aux_id):
        return _run(_aux_repo.delete(aux_id))

    @staticmethod
    def save_aux_mapping(ledger_id, aux_type, aux_id, voucher_no):
        from database_v3 import save_aux_mapping
        return save_aux_mapping(ledger_id, aux_type, aux_id, voucher_no)

    @staticmethod
    def get_aux_mapping(ledger_id, voucher_no):
        from database_v3 import get_aux_mapping
        return get_aux_mapping(ledger_id, voucher_no)

    @staticmethod
    def get_aux_balance(ledger_id, aux_type, aux_id, year, month):
        from database_v3 import get_aux_balance
        return get_aux_balance(ledger_id, aux_type, aux_id, year, month)

    @staticmethod
    def multi_aux_search(ledger_id, **kwargs):
        from database_v3 import multi_aux_search
        return multi_aux_search(ledger_id, **kwargs)
