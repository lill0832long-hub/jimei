"""配置常量 — 从 app_v3.py 提取"""
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "finance.db")

# ── 页面列表 ──
PAGES = [
    "dashboard", "journal", "voucher_detail", "accounts",
    "balance_sheet", "income_statement", "close_period",
    "charts", "compare", "ai_assistant",
    "import", "export", "settings",
    "fixed_assets", "cashier", "auxiliary",
]

# ── 错误消息 ──
ERROR_MESSAGES = {
    "required": "此项为必填项",
    "invalid_amount": "请输入有效金额",
    "invalid_date": "日期格式不正确",
    "unbalanced": "借贷不平衡，请检查",
    "no_ledger": "请先创建账套",
    "voucher_not_found": "凭证不存在",
    "permission_denied": "权限不足",
    "delete_confirm": "确认删除？此操作不可撤销",
    "close_period_warning": "期末结转后不可修改当期凭证",
    "import_error": "导入失败，请检查文件格式",
}

# ── 财务知识库 ──
FINANCIAL_KNOWLEDGE = {
    "资产负债表": "反映企业在某一特定日期的财务状况的会计报表，遵循 资产=负债+所有者权益",
    "利润表": "反映企业在一定会计期间经营成果的报表，遵循 收入-费用=利润",
    "现金流量表": "反映企业在一定会计期间现金和现金等价物流入和流出的报表",
    "借贷记账法": "以借、贷作为记账符号，遵循有借必有贷，借贷必相等的记账规则",
    "权责发生制": "以权利和责任的发生来决定收入和费用归属期的原则",
    "固定资产折旧": "固定资产在使用过程中逐渐损耗而转移到成本费用中的价值，常用方法有直线法、双倍余额递减法、年数总和法",
    "增值税": "对商品生产、流通、劳务服务中多个环节的新增价值或商品的附加值征收的一种流转税",
    "期末结转": "会计期末将损益类科目余额转入本年利润科目的过程",
    "银行余额调节表": "用于核对银行对账单余额与企业账面余额差异的调节表",
    "辅助核算": "在科目核算基础上附加的维度核算，如客户、供应商、部门、项目等",
}

# ── 侧边栏分组 ──
SIDEBAR_GROUPS = {
    "日常操作": ["dashboard", "journal", "accounts"],
    "期末处理": ["close_period", "balance_sheet", "income_statement"],
    "分析工具": ["charts", "compare", "ai_assistant"],
    "资产管理": ["fixed_assets", "cashier"],
    "系统管理": ["import", "export", "settings"],
}

# ── 页面名称映射 ──
PAGE_NAMES = {
    "dashboard": "仪表盘",
    "journal": "记账凭证",
    "voucher_detail": "凭证详情",
    "accounts": "科目余额表",
    "balance_sheet": "资产负债表",
    "income_statement": "利润表",
    "close_period": "期末结转",
    "charts": "图表分析",
    "compare": "对比分析",
    "ai_assistant": "AI助手",
    "import": "批量导入",
    "export": "数据导出",
    "settings": "系统设置",
    "fixed_assets": "固定资产",
    "cashier": "出纳管理",
    "auxiliary": "辅助核算",
}
