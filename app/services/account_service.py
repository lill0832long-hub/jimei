"""科目服务层 — 封装 database_v3 的科目/银行账号/辅助核算相关操作"""
from database_v3 import (
    get_accounts, add_account, search_accounts_by_kw,
    get_default_accounts, import_accounts_from_template,
    get_account_suggestions, get_avg_amount_for_account,
    create_bank_account, get_bank_accounts, update_bank_account, delete_bank_account,
    import_bank_statement, auto_match_bank_statement, get_bank_reconciliation,
    get_bank_statements_list, match_bank_statement, unmatch_bank_statement,
    get_unmatched_items, parse_bank_csv,
    create_auxiliary, get_auxiliaries, update_auxiliary, delete_auxiliary,
    save_aux_mapping, get_aux_mapping, get_aux_balance, multi_aux_search,
    get_account_ledger,
)


class AccountService:
    """科目与银行账号管理"""

    # ── 科目 ──
    @staticmethod
    def get_all(ledger_id=None, active_only=True):
        return get_accounts(ledger_id, active_only)

    @staticmethod
    def add(ledger_id, code, name, category, **kwargs):
        return add_account(ledger_id, code, name, category, **kwargs)

    @staticmethod
    def search(keyword, limit=10):
        return search_accounts_by_kw(keyword, limit)

    @staticmethod
    def get_defaults():
        return get_default_accounts()

    @staticmethod
    def import_from_template(ledger_id, template_name):
        return import_accounts_from_template(ledger_id, template_name)

    @staticmethod
    def get_suggestions(ledger_id, account_code):
        return get_account_suggestions(ledger_id, account_code)

    @staticmethod
    def get_avg_amount(ledger_id, account_code):
        return get_avg_amount_for_account(ledger_id, account_code)

    @staticmethod
    def get_ledger(ledger_id, account_code, year=None, month=None):
        return get_account_ledger(ledger_id, account_code, year, month)

    # ── 银行账号 ──
    @staticmethod
    def create_bank_account(ledger_id, **kwargs):
        return create_bank_account(ledger_id, **kwargs)

    @staticmethod
    def get_bank_accounts(ledger_id):
        return get_bank_accounts(ledger_id)

    @staticmethod
    def update_bank_account(account_id, **kwargs):
        return update_bank_account(account_id, **kwargs)

    @staticmethod
    def delete_bank_account(account_id):
        return delete_bank_account(account_id)

    # ── 银行对账 ──
    @staticmethod
    def get_bank_reconciliation(ledger_id, account_id, year, month):
        return get_bank_reconciliation(ledger_id, account_id, year, month)

    @staticmethod
    def get_bank_statements(ledger_id, account_id):
        return get_bank_statements_list(ledger_id, account_id)

    @staticmethod
    def get_unmatched(ledger_id, account_id):
        return get_unmatched_items(ledger_id, account_id)

    @staticmethod
    def import_bank_statement(ledger_id, account_id, file_path):
        return import_bank_statement(ledger_id, account_id, file_path)

    @staticmethod
    def auto_match(ledger_id, account_id):
        return auto_match_bank_statement(ledger_id, account_id)

    @staticmethod
    def match_statement(ledger_id, statement_id, voucher_no):
        return match_bank_statement(ledger_id, statement_id, voucher_no)

    @staticmethod
    def unmatch_statement(ledger_id, statement_id):
        return unmatch_bank_statement(ledger_id, statement_id)

    @staticmethod
    def parse_bank_csv(file_path):
        return parse_bank_csv(file_path)

    # ── 辅助核算 ──
    @staticmethod
    def create_auxiliary(ledger_id, name, category):
        return create_auxiliary(ledger_id, name, category)

    @staticmethod
    def get_auxiliaries(ledger_id, category=None):
        return get_auxiliaries(ledger_id, category)

    @staticmethod
    def update_auxiliary(aux_id, **kwargs):
        return update_auxiliary(aux_id, **kwargs)

    @staticmethod
    def delete_auxiliary(aux_id):
        return delete_auxiliary(aux_id)

    @staticmethod
    def save_aux_mapping(ledger_id, aux_type, aux_id, voucher_no):
        return save_aux_mapping(ledger_id, aux_type, aux_id, voucher_no)

    @staticmethod
    def get_aux_mapping(ledger_id, voucher_no):
        return get_aux_mapping(ledger_id, voucher_no)

    @staticmethod
    def get_aux_balance(ledger_id, aux_type, aux_id, year, month):
        return get_aux_balance(ledger_id, aux_type, aux_id, year, month)

    @staticmethod
    def multi_aux_search(ledger_id, **kwargs):
        return multi_aux_search(ledger_id, **kwargs)
