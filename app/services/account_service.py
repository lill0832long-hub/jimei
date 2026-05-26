"""科目服务层 — 使用 Repository 模式"""
from app.services._utils import run_async, to_dict
import logging
from app.repository.account_repository import AccountRepository, BankAccountRepository, AuxiliaryRepository
from app.repository.ledger_repository import LedgerRepository
from app.repository.classification_repository import ClassificationRepository

logger = logging.getLogger(__name__)

_account_repo = AccountRepository()
_bank_repo = BankAccountRepository()
_aux_repo = AuxiliaryRepository()
_ledger_repo = LedgerRepository()
_classification_repo = ClassificationRepository()


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
        account = to_dict(run_async(_account_repo.get_by_id(account_id))) if hasattr(_account_repo, "get_by_id") else None
        if account:
            account_code = account.get("code")
            if account_code:
                count = run_async(_account_repo.count_journal_entries(account_code))
                if count > 0:
                    raise PermissionError(
                        f"科目 '{account_code}' 已被 {count} 条凭证明细引用，无法删除"
                    )

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
        return run_async(_account_repo.import_from_template(ledger_id, template_name))

    @staticmethod
    def get_suggestions(ledger_id, account_code):
        return to_dict(run_async(_account_repo.get_suggestions(ledger_id, account_code)))

    @staticmethod
    def get_avg_amount(ledger_id, account_code):
        return run_async(_account_repo.get_avg_amount(ledger_id, account_code))

    @staticmethod
    def get_ledger(ledger_id, account_code, year=None, month=None):
        """明细账 — 使用 Repository 模式"""
        return run_async(_ledger_repo.get_account_ledger(ledger_id, account_code, year, month))

    @staticmethod
    def get_general_ledger(ledger_id, account_code=None, year=None, month=None):
        """总账 — 使用 Repository 模式"""
        return run_async(_ledger_repo.get_general_ledger(ledger_id, account_code=account_code, year=year, month=month))

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
        return run_async(_bank_repo.get_reconciliation(account_id))

    @staticmethod
    def get_bank_statements(ledger_id, account_id):
        return to_dict(run_async(_bank_repo.get_statements(account_id)))

    @staticmethod
    def get_unmatched(ledger_id, account_id):
        return to_dict(run_async(_bank_repo.get_unmatched_statements(account_id)))

    @staticmethod
    def import_bank_statement(ledger_id, account_id, file_path):
        """银行对账单导入 — 涉及文件解析，保留旧实现"""
        from database.account import import_bank_statement
        return import_bank_statement(account_id, file_path)

    @staticmethod
    def auto_match(ledger_id, account_id):
        return run_async(_bank_repo.auto_match(account_id))

    @staticmethod
    def match_statement(ledger_id, statement_id, voucher_no):
        return to_dict(run_async(_bank_repo.match_statement(statement_id, voucher_no=voucher_no)))

    @staticmethod
    def unmatch_statement(ledger_id, statement_id):
        return to_dict(run_async(_bank_repo.unmatch_statement(statement_id)))

    @staticmethod
    def parse_bank_csv(file_content):
        """银行CSV解析 — 使用 Repository 模式"""
        return ClassificationRepository.parse_bank_csv(file_content)

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
    def save_aux_mapping(ledger_id, aux_type, aux_id, voucher_no, entry_id=None, aux_name=None):
        """辅助核算映射 — 使用 Repository 模式"""
        return run_async(_aux_repo.save_aux_mapping(
            entry_id=entry_id, aux_type=aux_type, aux_id=aux_id, aux_name=aux_name))

    @staticmethod
    def get_aux_mapping(ledger_id, voucher_no, entry_id=None):
        """辅助核算映射查询 — 使用 Repository 模式"""
        return run_async(_aux_repo.get_aux_mapping(entry_id=entry_id))

    @staticmethod
    def get_aux_balance(ledger_id, aux_type, aux_id, year, month):
        """辅助核算余额 — 使用 Repository 模式"""
        return run_async(_aux_repo.get_aux_balance(ledger_id, aux_type, year=year, month=month))

    @staticmethod
    def multi_aux_search(ledger_id, **kwargs):
        """多维度辅助核算查询 — 使用 Repository 模式"""
        return run_async(_aux_repo.multi_aux_search(
            ledger_id, kwargs.get("aux_filters"), year=kwargs.get("year"), month=kwargs.get("month")
        ))