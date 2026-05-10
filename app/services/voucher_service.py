"""凭证服务层 — 封装 database_v3 的凭证/模板/计划凭证相关操作"""
from database_v3 import (
    create_voucher, update_voucher, post_voucher, submit_for_review,
    approve_voucher, reject_voucher, reverse_voucher, delete_voucher,
    get_vouchers, get_voucher_detail, search_vouchers, search_voucher_history_v2,
    get_voucher_templates, create_voucher_template, update_voucher_template,
    delete_voucher_template, save_voucher_template,
    get_scheduled_vouchers, add_scheduled_voucher, run_scheduled_voucher,
    check_budget_exceeded, get_avg_amount_for_account,
    import_vouchers_from_excel, generate_voucher_from_text,
)


class VoucherService:
    """凭证管理"""

    @staticmethod
    def create(ledger_id, date_str, description, entries, status="posted", voucher_no=None, user_id=None, operator_name=None):
        return create_voucher(ledger_id, date_str, description, entries, status, voucher_no, user_id, operator_name)

    @staticmethod
    def update(voucher_no, date_str=None, description=None, entries=None, user_id=None, operator_name=None):
        return update_voucher(voucher_no, date_str, description, entries, user_id, operator_name)

    @staticmethod
    def post(ledger_id, voucher_no=None, user_id=None, operator_name=None):
        return post_voucher(ledger_id, voucher_no, user_id, operator_name)

    @staticmethod
    def submit_for_review(ledger_id, voucher_no, user_id=None, operator_name=None):
        return submit_for_review(ledger_id, voucher_no, user_id, operator_name)

    @staticmethod
    def approve(ledger_id, voucher_no, user_id=None, operator_name=None):
        return approve_voucher(ledger_id, voucher_no, user_id, operator_name)

    @staticmethod
    def reject(ledger_id, voucher_no, reason="", user_id=None, operator_name=None):
        return reject_voucher(ledger_id, voucher_no, reason, user_id, operator_name)

    @staticmethod
    def reverse(voucher_no, reason="", user_id=None, operator_name=None):
        return reverse_voucher(voucher_no, reason, user_id, operator_name)

    @staticmethod
    def delete(voucher_no, ledger_id=None, user_id=None, operator_name=None):
        return delete_voucher(voucher_no, ledger_id, user_id, operator_name)

    @staticmethod
    def get_all(ledger_id, year=None, month=None, status=None, limit=100):
        return get_vouchers(ledger_id, year, month, status, limit)

    @staticmethod
    def get_detail(ledger_id, voucher_no):
        return get_voucher_detail(ledger_id, voucher_no)

    @staticmethod
    def search(ledger_id, **kwargs):
        return search_vouchers(ledger_id, **kwargs)

    @staticmethod
    def search_history(ledger_id, **kwargs):
        return search_voucher_history_v2(ledger_id, **kwargs)

    # ── 凭证模板 ──
    @staticmethod
    def get_templates(ledger_id):
        return get_voucher_templates(ledger_id)

    @staticmethod
    def create_template(ledger_id, name, entries):
        return create_voucher_template(ledger_id, name, entries)

    @staticmethod
    def update_template(template_id, **kwargs):
        return update_voucher_template(template_id, **kwargs)

    @staticmethod
    def delete_template(template_id):
        return delete_voucher_template(template_id)

    @staticmethod
    def save_template(ledger_id, name, entries):
        return save_voucher_template(ledger_id, name, entries)

    # ── 计划凭证 ──
    @staticmethod
    def get_scheduled(ledger_id):
        return get_scheduled_vouchers(ledger_id)

    @staticmethod
    def add_scheduled(ledger_id, **kwargs):
        return add_scheduled_voucher(ledger_id, **kwargs)

    @staticmethod
    def run_scheduled(scheduled_id):
        return run_scheduled_voucher(scheduled_id)

    # ── 辅助方法 ──
    @staticmethod
    def check_budget_exceeded(ledger_id, account_code, amount):
        return check_budget_exceeded(ledger_id, account_code, amount)

    @staticmethod
    def get_avg_amount(ledger_id, account_code):
        return get_avg_amount_for_account(ledger_id, account_code)

    @staticmethod
    def import_from_excel(ledger_id, file_path):
        return import_vouchers_from_excel(ledger_id, file_path)

    @staticmethod
    def generate_from_text(ledger_id, text):
        return generate_voucher_from_text(ledger_id, text)
