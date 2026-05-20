"""全局状态"""
from datetime import datetime
from app.services import LedgerService

def _get_ledgers():
    return LedgerService.get_all()

def _get_ledger(ledger_id):
    return LedgerService.get_by_id(ledger_id)

class State:
    current_page = "dashboard"  # 默认首页
    selected_ledger_id = None
    selected_year = datetime.now().year
    selected_month = datetime.now().month
    selected_voucher_no = None
    main_content = None
    sidebar_content = None  # sidebar 容器（兼容旧引用）
    current_user = None
    sidebar_collapsed = False
    sidebar_group_expanded = None  # 懒加载：首次 render_sidebar() 时初始化为 dict
    _sidebar_container = None  # sidebar 容器引用（避免重复创建）
    compare_months = 6  # 默认对比6个月
    show_onboarding = True  # 新用户引导面板
    onboarding_step = 0  # 当前引导步骤 (0=未开始, 1-5=引导中, 6=已完成)
    _header_css_added = False  # header选择框CSS是否已注入
    _dashboard_cache = None  # Dashboard 数据缓存 (bs, inc, recent_vouchers)
    _dashboard_cache_key = None  # 缓存键 (lid, year, month)
    dismissed_tips = set()  # 已关闭的功能提示集合
    show_shortcut_help = False  # 快捷键帮助面板显示状态
    recent_pages = []  # 最近访问的页面（最多3个）
    voucher_status_filter = "all"  # 凭证状态筛选：all/draft/pending_review/posted/reversed

    # ── Tab 系统 ──
    _tabs = None  # [{"key": "dashboard", "label": "仪表盘"}]
    _active_tab_idx = 0  # 当前激活 tab 索引
    _tab_bar_container = None  # tab 栏容器引用
    _tab_contents = None  # tab 内容容器引用（ui.column）
    # 页面 key -> 中文标签映射（与 sidebar 菜单一致）
    _tab_labels = {
        "dashboard": "仪表盘",
        "journal": "记账凭证",
        "voucher_detail": "凭证详情",
        "accounts": "科目余额表",
        "balance_sheet": "资产负债表",
        "trial_balance": "试算平衡表",
        "income_statement": "利润表",
        "close_period": "期末结转",
        "charts": "图表分析",
        "compare": "对比分析",
        "ai_assistant": "AI助手",
        "import": "批量导入",
        "export": "数据导出",
        "fixed_assets": "固定资产",
        "cashier": "出纳管理",
        "auxiliary": "辅助核算",
        "settings": "系统设置",
        "about": "关于",
        "tax": "增值税管理",
        "cash_flow": "现金流",
        "budget": "预算管理",
        "scheduled_vouchers": "定时凭证",
        "invoices": "发票管理",
        "multi_currency": "多币种",
        "audit_log": "审计日志",
        "setup_wizard": "设置向导",
        "voucher_template": "凭证模板",
        "account_ledger": "科目明细账",
        "general_ledger": "总分类账",
        "bank_reconciliation": "银行对账",
        "cash_flow_statement": "现金流量表",
        "reports_center": "报表中心",
        "journal_form": "凭证录入",
    }


    # ── Tab 管理 ──

    @property
    def tabs(self):
        if self._tabs is None:
            self._tabs = [{"key": "dashboard", "label": self._tab_labels.get("dashboard", "仪表盘")}]
        return self._tabs

    @tabs.setter
    def tabs(self, value):
        self._tabs = value

    @property
    def active_tab_idx(self):
        return self._active_tab_idx

    @active_tab_idx.setter
    def active_tab_idx(self, value):
        self._active_tab_idx = value

    @property
    def tab_bar_container(self):
        return self._tab_bar_container

    @tab_bar_container.setter
    def tab_bar_container(self, value):
        self._tab_bar_container = value

    @property
    def tab_contents(self):
        return self._tab_contents

    @tab_contents.setter
    def tab_contents(self, value):
        self._tab_contents = value

    def get_tab_label(self, page_key):
        return self._tab_labels.get(page_key, page_key)

    @property
    def ledger(self):
        if self.selected_ledger_id:
            return _get_ledger(self.selected_ledger_id)
        ledgers = _get_ledgers()
        if ledgers and not self.selected_ledger_id:
            self.selected_ledger_id = ledgers[0]["id"]
        return ledgers[0] if ledgers else None

state = State()


# ── 错误提示体系 ──
ERROR_MESSAGES = {
    "UNBALANCED": "借贷金额不平衡，请检查分录",
    "ACCOUNT_NOT_FOUND": "科目编码不存在，请检查输入",
    "ZERO_AMOUNT": "金额不能为零",
    "DUPLICATE_VOUCHER": "凭证编号已存在",
    "PERIOD_CLOSED": "当前会计期间已结账，无法修改",
    "SESSION_EXPIRED": "登录已过期，请重新登录",
    "PERMISSION_DENIED": "您没有权限执行此操作",
    "REQUIRED_FIELD": "请填写必填项",
    "SAVE_SUCCESS": "保存成功",
    "DELETE_SUCCESS": "删除成功",
    "AUDIT_SUCCESS": "审核成功",
}
