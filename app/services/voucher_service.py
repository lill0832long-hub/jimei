"""凭证服务层 — 封装 database_v3 的凭证相关操作"""
from database_v3 import (
    create_voucher, update_voucher, post_voucher, submit_for_review,
    approve_voucher, reject_voucher, reverse_voucher, delete_voucher,
    get_vouchers, get_voucher_detail, search_vouchers, search_voucher_history_v2
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
