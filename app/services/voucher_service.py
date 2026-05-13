"""凭证服务层 — 使用 Repository 模式"""
import asyncio
from app.repository.voucher_repository import VoucherRepository

_voucher_repo = VoucherRepository()


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


class VoucherService:
    """凭证管理"""

    @staticmethod
    def count(ledger_id, **filters):
        return _run(_voucher_repo.count(ledger_id, **filters))

    @staticmethod
    def create(ledger_id, date_str, description, entries, status="posted", voucher_no=None, user_id=None, operator_name=None):
        return _run(_voucher_repo.create_with_entries(
            ledger_id=ledger_id, date=date_str, description=description,
            entries=entries, status=status, voucher_no=voucher_no,
        ))

    @staticmethod
    def update(voucher_no, date_str=None, description=None, entries=None, user_id=None, operator_name=None):
        return _run(_voucher_repo.update(
            voucher_no, date=date_str, description=description,
            entries=entries,
        ))

    @staticmethod
    def post(ledger_id, voucher_no=None, user_id=None, operator_name=None):
        return _run(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="posted",
            user_id=user_id, action="post", comment="",
        ))

    @staticmethod
    def submit_for_review(ledger_id, voucher_no, user_id=None, operator_name=None):
        return _run(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="pending_review",
            user_id=user_id, action="submit", comment="",
        ))

    @staticmethod
    def approve(ledger_id, voucher_no, user_id=None, operator_name=None):
        return _run(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="approved",
            user_id=user_id, action="approve", comment="",
        ))

    @staticmethod
    def reject(ledger_id, voucher_no, reason="", user_id=None, operator_name=None):
        return _run(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="rejected",
            user_id=user_id, action="reject", comment=reason,
        ))

    @staticmethod
    def reverse(voucher_no, reason="", user_id=None, operator_name=None):
        return _run(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="reversed",
            user_id=user_id, action="reverse", comment=reason,
        ))

    @staticmethod
    def delete(voucher_no, ledger_id=None, user_id=None, operator_name=None):
        return _run(_voucher_repo.delete(voucher_no))

    @staticmethod
    def get_all(ledger_id, year=None, month=None, status=None, limit=100):
        return _to_dict(_run(_voucher_repo.get_all(ledger_id, year=year, month=month, status=status, limit=limit)))

    @staticmethod
    def get_detail(ledger_id, voucher_no):
        return _to_dict(_run(_voucher_repo.get_with_entries(ledger_id, voucher_no)))

    @staticmethod
    def search(ledger_id, **kwargs):
        return _to_dict(_run(_voucher_repo.search(ledger_id, **kwargs)))

    @staticmethod
    def search_history(ledger_id, **kwargs):
        return _run(_voucher_repo.search(ledger_id, **kwargs))

    # ── 凭证模板（暂保留旧实现，待后续迁移） ──
    @staticmethod
    def get_templates(ledger_id, include_inactive=False):
        # TODO: migrate to repository pattern
        from database.voucher import get_voucher_templates
        return get_voucher_templates(ledger_id, include_inactive)

    @staticmethod
    def create_template(ledger_id, name, description="", entries=None, category="general"):
        # TODO: migrate to repository pattern
        from database.voucher import create_voucher_template
        return create_voucher_template(ledger_id, name, description, entries, category)

    @staticmethod
    def update_template(template_id, ledger_id=None, **kwargs):
        # TODO: migrate to repository pattern
        from database.voucher import update_voucher_template
        return update_voucher_template(template_id, ledger_id, **kwargs)

    @staticmethod
    def delete_template(template_id, ledger_id=None):
        # TODO: migrate to repository pattern
        from database.voucher import delete_voucher_template
        return delete_voucher_template(template_id, ledger_id)

    @staticmethod
    def save_template(ledger_id, name, entries, description="", voucher_type="记"):
        # TODO: migrate to repository pattern
        from database.voucher import save_voucher_template
        return save_voucher_template(ledger_id, name, entries, description, voucher_type)

    # ── 计划凭证（暂保留旧实现） ──
    @staticmethod
    def get_scheduled(ledger_id):
        # TODO: migrate to repository pattern
        from database.voucher import get_scheduled_vouchers
        return get_scheduled_vouchers(ledger_id)

    @staticmethod
    def add_scheduled(ledger_id, **kwargs):
        # TODO: migrate to repository pattern
        from database.voucher import add_scheduled_voucher
        return add_scheduled_voucher(ledger_id, **kwargs)

    @staticmethod
    def run_scheduled(scheduled_id):
        # TODO: migrate to repository pattern
        from database.voucher import run_scheduled_voucher
        return run_scheduled_voucher(scheduled_id)

    # ── 辅助方法（暂保留旧实现） ──
    @staticmethod
    def import_from_excel(ledger_id, file_path):
        # TODO: migrate to repository pattern
        from database.voucher import import_vouchers_from_excel
        return import_vouchers_from_excel(ledger_id, file_path)

    @staticmethod
    def generate_from_text(ledger_id, text):
        # TODO: migrate to repository pattern
        from database.voucher import generate_voucher_from_text
        return generate_voucher_from_text(ledger_id, text)

    @staticmethod
    def search_by_auxiliary(ledger_id, aux_filters):
        """多维度辅助核算查询"""
        # TODO: migrate to repository pattern
        from database.auxiliary import multi_aux_search
        return multi_aux_search(ledger_id, aux_filters)
