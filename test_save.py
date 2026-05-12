"""测试凭证保存流程"""
import json
import sys
sys.path.insert(0, r'e:\ClaudeCode\my-project')

from app.services import AccountService, VoucherService, LedgerService
from app.components.state import state

# 获取账套
ledgers = LedgerService.get_all()
print(f"账套列表: {[(l['id'], l['name']) for l in ledgers]}")

if not ledgers:
    print("没有账套，无法测试")
    exit(1)

ledger_id = ledgers[0]['id']
print(f"使用账套: {ledger_id} ({ledgers[0]['name']})")

# 模拟 state
state.selected_ledger_id = ledger_id
state.selected_year = 2026
state.selected_month = 5

# 获取科目
acct_data = AccountService.get_all()
print(f"\n科目数量: {len(acct_data)}")

# 构造测试分录
test_entries_raw = [
    {"summary": "测试摘要", "acct_code": "1002", "debit": 10000, "credit": 0},
    {"summary": "测试摘要", "acct_code": "5001", "debit": 0, "credit": 10000},
]

# 模拟 _collect_entries 的处理逻辑
acct_map = {a["code"]: a for a in acct_data}
entries = []
for e in test_entries_raw:
    dr = float(e.get("debit") or 0)
    cr = float(e.get("credit") or 0)
    if dr == 0 and cr == 0:
        continue
    code = e.get("acct_code", "")
    if not code:
        continue
    name = acct_map.get(code, {}).get("name", code) if isinstance(acct_map.get(code), dict) else code
    entries.append({"account_code": code, "account_name": name, "debit": dr, "credit": cr, "summary": e.get("summary", "")})

print(f"\n处理后的分录:")
for e in entries:
    print(f"  {e['account_code']} {e['account_name']} 借:{e['debit']} 贷:{e['credit']}")

total_debit = sum(e["debit"] for e in entries)
total_credit = sum(e["credit"] for e in entries)
print(f"\n借方合计: {total_debit}")
print(f"贷方合计: {total_credit}")
print(f"平衡: {abs(total_debit - total_credit) <= 0.01}")

# 尝试保存
print("\n尝试保存凭证...")
try:
    vn = VoucherService.create(
        ledger_id=ledger_id,
        date_str="2026-05-11",
        description="测试凭证",
        entries=entries,
        status="draft"
    )
    print(f"保存成功！凭证号: {vn}")
except Exception as ex:
    print(f"保存失败: {ex}")
    import traceback
    traceback.print_exc()
