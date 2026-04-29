"""全局状态"""
from datetime import datetime
from database_v3 import get_ledgers, get_ledger

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


    @property
    def ledger(self):
        if self.selected_ledger_id:
            return get_ledger(self.selected_ledger_id)
        ledgers = get_ledgers()
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
