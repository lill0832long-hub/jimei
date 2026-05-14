"""凭证服务层 — 使用 Repository 模式"""
import logging
from app.services._utils import run_async, to_dict
from app.repository.voucher_repository import VoucherRepository

logger = logging.getLogger(__name__)


_voucher_repo = VoucherRepository()


class VoucherService:
    """凭证管理"""

    @staticmethod
    def count(ledger_id, **filters):
        return run_async(_voucher_repo.count(ledger_id, **filters))

    @staticmethod
    def create(ledger_id, date_str, description, entries, status="posted", voucher_no=None, user_id=None, operator_name=None):
        """创建凭证 — 自动校验借贷平衡"""
        if entries and len(entries) > 0:
            total_debit = 0
            total_credit = 0
            for entry in entries:
                debit = float(entry.get("debit", 0) if isinstance(entry, dict) else getattr(entry, "debit", 0))
                credit = float(entry.get("credit", 0) if isinstance(entry, dict) else getattr(entry, "credit", 0))
                total_debit += debit
                total_credit += credit
            # 允许 0.01 的浮点误差
            if abs(total_debit - total_credit) > 0.01:
                logger.warning(
                    f"Voucher imbalance: debit={total_debit}, credit={total_credit}, "
                    f"diff={abs(total_debit - total_credit):.4f}"
                )
                raise ValueError(
                    f"借贷不平衡: 借方合计 {total_debit:.2f}, 贷方合计 {total_credit:.2f}"
                )
        else:
            raise ValueError("凭证明细不能为空")

        logger.info(f"Creating voucher for ledger={ledger_id}, date={date_str}, entries={len(entries)}")
        return run_async(_voucher_repo.create_with_entries(
            ledger_id=ledger_id, date=date_str, description=description,
            entries=entries, status=status, voucher_no=voucher_no,
        ))

    @staticmethod
    def update(voucher_no, date_str=None, description=None, entries=None, user_id=None, operator_name=None):
        """更新凭证 — 如修改明细则重新校验借贷平衡"""
        if entries and len(entries) > 0:
            total_debit = 0
            total_credit = 0
            for entry in entries:
                debit = float(entry.get("debit", 0) if isinstance(entry, dict) else getattr(entry, "debit", 0))
                credit = float(entry.get("credit", 0) if isinstance(entry, dict) else getattr(entry, "credit", 0))
                total_debit += debit
                total_credit += credit
            if abs(total_debit - total_credit) > 0.01:
                raise ValueError(
                    f"借贷不平衡: 借方合计 {total_debit:.2f}, 贷方合计 {total_credit:.2f}"
                )

        logger.info(f"Updating voucher {voucher_no}")
        return run_async(_voucher_repo.update(
            voucher_no, date=date_str, description=description,
            entries=entries,
        ))

    @staticmethod
    def post(ledger_id, voucher_no=None, user_id=None, operator_name=None):
        return run_async(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="posted",
            user_id=user_id, action="post", comment="",
        ))

    @staticmethod
    def submit_for_review(ledger_id, voucher_no, user_id=None, operator_name=None):
        return run_async(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="pending_review",
            user_id=user_id, action="submit", comment="",
        ))

    @staticmethod
    def approve(ledger_id, voucher_no, user_id=None, operator_name=None):
        """审核凭证 — 仅待审核状态的凭证可审核"""
        # 查询凭证当前状态
        voucher = to_dict(run_async(_voucher_repo.get_with_entries(ledger_id, voucher_no)))
        if not voucher:
            raise FileNotFoundError(f"凭证 {voucher_no} 不存在")

        current_status = voucher.get("status") if isinstance(voucher, dict) else getattr(voucher, "status", None)
        if current_status not in ("pending_review", "draft"):
            raise PermissionError(
                f"凭证当前状态为 '{current_status}'，只有待审核或草稿状态的凭证才能审核"
            )

        logger.info(f"Approving voucher {voucher_no} by user={user_id}")
        return run_async(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="approved",
            user_id=user_id, action="approve", comment="",
        ))

    @staticmethod
    def reject(ledger_id, voucher_no, reason="", user_id=None, operator_name=None):
        return run_async(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="rejected",
            user_id=user_id, action="reject", comment=reason,
        ))

    @staticmethod
    def reverse(voucher_no, reason="", user_id=None, operator_name=None):
        return run_async(_voucher_repo.update_status(
            voucher_no=voucher_no, new_status="reversed",
            user_id=user_id, action="reverse", comment=reason,
        ))

    @staticmethod
    def delete(voucher_no, ledger_id=None, user_id=None, operator_name=None):
        """删除凭证 — 仅草稿状态的凭证可删除"""
        # 查询凭证当前状态
        voucher = to_dict(run_async(_voucher_repo.get_with_entries(ledger_id, voucher_no))) if ledger_id else None
        if voucher:
            current_status = voucher.get("status") if isinstance(voucher, dict) else getattr(voucher, "status", None)
            if current_status and current_status != "draft":
                raise PermissionError(
                    f"凭证当前状态为 '{current_status}'，只有草稿状态的凭证才能删除"
                )

        logger.info(f"Deleting voucher {voucher_no} by user={user_id}")
        return run_async(_voucher_repo.delete(voucher_no))

    @staticmethod
    def get_all(ledger_id, year=None, month=None, status=None, limit=100):
        return to_dict(run_async(_voucher_repo.get_all(ledger_id, year=year, month=month, status=status, limit=limit)))

    @staticmethod
    def get_detail(ledger_id, voucher_no):
        return to_dict(run_async(_voucher_repo.get_with_entries(ledger_id, voucher_no)))

    @staticmethod
    def search(ledger_id, **kwargs):
        return to_dict(run_async(_voucher_repo.search(ledger_id, **kwargs)))

    @staticmethod
    def search_history(ledger_id, **kwargs):
        return run_async(_voucher_repo.search(ledger_id, **kwargs))

    @staticmethod
    def get_workflow_history(ledger_id, voucher_no):
        """获取凭证的操作历史时间线"""
        voucher = run_async(_voucher_repo.get_with_entries(ledger_id, voucher_no))
        if not voucher:
            return []
        voucher_id = voucher.id if hasattr(voucher, "id") else voucher.get("id")
        if not voucher_id:
            return []
        return to_dict(run_async(_voucher_repo.get_workflow_history(voucher_id)))

    # ── 凭证模板（暂保留旧实现，待后续迁移） ──
    @staticmethod
    def get_templates(ledger_id, include_inactive=False):
        from database.voucher import get_voucher_templates
        return get_voucher_templates(ledger_id, include_inactive)

    @staticmethod
    def create_template(ledger_id, name, description="", entries=None, category="general"):
        from database.voucher import create_voucher_template
        return create_voucher_template(ledger_id, name, description, entries, category)

    @staticmethod
    def update_template(template_id, ledger_id=None, **kwargs):
        from database.voucher import update_voucher_template
        return update_voucher_template(template_id, ledger_id, **kwargs)

    @staticmethod
    def delete_template(template_id, ledger_id=None):
        from database.voucher import delete_voucher_template
        return delete_voucher_template(template_id, ledger_id)

    @staticmethod
    def save_template(ledger_id, name, entries, description="", voucher_type="记"):
        from database.voucher import save_voucher_template
        return save_voucher_template(ledger_id, name, entries, description, voucher_type)

    # ── 计划凭证（暂保留旧实现） ──
    @staticmethod
    def get_scheduled(ledger_id):
        from database.voucher import get_scheduled_vouchers
        return get_scheduled_vouchers(ledger_id)

    @staticmethod
    def add_scheduled(ledger_id, **kwargs):
        from database.voucher import add_scheduled_voucher
        return add_scheduled_voucher(ledger_id, **kwargs)

    @staticmethod
    def run_scheduled(scheduled_id):
        from database.voucher import run_scheduled_voucher
        return run_scheduled_voucher(scheduled_id)

    # ── 辅助方法（暂保留旧实现） ──
    @staticmethod
    def import_from_excel(ledger_id, file_path):
        from database.voucher import import_vouchers_from_excel
        return import_vouchers_from_excel(ledger_id, file_path)

    @staticmethod
    def generate_from_text(ledger_id, text):
        from database.voucher import generate_voucher_from_text
        return generate_voucher_from_text(ledger_id, text)

    @staticmethod
    def search_by_auxiliary(ledger_id, aux_filters):
        """多维度辅助核算查询"""
        from database.auxiliary import multi_aux_search
        return multi_aux_search(ledger_id, aux_filters)