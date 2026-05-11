"""Database module: voucher domain"""

from .connection import get_conn, transaction, DB_PATH, clear_query_cache
from .audit import add_audit_log

def create_voucher(ledger_id, date_str, description, entries, status="posted", voucher_no=None, user_id=None, operator_name=None):
    """
    创建记账凭证（支持多状态）
    entries: [{"account_code": "1002", "debit": 10000, "credit": 0, "summary": ""}, ...]
    account_name 会自动从 accounts 表查找填充
    voucher_no: 自定义凭证编号，为 None 时自动生成
    """
    conn = get_conn()
    try:
        with transaction(conn):
            if not voucher_no:
                prefix = f"PZ{date_str.replace('-', '')}"
                count = conn.execute("SELECT COUNT(*) FROM vouchers WHERE voucher_no LIKE ? AND ledger_id = ?",
                                     (prefix + "%", ledger_id)).fetchone()[0]
                voucher_no = f"{prefix}{count+1:04d}"

            total_debit = sum(e.get("debit", 0) for e in entries)
            total_credit = sum(e.get("credit", 0) for e in entries)

            if abs(total_debit - total_credit) > 0.01:
                raise ValueError(f"借贷不平衡：借方 {total_debit} ≠ 贷方 {total_credit}")

            cur = conn.execute(
                "INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status, currency) VALUES (?,?,?,?,?,?,?,?)",
                (ledger_id, voucher_no, date_str, description, total_debit, total_credit, status, "CNY")
            )
            voucher_id = cur.lastrowid

            for e in entries:
                account_code = e.get("account_code", "")
                account_name = e.get("account_name")
                if not account_name:
                    row = conn.execute("SELECT name FROM accounts WHERE code = ?", (account_code,)).fetchone()
                    account_name = row["name"] if row else account_code
                conn.execute(
                    "INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary, foreign_currency, foreign_amount, exchange_rate) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (ledger_id, voucher_id, account_code, account_name, e.get("debit", 0), e.get("credit", 0), e.get("summary", ""),
                     e.get("foreign_currency", ""), e.get("foreign_amount", 0), e.get("exchange_rate", 1))
                )

            # 审计日志（在事务内，保证原子性）
            add_audit_log(
                ledger_id=ledger_id,
                action="create_voucher",
                detail=f"创建凭证 {voucher_no}",
                voucher_id=voucher_id,
                module="voucher",
                target_table="vouchers",
                target_id=voucher_id,
                user_id=user_id,
                operator_name=operator_name,
                remark=f"凭证号:{voucher_no}",
                conn=conn,
            )
        return voucher_no
    finally:
        conn.close()

def update_voucher(voucher_no, date_str=None, description=None, entries=None, user_id=None, operator_name=None):
    """更新凭证（仅限 draft 状态）"""
    conn = get_conn()
    try:
        with transaction(conn):
            v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
            if not v:
                raise ValueError("凭证不存在")
            if v["status"] != "draft":
                raise ValueError(f"只能编辑草稿状态的凭证（当前状态：{v['status']}）")

            if date_str:
                conn.execute("UPDATE vouchers SET date = ? WHERE id = ?", (date_str, v["id"]))
            if description:
                conn.execute("UPDATE vouchers SET description = ? WHERE id = ?", (description, v["id"]))
            if entries:
                conn.execute("DELETE FROM journal_entries WHERE voucher_id = ?", (v["id"],))
                total_debit = sum(e.get("debit", 0) for e in entries)
                total_credit = sum(e.get("credit", 0) for e in entries)
                if abs(total_debit - total_credit) > 0.01:
                    raise ValueError("借贷不平衡")
                for e in entries:
                    account_code = e.get("account_code", "")
                    account_name = e.get("account_name")
                    if not account_name:
                        row = conn.execute("SELECT name FROM accounts WHERE code = ?", (account_code,)).fetchone()
                        account_name = row["name"] if row else account_code
                    conn.execute(
                        "INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary, foreign_currency, foreign_amount, exchange_rate) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (v["ledger_id"], v["id"], account_code, account_name, e.get("debit", 0), e.get("credit", 0), e.get("summary", ""),
                         e.get("foreign_currency", ""), e.get("foreign_amount", 0), e.get("exchange_rate", 1))
                    )
                conn.execute("UPDATE vouchers SET total_debit = ?, total_credit = ? WHERE id = ?", (total_debit, total_credit, v["id"]))

            conn.execute("UPDATE vouchers SET updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
            add_audit_log(
                ledger_id=v["ledger_id"],
                action="update_voucher",
                detail=f"更新凭证 {voucher_no}",
                voucher_id=v["id"],
                module="voucher",
                target_table="vouchers",
                target_id=v["id"],
                user_id=user_id,
                operator_name=operator_name,
                remark=f"凭证号:{voucher_no}",
                conn=conn,
            )
    finally:
        conn.close()

def post_voucher(ledger_id, voucher_no=None, user_id=None, operator_name=None):
    """审核并过账（验证凭证属于指定账套）
    兼容两种调用方式：
    - post_voucher(ledger_id, voucher_no)  # 显式指定账套
    - post_voucher(voucher_no)             # 仅凭证号（从凭证中推断账套）
    """
    # 处理向后兼容：如果只传一个参数，则视为 voucher_no
    if voucher_no is None:
        voucher_no = ledger_id
        ledger_id = None

    conn = get_conn()
    if ledger_id is not None:
        v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    else:
        v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
    if not v:
        conn.close()
        raise ValueError("凭证不存在或不属于该账套")
    if v["status"] == "posted":
        conn.close()
        return  # 已过账
    conn.execute("UPDATE vouchers SET status = 'posted', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=v["ledger_id"],
        action="post_voucher",
        detail=f"过账凭证 {voucher_no}",
        voucher_id=v["id"],
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        remark=f"凭证号:{voucher_no}",
        conn=conn,
    )
    conn.commit()
    conn.close()
    clear_query_cache()

def approve_voucher(ledger_id, voucher_no, user_id=None, operator_name=None):
    """approve_voucher: pending_review -> posted"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    if not v:
        conn.close()
        raise ValueError("voucher not found")
    if v["status"] != "pending_review":
        conn.close()
        raise ValueError("only pending_review can approve")
    conn.execute("UPDATE vouchers SET status = 'posted', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=ledger_id,
        action="approve_voucher",
        detail="审核通过 " + voucher_no,
        voucher_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        remark=f"凭证号:{voucher_no}",
        conn=conn,
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    add_workflow_log(ledger_id, v["id"], "approve", "pending_review", "posted", user_id)

def reject_voucher(ledger_id, voucher_no, reason="", user_id=None, operator_name=None):
    """reject_voucher: pending_review -> draft"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    if not v:
        conn.close()
        raise ValueError("voucher not found")
    if v["status"] != "pending_review":
        conn.close()
        raise ValueError("only pending_review can reject")
    conn.execute("UPDATE vouchers SET status = 'draft', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=ledger_id,
        action="reject_voucher",
        detail="驳回 " + voucher_no + " 原因:" + reason,
        voucher_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        remark=reason,
        conn=conn,
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    add_workflow_log(ledger_id, v["id"], "reject", "pending_review", "draft", user_id, reason)

def reverse_voucher(voucher_no, reason="", user_id=None, operator_name=None):
    """reverse_voucher"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
    if not v:
        raise ValueError("凭证不存在")
    if v["status"] != "posted":
        raise ValueError("只能冲销已过账的凭证")

    # 创建冲销凭证号
    prefix = f"CH{v['date'].replace('-', '')}"
    count = conn.execute("SELECT COUNT(*) FROM vouchers WHERE voucher_no LIKE ? AND ledger_id = ?",
                         (prefix + "%", v["ledger_id"])).fetchone()[0]
    reverse_no = f"{prefix}{count+1:04d}"

    entries = conn.execute("SELECT * FROM journal_entries WHERE voucher_id = ?", (v["id"],)).fetchall()

    # 红字冲销：借贷方向互换，金额取正数（会计规范：红字冲销=反向等额分录）
    reverse_entries = [{
        "account_code": e["account_code"],
        "account_name": e["account_name"],
        "debit": round(e["credit"], 2),   # 原贷方 → 冲销借方
        "credit": round(e["debit"], 2),   # 原借方 → 冲销贷方
        "summary": f"红字冲销{voucher_no}: {e['summary']}",
    } for e in entries]

    total_dr = sum(e["debit"] for e in reverse_entries)
    total_cr = sum(e["credit"] for e in reverse_entries)

    cur = conn.execute(
        "INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status, currency) VALUES (?,?,?,?,?,?,?,?)",
        (v["ledger_id"], reverse_no, date.today().isoformat(),
         f"红字冲销 {voucher_no}" + (f" - {reason}" if reason else ""),
         total_dr, total_cr, "posted", v.get("currency", "CNY"))
    )
    reverse_id = cur.lastrowid

    for e in reverse_entries:
        conn.execute(
            "INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary, foreign_currency, foreign_amount, exchange_rate) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (v["ledger_id"], reverse_id, e["account_code"], e["account_name"], e["debit"], e["credit"], e["summary"],
             e.get("foreign_currency", ""), e.get("foreign_amount", 0), e.get("exchange_rate", 1))
        )

    conn.execute("UPDATE vouchers SET status = 'reversed', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=v["ledger_id"],
        action="reverse_voucher",
        detail=f"冲销凭证 {voucher_no} -> {reverse_no}: {reason}",
        voucher_id=v["id"],
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        remark=f"原凭证:{voucher_no} 冲销:{reverse_no}",
        conn=conn,
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    return reverse_no

def delete_voucher(voucher_no, ledger_id=None, user_id=None, operator_name=None):
    """删除凭证（仅限 draft 状态）
    ledger_id 为可选参数，用于验证凭证归属（推荐传入以提升安全性）
    """
    conn = get_conn()
    try:
        with transaction(conn):
            if ledger_id is not None:
                v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
            else:
                v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
            if not v:
                raise ValueError("凭证不存在或不属于该账套")
            if v["status"] != "draft":
                raise ValueError("只能删除草稿状态的凭证，已过账请使用冲销")
            conn.execute("DELETE FROM journal_entries WHERE voucher_id = ?", (v["id"],))
            conn.execute("DELETE FROM vouchers WHERE id = ?", (v["id"],))
            add_audit_log(
                ledger_id=v["ledger_id"],
                action="delete_voucher",
                detail=f"删除凭证 {voucher_no}",
                voucher_id=None,
                module="voucher",
                target_table="vouchers",
                target_id=v["id"],
                user_id=user_id,
                operator_name=operator_name,
                remark=f"凭证号:{voucher_no}",
                conn=conn,
            )
    finally:
        conn.close()

def get_vouchers(ledger_id, year=None, month=None, status=None, limit=100):
    """查询凭证列表"""
    conn = get_conn()
    sql = "SELECT * FROM vouchers WHERE ledger_id = ?"
    params = [ledger_id]
    if year:
        sql += " AND strftime('%Y', date) = ?"
        params.append(str(year))
    if month:
        sql += " AND strftime('%m', date) = ?"
        params.append(f"{month:02d}")
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY date DESC, voucher_no DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result

def get_voucher_detail(ledger_id, voucher_no):
    """获取凭证详情（验证凭证属于指定账套）"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    if not v:
        conn.close()
        return None
    entries = conn.execute("SELECT * FROM journal_entries WHERE voucher_id = ?", (v["id"],)).fetchall()
    result = dict(v)
    result["entries"] = [dict(e) for e in entries]
    conn.close()
    return result

def generate_voucher_from_text(ledger_id: int, text: str) -> dict:
    """
    从自然语言描述生成分录建议
    返回 {"description": str, "entries": [...], "confidence": float, "composite": bool, "currency": str, "exchange_rate": float}
    规则引擎实现（基于关键词匹配 + 金额提取）
    支持：简单一借一贷 / 复合多借多贷 / 外币金额
    """
    import re
    text = str(text).strip()
    entries = []
    description = text
    confidence = 0.5
    currency = "CNY"
    exchange_rate = 1.0
    is_composite = False

    def _extract_amount(t):
        """提取金额，支持'万'单位和逗号"""
        m = re.search(r'(\d[\d,]*\.?\d*)\s*[万wW]', t)
        if m:
            return float(m.group(1).replace(',', '')) * 10000
        m = re.search(r'(\d[\d,]*\.?\d*)', t.replace(',', ''))
        if m:
            return float(m.group(1))
        return None

    def _extract_currency(t):
        """提取外币币种"""
        currency_map = {
            'USD': ['USD', '美元', '\\$'], 'EUR': ['EUR', '欧元'],
            'JPY': ['JPY', '日元'], 'HKD': ['HKD', '港币', '港元'],
            'GBP': ['GBP', '英镑'],
        }
        for code, keywords in currency_map.items():
            for kw in keywords:
                if kw in t:
                    return code
        return 'CNY'

    def _extract_all_amounts(t):
        """提取文本中所有金额，支持万/w/元"""
        amounts = []
        # 先匹配 数字+万/w
        for m in re.finditer(r'(\d[\d,]*\.?\d*)\s*[万wW]', t):
            amounts.append(float(m.group(1).replace(',', '')) * 10000)
        # 再匹配 数字+元（排除已匹配的万/w数字）
        if not amounts:
            for m in re.finditer(r'(\d[\d,]*\.?\d*)\s*元', t):
                amounts.append(float(m.group(1).replace(',', '')))
        # 最后匹配纯数字（排除已匹配的）
        if not amounts:
            for m in re.finditer(r'(\d[\d,]*\.?\d*)', t.replace(',', '')):
                amounts.append(float(m.group(1)))
        return amounts

    # 复合业务解析器
    def _parse_partial_cash_credit(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 3:
            total, cash, credit = amounts[0], amounts[1], amounts[2]
        elif len(amounts) == 2:
            total, cash = amounts[0], amounts[1]
            credit = total - cash
        else:
            total = amounts[0] if amounts else 0
            cash = total * 0.6
            credit = total - cash
        is_fixed = any(kw in t for kw in ['设备', '机器', '固定资产'])
        debit_code = '1601' if is_fixed else '1403'
        debit_name = '固定资产' if is_fixed else '原材料'
        return [
            {"account_code": debit_code, "account_name": debit_name, "debit": round(total, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(cash, 2)},
            {"account_code": "2202", "account_name": "应付账款", "debit": 0, "credit": round(credit, 2)},
        ]

    def _parse_partial_cash_ar(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 3:
            total, cash, ar = amounts[0], amounts[1], amounts[2]
        elif len(amounts) == 2:
            total, cash = amounts[0], amounts[1]
            ar = total - cash
        else:
            total = amounts[0] if amounts else 0
            cash = total * 0.6
            ar = total - cash
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(cash, 2), "credit": 0},
            {"account_code": "1122", "account_name": "应收账款", "debit": round(ar, 2), "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_expense_reimbursement(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 3:
            total, cash, loan = amounts[0], amounts[1], amounts[2]
        elif len(amounts) == 2:
            total, cash = amounts[0], amounts[1]
            loan = total - cash
        else:
            total = amounts[0] if amounts else 0
            cash = total * 0.6
            loan = total - cash
        return [
            {"account_code": "6602", "account_name": "管理费用", "debit": round(total, 2), "credit": 0},
            {"account_code": "1001", "account_name": "库存现金", "debit": 0, "credit": round(cash, 2)},
            {"account_code": "1221", "account_name": "其他应收款", "debit": 0, "credit": round(loan, 2)},
        ]

    def _parse_purchase_with_vat(t):
        amounts = _extract_all_amounts(t)
        rate_match = re.search(r'税率[：:\s]*(\d+\.?\d*)%', t)
        rate = float(rate_match.group(1)) / 100 if rate_match else 0.13
        if len(amounts) >= 2:
            if '不含税' in t:
                ex_tax = amounts[0]
                vat = round(ex_tax * rate, 2)
                total = ex_tax + vat
            elif len(amounts) >= 3:
                ex_tax, vat = amounts[0], amounts[1]
                total = ex_tax + vat
            else:
                total_or_ex = amounts[0]
                if '价税合计' in t or '总价' in t:
                    ex_tax = round(total_or_ex / (1 + rate), 2)
                    vat = total_or_ex - ex_tax
                    total = total_or_ex
                else:
                    ex_tax = total_or_ex
                    vat = round(ex_tax * rate, 2)
                    total = ex_tax + vat
        else:
            ex_tax = amounts[0] if amounts else 0
            vat = round(ex_tax * rate, 2)
            total = ex_tax + vat
        is_fixed = any(kw in t for kw in ['设备', '机器', '固定资产'])
        debit_code = '1601' if is_fixed else '1403'
        debit_name = '固定资产' if is_fixed else '原材料'
        return [
            {"account_code": debit_code, "account_name": debit_name, "debit": round(ex_tax, 2), "credit": 0},
            {"account_code": "222101", "account_name": "应交增值税(进项税额)", "debit": round(vat, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_salary_allocation(t):
        amounts = _extract_all_amounts(t)
        if not amounts:
            return None
        dept_keywords = [
            ('生产成本', ['生产', '车间', '制造'], '5001'),
            ('管理费用', ['管理', '行政', '财务', '人事'], '6602'),
            ('销售费用', ['销售', '营销', '市场'], '6601'),
            ('研发支出', ['研发', '开发', '技术'], '5301'),
        ]
        matched_depts = []
        for dept_name, keywords, acct_code in dept_keywords:
            if any(kw in t for kw in keywords):
                matched_depts.append((dept_name, acct_code))
        if not matched_depts:
            matched_depts = [
                ('生产成本', '5001'),
                ('管理费用', '6602'),
                ('销售费用', '6601'),
            ]
        # Assign amounts to departments in order
        depts = []
        for i, (dept_name, acct_code) in enumerate(matched_depts):
            if i < len(amounts):
                dept_amt = round(amounts[i], 2)
            else:
                dept_amt = 0
            depts.append({"account_code": acct_code, "account_name": dept_name,
                          "debit": dept_amt, "credit": 0})
        total = sum(d['debit'] for d in depts)
        depts.append({"account_code": "2211", "account_name": "应付职工薪酬", "debit": 0, "credit": round(total, 2)})
        return depts

    def _parse_loan_repayment_with_interest(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 2:
            principal, interest = amounts[0], amounts[1]
        else:
            principal = amounts[0] if amounts else 0
            interest = round(principal * 0.05, 2)
        return [
            {"account_code": "2001", "account_name": "短期借款", "debit": round(principal, 2), "credit": 0},
            {"account_code": "6603", "account_name": "财务费用", "debit": round(interest, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(principal + interest, 2)},
        ]

    def _parse_investment_and_loan(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 2:
            invest, loan = amounts[0], amounts[1]
        else:
            invest = amounts[0] if amounts else 0
            loan = round(invest * 0.5, 2)
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(invest + loan, 2), "credit": 0},
            {"account_code": "4001", "account_name": "实收资本", "debit": 0, "credit": round(invest, 2)},
            {"account_code": "2001", "account_name": "短期借款", "debit": 0, "credit": round(loan, 2)},
        ]

    def _parse_depr_and_amort(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 2:
            depr, amort = amounts[0], amounts[1]
        else:
            depr = amounts[0] if amounts else 0
            amort = round(depr * 0.3, 2)
        return [
            {"account_code": "6602", "account_name": "管理费用-折旧", "debit": round(depr, 2), "credit": 0},
            {"account_code": "6602", "account_name": "管理费用-摊销", "debit": round(amort, 2), "credit": 0},
            {"account_code": "1602", "account_name": "累计折旧", "debit": 0, "credit": round(depr, 2)},
            {"account_code": "1702", "account_name": "累计摊销", "debit": 0, "credit": round(amort, 2)},
        ]

    def _parse_purchase_with_freight(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        freight = round(total * 0.05, 2) if len(amounts) < 2 else amounts[1]
        goods = total - freight
        return [
            {"account_code": "1403", "account_name": "原材料", "debit": round(goods, 2), "credit": 0},
            {"account_code": "6602", "account_name": "管理费用-运费", "debit": round(freight, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_sale_with_discount(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        discount = round(total * 0.1, 2) if len(amounts) < 2 else amounts[1]
        net = total - discount
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(net, 2), "credit": 0},
            {"account_code": "6601", "account_name": "销售费用-折扣", "debit": round(discount, 2), "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_equity_investment_fixed(t):
        amounts = _extract_all_amounts(t)
        val = amounts[0] if amounts else 0
        return [
            {"account_code": "1601", "account_name": "固定资产", "debit": round(val, 2), "credit": 0},
            {"account_code": "4001", "account_name": "实收资本", "debit": 0, "credit": round(val, 2)},
        ]

    def _parse_income_tax(t):
        amounts = _extract_all_amounts(t)
        tax = amounts[0] if amounts else 0
        return [
            {"account_code": "6801", "account_name": "所得税费用", "debit": round(tax, 2), "credit": 0},
            {"account_code": "2231", "account_name": "应交税费-应交所得税", "debit": 0, "credit": round(tax, 2)},
        ]

    def _parse_profit_distribution(t):
        amounts = _extract_all_amounts(t)
        profit = amounts[0] if amounts else 0
        dividend = round(profit * 0.3, 2)
        return [
            {"account_code": "4104", "account_name": "利润分配-未分配利润", "debit": round(dividend, 2), "credit": 0},
            {"account_code": "2232", "account_name": "应付股利", "debit": 0, "credit": round(dividend, 2)},
        ]

    def _parse_prepayment_purchase(t):
        amounts = _extract_all_amounts(t)
        amt = amounts[0] if amounts else 0
        return [
            {"account_code": "1123", "account_name": "预付账款", "debit": round(amt, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(amt, 2)},
        ]

    def _parse_social_insurance(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        company = round(total * 0.7, 2)
        return [
            {"account_code": "6601", "account_name": "管理费用-社保", "debit": round(company, 2), "credit": 0},
            {"account_code": "2211", "account_name": "应付职工薪酬-社保", "debit": 0, "credit": round(total, 2)},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_housing_fund(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        return [
            {"account_code": "6601", "account_name": "管理费用-公积金", "debit": round(total, 2), "credit": 0},
            {"account_code": "2211", "account_name": "应付职工薪酬-公积金", "debit": 0, "credit": round(total, 2)},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_fixed_asset_disposal(t):
        amounts = _extract_all_amounts(t)
        proceeds = amounts[0] if amounts else 1000
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(proceeds, 2), "credit": 0},
            {"account_code": "1601", "account_name": "固定资产", "debit": 0, "credit": round(proceeds * 1.2, 2)},
            {"account_code": "1602", "account_name": "累计折旧", "debit": round(proceeds * 0.2, 2), "credit": 0},
        ]

    def _parse_prepayment_received(t):
        amounts = _extract_all_amounts(t)
        amt = amounts[0] if amounts else 0
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(amt, 2), "credit": 0},
            {"account_code": "2203", "account_name": "预收账款", "debit": 0, "credit": round(amt, 2)},
        ]

    def _parse_bad_debt_writeoff(t):
        amounts = _extract_all_amounts(t)
        amt = amounts[0] if amounts else 0
        return [
            {"account_code": "1231", "account_name": "坏账准备", "debit": round(amt, 2), "credit": 0},
            {"account_code": "1122", "account_name": "应收账款", "debit": 0, "credit": round(amt, 2)},
        ]

    def _parse_export_with_rebate(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        rebate = round(total * 0.13, 2)
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(total + rebate, 2), "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": round(total, 2)},
            {"account_code": "2231", "account_name": "应交税费-出口退税", "debit": 0, "credit": round(rebate, 2)},
        ]

    def _parse_cip_to_fixed(t):
        amounts = _extract_all_amounts(t)
        val = amounts[0] if amounts else 0
        return [
            {"account_code": "1601", "account_name": "固定资产", "debit": round(val, 2), "credit": 0},
            {"account_code": "1604", "account_name": "在建工程", "debit": 0, "credit": round(val, 2)},
        ]

    def _parse_salary_with_tax(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        tax = round(total * 0.1, 2)
        net = total - tax
        return [
            {"account_code": "2211", "account_name": "应付职工薪酬", "debit": round(total, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(net, 2)},
            {"account_code": "2231", "account_name": "应交税费-个人所得税", "debit": 0, "credit": round(tax, 2)},
        ]

    # 复合业务规则（优先匹配）
    composite_rules = [
        {"pattern": r'(购入|购买|采购|购)(设备|机器|材料|原材料|商品|货物).+(其中|一部?分?).+(支付|付现|银行存款|现金).+(余款|剩余|欠|赊|应付)',
         "desc_fn": lambda m: f"购入{m.group(2)}，部分付现部分赊购", "parser": _parse_partial_cash_credit, "confidence": 0.95},
        {"pattern": r'(销售|卖出|出售|销)(商品|货物|产品|材料).+(其中|一部?分?).+(收现|收到|银行存款|现金).+(余款|剩余|赊|应收|欠款)',
         "desc_fn": lambda m: "销售商品，部分收现部分赊销", "parser": _parse_partial_cash_ar, "confidence": 0.95},
        {"pattern": r'(报销|差旅费|出差).+(其中|一部?分?).+(现金|银行存款|付现).+(冲|抵|还|借款|其他应收款)',
         "desc_fn": lambda m: "报销差旅费，部分付现部分冲借款", "parser": _parse_expense_reimbursement, "confidence": 0.93},
        {"pattern": r'(购入|购买|采购|购)(材料|原材料|设备|商品|货物).+(增值税|进项税|税率)',
         "desc_fn": lambda m: "购入货物含增值税进项", "parser": _parse_purchase_with_vat, "confidence": 0.93},
        {"pattern": r'(计提|分配).+(工资|薪酬|职工薪酬).+(生产|管理|销售|研发)',
         "desc_fn": lambda m: "计提工资分配到多科目", "parser": _parse_salary_allocation, "confidence": 0.92},
        {"pattern": r'(归还|偿还|还)(借款|贷款).+(利息|手续费)',
         "desc_fn": lambda m: "归还借款并支付利息", "parser": _parse_loan_repayment_with_interest, "confidence": 0.93},
        {"pattern": r'(投资|注资|出资).+(借款|贷款|银行)',
         "desc_fn": lambda m: "收到投资款及银行借款", "parser": _parse_investment_and_loan, "confidence": 0.90},
        {"pattern": r'(折旧|计提折旧).+(摊销|无形资产)',
         "desc_fn": lambda m: "计提折旧及无形资产摊销", "parser": _parse_depr_and_amort, "confidence": 0.92},
        # ── Phase 7 新增复合规则 ──
        {"pattern": r'(采购|购买|购入|购)(材料|原材料|商品|货物).+(运费|运输费|物流费|装卸费)',
         "desc_fn": lambda m: "采购货物并支付运费", "parser": _parse_purchase_with_freight, "confidence": 0.94},
        {"pattern": r'(销售|卖出|出售|销)(商品|货物|产品).+(折扣|折让|优惠|返利)',
         "desc_fn": lambda m: "销售商品并给予折扣", "parser": _parse_sale_with_discount, "confidence": 0.94},
        {"pattern": r'(收到|收)(投资|注资|出资|股东).+(设备|固定资产|资产).+(股权|资本|股份)',
         "desc_fn": lambda m: "收到固定资产投资（实物出资）", "parser": _parse_equity_investment_fixed, "confidence": 0.91},
        {"pattern": r'(计提|分配|结转).+(所得税|企业所得税|所得)',
         "desc_fn": lambda m: "计提所得税费用", "parser": _parse_income_tax, "confidence": 0.92},
        {"pattern": r'(利润|净利润|本年利润).+(分配|分红|股利|派息)',
         "desc_fn": lambda m: "利润分配（宣告股利）", "parser": _parse_profit_distribution, "confidence": 0.93},
        {"pattern": r'(购入|购买|采购).+(材料|原材料).+(预付|预付款|先付)',
         "desc_fn": lambda m: "预付采购货款", "parser": _parse_prepayment_purchase, "confidence": 0.93},
        {"pattern": r'(支付|付|交).+(社保|社会保险|养老保险|医疗保险)',
         "desc_fn": lambda m: "支付社会保险费", "parser": _parse_social_insurance, "confidence": 0.92},
        {"pattern": r'(支付|付|交).+(公积金|住房公积金)',
         "desc_fn": lambda m: "支付住房公积金", "parser": _parse_housing_fund, "confidence": 0.92},
        {"pattern": r'(处置|出售|卖出).+(固定资产|设备|机器).+(清理|报废|转让)',
         "desc_fn": lambda m: "处置固定资产", "parser": _parse_fixed_asset_disposal, "confidence": 0.91},
        {"pattern": r'(收到|收)(客户|买方|购货方).+(预付|预付款|定金)',
         "desc_fn": lambda m: "收到客户预付货款", "parser": _parse_prepayment_received, "confidence": 0.93},
        {"pattern": r'(结转|转销|核销).+(坏账|坏账准备|减值)',
         "desc_fn": lambda m: "核销坏账准备", "parser": _parse_bad_debt_writeoff, "confidence": 0.92},
        {"pattern": r'(出口|外销|外贸).+(销售|卖出|出售).+(退税|出口退税)',
         "desc_fn": lambda m: "出口销售并确认退税", "parser": _parse_export_with_rebate, "confidence": 0.90},
        {"pattern": r'(建造|建设|施工|在建工程).+(完工|竣工|验收).+(转固|结转)',
         "desc_fn": lambda m: "在建工程完工转固", "parser": _parse_cip_to_fixed, "confidence": 0.93},
        {"pattern": r'(发放|发).+(工资|薪酬).+(代扣|扣除).+(个税|个人所得税)',
         "desc_fn": lambda m: "发放工资并代扣个税", "parser": _parse_salary_with_tax, "confidence": 0.93},
    ]

    # 尝试复合规则匹配
    composite_matched = False
    for cr in composite_rules:
        m = re.search(cr["pattern"], text)
        if m:
            try:
                parsed = cr["parser"](text)
                if parsed and len(parsed) >= 2:
                    entries = parsed
                    description = cr["desc_fn"](m)
                    confidence = cr["confidence"]
                    is_composite = True
                    composite_matched = True
                    break
            except Exception:
                continue

    if not composite_matched:
        # ===== 简单规则（原有逻辑）=====
        amount = _extract_amount(text)
        if amount is None:
            amount = 0

        currency = _extract_currency(text)
        if currency != 'CNY':
            exchange_rate = get_exchange_rate(currency, 'CNY', datetime.now().strftime('%Y-%m-%d')) or 1.0
        else:
            exchange_rate = 1.0

        # 简单规则回退
        if not entries:
            amount = amount or _extract_amount(text) or 0
            # 基本关键词匹配
            if any(kw in text for kw in ["收入", "销售", "卖出"]):
                entries = [
                    {"account_code": "1002", "account_name": "银行存款", "debit": amount, "credit": 0},
                    {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": amount},
                ]
                description = "确认收入"
                confidence = 0.70
            elif any(kw in text for kw in ["采购", "购入", "购买"]):
                entries = [
                    {"account_code": "1403", "account_name": "原材料", "debit": amount, "credit": 0},
                    {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": amount},
                ]
                description = "采购原材料"
                confidence = 0.70
            elif any(kw in text for kw in ["报销", "费用"]):
                entries = [
                    {"account_code": "6602", "account_name": "管理费用", "debit": amount, "credit": 0},
                    {"account_code": "1001", "account_name": "库存现金", "debit": 0, "credit": amount},
                ]
                description = "报销费用"
                confidence = 0.70
            else:
                entries = [
                    {"account_code": "1002", "account_name": "银行存款", "debit": amount, "credit": 0},
                    {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": amount},
                ]
                description = text[:30]
                confidence = 0.50

    return {"description": description, "entries": entries, "confidence": confidence,
            "composite": is_composite, "currency": currency, "exchange_rate": exchange_rate}

def get_voucher_templates(ledger_id: int, include_inactive: bool = False) -> list:
    """获取凭证模板列表"""
    conn = get_conn()
    if include_inactive:
        rows = conn.execute(
            "SELECT * FROM voucher_templates WHERE ledger_id = ? ORDER BY name",
            (ledger_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM voucher_templates WHERE ledger_id = ? AND is_active = 1 ORDER BY name",
            (ledger_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_voucher_template(ledger_id, name, description, entries, category='general', is_system=0):
    """创建凭证模板"""
    import json
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO voucher_templates (ledger_id, name, description, category, entries, is_system) VALUES (?,?,?,?,?,?)",
            (ledger_id, name, description, category, json.dumps(entries, ensure_ascii=False), is_system)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"模板名称 '{name}' 已存在")
    finally:
        conn.close()

def update_voucher_template(template_id, ledger_id, name=None, description=None, entries=None, category=None, is_active=None):
    """更新凭证模板"""
    import json
    conn = get_conn()
    updates = {}
    if name is not None:
        updates["name"] = name
    if description is not None:
        updates["description"] = description
    if entries is not None:
        updates["entries"] = json.dumps(entries, ensure_ascii=False)
    if category is not None:
        updates["category"] = category
    if is_active is not None:
        updates["is_active"] = 1 if is_active else 0
    if not updates:
        conn.close()
        return
    updates["updated_at"] = "datetime('now','localtime')"
    # 手动构建 SET 子句，因为 updated_at 是 SQL 表达式
    set_parts = []
    params = []
    for k, v in updates.items():
        if k == "updated_at":
            set_parts.append(f"{k} = {v}")
        else:
            set_parts.append(f"{k} = ?")
            params.append(v)
    params.extend([template_id, ledger_id])
    conn.execute(
        f"UPDATE voucher_templates SET {', '.join(set_parts)} WHERE id = ? AND ledger_id = ? AND is_system = 0",
        params
    )
    conn.commit()
    conn.close()
    clear_query_cache()

def delete_voucher_template(template_id, ledger_id):
    """删除凭证模板（不能删除系统模板）"""
    conn = get_conn()
    conn.execute(
        "DELETE FROM voucher_templates WHERE id = ? AND ledger_id = ? AND is_system = 0",
        (template_id, ledger_id)
    )
    conn.commit()
    conn.close()
    clear_query_cache()

def submit_for_review(ledger_id, voucher_no, user_id=None, operator_name=None):
    """submit_for_review: draft/reversed -> pending_review"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    if not v:
        conn.close()
        raise ValueError("voucher not found")
    if v["status"] not in ("draft", "reversed"):
        conn.close()
        raise ValueError("only draft/reversed can submit for review")
    conn.execute("UPDATE vouchers SET status = 'pending_review', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=ledger_id,
        action="submit_review",
        detail="提交审核 " + voucher_no,
        voucher_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        remark=f"凭证号:{voucher_no}",
        conn=conn,
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    add_workflow_log(ledger_id, v["id"], "submit", v["status"], "pending_review", user_id)

def get_voucher_workflow(voucher_id: int) -> list:
    """获取凭证的审核流程历史"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT w.*, u.username "
        "FROM voucher_workflow w "
        "LEFT JOIN users u ON w.user_id = u.id "
        "WHERE w.voucher_id = ? ORDER BY w.created_at ASC",
        (voucher_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_scheduled_vouchers(ledger_id: int) -> list:
    """获取定时凭证任务列表"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT sv.*, vt.name as template_name "
        "FROM scheduled_vouchers sv "
        "LEFT JOIN voucher_templates vt ON sv.template_id = vt.id "
        "WHERE sv.ledger_id = ? AND sv.is_active = 1 "
        "ORDER BY sv.next_run_at",
        (ledger_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_scheduled_voucher(ledger_id: int, name: str, cron_expression: str, template_id: int = None, next_run_at: str = None):
    """添加定时凭证任务"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO scheduled_vouchers (ledger_id, template_id, name, cron_expression, next_run_at) VALUES (?,?,?,?,?)",
        (ledger_id, template_id, name, cron_expression, next_run_at)
    )
    conn.commit()
    conn.close()
    clear_query_cache()

def run_scheduled_voucher(scheduled_id: int) -> str:
    """执行定时凭证任务，生成实际凭证"""
    from datetime import datetime
    conn = get_conn()
    sv = conn.execute("SELECT * FROM scheduled_vouchers WHERE id = ?", (scheduled_id,)).fetchone()
    if not sv:
        conn.close()
        raise ValueError("定时任务不存在")

    entries = []
    if sv["template_id"]:
        tpl = conn.execute("SELECT entries FROM voucher_templates WHERE id = ?", (sv["template_id"],)).fetchone()
        if tpl:
            entries = _json_mod.loads(tpl["entries"])
    else:
        conn.close()
        raise ValueError("定时任务未关联凭证模板")

    if not entries:
        conn.close()
        raise ValueError("凭证模板分录为空")

    today = datetime.now().strftime("%Y-%m-%d")
    vn = create_voucher(sv["ledger_id"], today, f"[自动]{sv['name']}", entries, status="draft")

    # 更新最后执行时间
    conn.execute(
        "UPDATE scheduled_vouchers SET last_run_at = datetime('now','localtime'), updated_at = datetime('now','localtime') WHERE id = ?",
        (scheduled_id,)
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    return vn

def link_invoice_voucher(invoice_id: int, voucher_id: int, ledger_id: int):
    """关联发票与凭证"""
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO invoice_voucher (invoice_id, voucher_id, ledger_id) VALUES (?,?,?)",
        (invoice_id, voucher_id, ledger_id)
    )
    conn.commit()
    conn.close()
    clear_query_cache()

def get_invoice_vouchers(invoice_id: int) -> list:
    """获取发票关联的凭证"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT v.* FROM vouchers v "
        "JOIN invoice_voucher iv ON v.id = iv.voucher_id "
        "WHERE iv.invoice_id = ? ORDER BY v.date DESC",
        (invoice_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def import_vouchers_from_excel(ledger_id: int, file_path: str) -> dict:
    """从 Excel 文件批量导入凭证
    期望列：日期 | 摘要 | 科目代码 | 科目名称 | 借方金额 | 贷方金额
    返回: {"total": N, "imported": N, "errors": [str], "voucher_nos": [str]}
    """
    import openpyxl
    from datetime import datetime

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    result = {"total": 0, "imported": 0, "errors": [], "voucher_nos": []}
    current_voucher = None  # {"date": ..., "desc": ..., "entries": [...]}

    rows = list(ws.iter_rows(min_row=2, values_only=True))  # 跳过表头

    def _flush_voucher():
        nonlocal current_voucher, result
        if not current_voucher:
            return
        entries = current_voucher["entries"]
        if not entries:
            result["errors"].append(f"凭证 {current_voucher['date']} {current_voucher['desc']} 无分录")
            return
        total_dr = sum(e["debit"] for e in entries)
        total_cr = sum(e["credit"] for e in entries)
        if abs(total_dr - total_cr) > 0.01:
            result["errors"].append(
                f"凭证 {current_voucher['date']} {current_voucher['desc']} 借贷不平(借{total_dr:.2f} 贷{total_cr:.2f})")
            return
        try:
            vn = create_voucher(ledger_id, current_voucher["date"],
                                current_voucher["desc"], entries, status="draft")
            result["imported"] += 1
            result["voucher_nos"].append(vn)
        except ValueError as e:
            result["errors"].append(f"凭证 {current_voucher['date']} {current_voucher['desc']}: {e}")

    for row in rows:
        if all(v is None for v in row):
            continue
        result["total"] += 1

        date_val = row[0]
        desc = str(row[1]).strip() if row[1] else ""
        code = str(row[2]).strip() if row[2] else ""
        name = str(row[3]).strip() if row[3] else ""
        debit = float(row[4]) if row[4] else 0
        credit = float(row[5]) if row[5] else 0

        # 日期解析
        if isinstance(date_val, datetime):
            date_str = date_val.strftime("%Y-%m-%d")
        elif isinstance(date_val, str):
            date_str = date_val.strip()
        else:
            date_str = str(date_val)

        # 新凭证：以日期+摘要变化为分界
        if current_voucher is None or date_str != current_voucher["date"] or desc != current_voucher["desc"]:
            _flush_voucher()
            current_voucher = {"date": date_str, "desc": desc, "entries": []}

        if code:
            current_voucher["entries"].append({
                "account_code": code,
                "account_name": name,
                "debit": debit,
                "credit": credit,
                "summary": "",
            })

    _flush_voucher()  # 最后一张
    return result

def generate_composite_voucher(ledger_id: int, text: str) -> dict:
    """
    复合业务AI凭证生成 — 支持多借多贷、一句话描述复杂业务
    返回 {"description": str, "entries": [...], "confidence": float, "composite": bool}
    """
    import re
    text = str(text).strip()

    def _extract_all_amounts(t):
        amounts = []
        for m in re.finditer(r'(\d+\.?\d*)\s*[万wW]', t):
            amounts.append(float(m.group(1)) * 10000)
        if not amounts:
            for m in re.finditer(r'(\d[\d,]*(?:\.\d+)?)', t.replace(',', '')):
                amounts.append(float(m.group(1)))
        return amounts

    def _get_account(code):
        conn = get_conn()
        row = conn.execute("SELECT name FROM accounts WHERE code = ?", (code,)).fetchone()
        conn.close()
        return row["name"] if row else code

    def _make_entry(code, debit=0, credit=0, summary=""):
        return {"account_code": code, "account_name": _get_account(code),
                "debit": round(debit, 2), "credit": round(credit, 2), "summary": summary}

    def _parse_mixed_purchase(t, amounts):
        if len(amounts) >= 2:
            total, cash = amounts[0], amounts[1]
            credit_amt = round(total - cash, 2)
            return ("购入固定资产（部分赊购）", [
                _make_entry("1601", debit=total, summary="购入固定资产"),
                _make_entry("1002", credit=cash, summary="银行存款支付"),
                _make_entry("2202", credit=credit_amt, summary="余款赊购（应付账款）"),
            ])
        return None

    def _parse_mixed_sale(t, amounts):
        if len(amounts) >= 2:
            total, cash = amounts[0], amounts[1]
            credit_amt = round(total - cash, 2)
            return ("销售商品（部分赊销）", [
                _make_entry("1002", debit=cash, summary="银行存款收现"),
                _make_entry("1122", debit=credit_amt, summary="余款赊销（应收账款）"),
                _make_entry("6001", credit=total, summary="主营业务收入"),
            ])
        return None

    def _parse_reimbursement(t, amounts):
        if len(amounts) >= 2:
            total, cash = amounts[0], amounts[1]
            other = round(total - cash, 2)
            return ("报销差旅费（部分冲借款）", [
                _make_entry("6602", debit=total, summary="差旅费报销"),
                _make_entry("1001", credit=cash, summary="现金支付"),
                _make_entry("1221", credit=other, summary="冲抵其他应收款"),
            ])
        return None

    def _parse_purchase_with_tax(t, amounts):
        if len(amounts) >= 2:
            material, tax = amounts[0], amounts[1]
            total = round(material + tax, 2)
            return ("采购原材料（含增值税）", [
                _make_entry("1403", debit=material, summary="原材料采购"),
                _make_entry("222101", debit=tax, summary="进项增值税"),
                _make_entry("1002", credit=total, summary="银行存款支付"),
            ])
        return None

    def _parse_multi_dept_salary(t, amounts):
        if len(amounts) >= 3:
            a, b, c = amounts[0], amounts[1], amounts[2]
            total = round(a + b + c, 2)
            return ("计提职工薪酬（多部门）", [
                _make_entry("5101", debit=a, summary="生产工人工资"),
                _make_entry("6602", debit=b, summary="管理人员工资"),
                _make_entry("6601", debit=c, summary="销售人员工资"),
                _make_entry("2211", credit=total, summary="应付职工薪酬"),
            ])
        return None

    composite_rules = [
        (r'(?:购入|购买|采购|购)(?:设备|固定资产|机器).*(?:其中|部分).*(?:余款|剩余|赊购|欠款|应付)', _parse_mixed_purchase),
        (r'(?:销售|卖出|出售).*(?:商品|货物|产品).*(?:其中|部分).*(?:收现|现金|余款赊销|挂账)', _parse_mixed_sale),
        (r'(?:报销|差旅费).*(?:现金|库存现金).*(?:冲抵|冲借款|其他应收|剩余)', _parse_reimbursement),
        (r'(?:购入|采购|购买).*(?:原材料|材料).*(?:增值税|进项).*(?:全部|银行)', _parse_purchase_with_tax),
        (r'(?:计提|分配).*(?:工资|薪酬).*(?:生产|工人|管理|销售)', _parse_multi_dept_salary),
    ]

    for pattern, handler in composite_rules:
        if re.search(pattern, text):
            amounts = _extract_all_amounts(text)
            if amounts:
                result = handler(text, amounts)
                if result:
                    desc, entries = result
                    total_dr = sum(e["debit"] for e in entries)
                    total_cr = sum(e["credit"] for e in entries)
                    if abs(total_dr - total_cr) < 0.02:
                        return {"description": desc, "entries": entries,
                                "confidence": 0.88, "composite": True}

    return {"description": text, "entries": [], "confidence": 0.0, "composite": False}

def parse_complex_voucher(ledger_id: int, text: str) -> dict:
    """
    Phase 7: 高级复合业务解析入口
    结合: 正则匹配 + 关键词 + 上下文分析 + ai_rules_complex 表查询
    返回: {
        "description": str,
        "entries": [{"account_code", "account_name", "debit", "credit", "summary"}],
        "confidence": float,
        "composite": bool,
        "matched_rule": str | None,
        "analysis": dict  # 上下文分析详情
    }
    """
    import json, re as _re
    text = str(text).strip()

    def _extract_all_amounts(t):
        amounts = []
        for m in _re.finditer(r'(\d+\.?\d*)\s*[万wW]', t):
            amounts.append(float(m.group(1)) * 10000)
        if not amounts:
            for m in _re.finditer(r'(\d[\d,]*(?:\.\d+)?)', t.replace(',', '')):
                amounts.append(float(m.group(1)))
        return amounts

    def _get_account(code):
        conn = get_conn()
        row = conn.execute("SELECT name FROM accounts WHERE code = ?", (code,)).fetchone()
        conn.close()
        return row["name"] if row else code

    def _make_entry(code, debit=0, credit=0, summary=""):
        return {"account_code": code, "account_name": _get_account(code),
                "debit": round(debit, 2), "credit": round(credit, 2), "summary": summary}

    # ── 1. 上下文分析 ──
    analysis = {
        "detected_keywords": [],
        "detected_amounts": _extract_all_amounts(text),
        "detected_business_type": None,
        "context_score": 0.0,
    }

    # 关键词上下文映射
    context_keywords = {
        "采购": ["采购", "购入", "购买", "购货", "进货", "买"],
        "销售": ["销售", "卖出", "出售", "销货", "营收"],
        "费用": ["费用", "报销", "支出", "付款", "缴纳"],
        "薪酬": ["工资", "薪酬", "社保", "公积金", "奖金", "津贴"],
        "资产": ["设备", "机器", "固定资产", "在建工程", "无形资产"],
        "税费": ["增值税", "所得税", "城建税", "个税", "退税"],
        "融资": ["投资", "借款", "贷款", "注资", "股东"],
        "利润": ["利润", "分红", "股利", "分配"],
    }
    for biz_type, keywords in context_keywords.items():
        for kw in keywords:
            if kw in text:
                analysis["detected_keywords"].append(kw)
                if not analysis["detected_business_type"]:
                    analysis["detected_business_type"] = biz_type
                break

    amounts = analysis["detected_amounts"]
    amt_count = len(amounts)

    # ── 2. 内置复合规则匹配（高优先级）──
    # 规则: (pattern, handler_fn, confidence)
    def _rule_purchase_freight(t, amts):
        if len(amts) >= 2:
            mat, freight = amts[0], amts[1]
            total = round(mat + freight, 2)
            return ("采购材料含运费", [
                _make_entry("1403", debit=mat, summary="原材料采购"),
                _make_entry("6601", debit=freight, summary="运费"),
                _make_entry("1002", credit=total, summary="银行存款支付"),
            ])
        return None

    def _rule_sale_discount(t, amts):
        disc_match = _re.search(r'(\d+\.?\d*)%?\s*(折扣|折让|优惠)', t)
        if len(amts) >= 3:
            total, cash, disc = amts[0], amts[1], amts[2]
        elif len(amts) == 2:
            total, cash = amts[0], amts[1]
            disc = round(total - cash, 2)
        else:
            total = amts[0] if amts else 0
            rate = float(disc_match.group(1)) / 100 if disc_match and '%' in disc_match.group(0) else 0.05
            disc = round(total * rate, 2)
            cash = round(total - disc, 2)
        return ("销售商品含折扣", [
            _make_entry("1002", debit=cash, summary="实收金额"),
            _make_entry("6601", debit=disc, summary="销售折扣"),
            _make_entry("6001", credit=total, summary="主营业务收入"),
        ])

    def _rule_salary_tax(t, amts):
        if len(amts) >= 3:
            gross, tax, net = amts[0], amts[1], amts[2]
        elif len(amts) == 2:
            gross, tax = amts[0], amts[1]
            net = round(gross - tax, 2)
        else:
            gross = amts[0] if amts else 0
            tax = round(gross * 0.1, 2)
            net = round(gross - tax, 2)
        return ("发放工资代扣个税", [
            _make_entry("2211", debit=gross, summary="应付职工薪酬"),
            _make_entry("1002", credit=net, summary="实际发放"),
            _make_entry("222102", credit=tax, summary="代扣个税"),
        ])

    def _rule_social_insurance(t, amts):
        if len(amts) >= 2:
            co, per = amts[0], amts[1]
        else:
            total = amts[0] if amts else 0
            co = round(total * 0.7, 2)
            per = round(total * 0.3, 2)
        total = round(co + per, 2)
        return ("支付社会保险费", [
            _make_entry("6602", debit=co, summary="社保（公司部分）"),
            _make_entry("1221", debit=per, summary="社保（个人代扣）"),
            _make_entry("1002", credit=total, summary="银行存款支付"),
        ])

    def _rule_fixed_asset_disposal(t, amts):
        if len(amts) >= 3:
            orig, accum, proceeds = amts[0], amts[1], amts[2]
        elif len(amts) == 2:
            orig, accum = amts[0], amts[1]
            proceeds = round(orig - accum, 2)
        else:
            orig = amts[0] if amts else 0
            accum = round(orig * 0.6, 2)
            proceeds = round(orig - accum, 2)
        net = round(orig - accum, 2)
        return ("处置固定资产", [
            _make_entry("1602", debit=accum, summary="累计折旧"),
            _make_entry("1601", debit=net, summary="固定资产清理"),
            _make_entry("1601", credit=orig, summary="固定资产原值"),
            _make_entry("1002", debit=proceeds, summary="处置收入"),
        ])

    def _rule_cip_transfer(t, amts):
        amt = amts[0] if amts else 0
        return ("在建工程完工转固", [
            _make_entry("1601", debit=amt, summary="结转固定资产"),
            _make_entry("1604", credit=amt, summary="在建工程"),
        ])

    def _rule_export_rebate(t, amts):
        if len(amts) >= 2:
            rev, rebate = amts[0], amts[1]
        else:
            rev = amts[0] if amts else 0
            rebate = round(rev * 0.13, 2)
        return ("出口销售含退税", [
            _make_entry("1122", debit=rev, summary="应收账款"),
            _make_entry("6001", credit=rev, summary="主营业务收入"),
            _make_entry("1221", debit=rebate, summary="应收出口退税"),
            _make_entry("222101", credit=rebate, summary="应交增值税(出口退税)"),
        ])

    def _rule_prepay_purchase(t, amts):
        amt = amts[0] if amts else 0
        return ("预付采购货款", [
            _make_entry("1123", debit=amt, summary="预付账款"),
            _make_entry("1002", credit=amt, summary="银行存款支付"),
        ])

    def _rule_prepay_received(t, amts):
        amt = amts[0] if amts else 0
        return ("收到预收货款", [
            _make_entry("1002", debit=amt, summary="银行存款"),
            _make_entry("2203", credit=amt, summary="预收账款"),
        ])

    def _rule_profit_dist(t, amts):
        amt = amts[0] if amts else 0
        return ("利润分配-宣告股利", [
            _make_entry("4104", debit=amt, summary="利润分配"),
            _make_entry("2232", credit=amt, summary="应付股利"),
        ])

    def _rule_income_tax(t, amts):
        if len(amts) >= 2:
            profit, tax = amts[0], amts[1]
        else:
            profit = amts[0] if amts else 0
            tax = round(profit * 0.25, 2)
        return ("计提所得税费用", [
            _make_entry("6801", debit=tax, summary="所得税费用"),
            _make_entry("222102", credit=tax, summary="应交所得税"),
        ])

    def _rule_bad_debt(t, amts):
        amt = amts[0] if amts else 0
        return ("核销坏账准备", [
            _make_entry("1221", debit=amt, summary="坏账准备"),
            _make_entry("1122", credit=amt, summary="应收账款"),
        ])

    def _rule_equity_fixed(t, amts):
        amt = amts[0] if amts else 0
        return ("收到固定资产投资", [
            _make_entry("1601", debit=amt, summary="固定资产"),
            _make_entry("4001", credit=amt, summary="实收资本"),
        ])

    def _rule_housing_fund(t, amts):
        if len(amts) >= 2:
            co, per = amts[0], amts[1]
        else:
            total = amts[0] if amts else 0
            co = round(total * 0.5, 2)
            per = round(total * 0.5, 2)
        total = round(co + per, 2)
        return ("支付住房公积金", [
            _make_entry("6602", debit=co, summary="公积金（公司部分）"),
            _make_entry("1221", debit=per, summary="公积金（个人代扣）"),
            _make_entry("1002", credit=total, summary="银行存款支付"),
        ])

    # 内置规则列表: (pattern, handler, confidence)
    builtin_complex_rules = [
        (_re.compile(r'(采购|购买|购入)(材料|原材料|商品|货物).{0,15}(运费|运输|物流|装卸)'), _rule_purchase_freight, 0.94),
        (_re.compile(r'(销售|卖出|出售|销)(商品|货物|产品).{0,15}(折扣|折让|优惠|返利)'), _rule_sale_discount, 0.94),
        (_re.compile(r'(发放|发).{0,10}(工资|薪酬).{0,15}(代扣|扣除|个税|所得税)'), _rule_salary_tax, 0.93),
        (_re.compile(r'(支付|交|缴).{0,10}(社保|社会保险|养老保险|医疗保险)'), _rule_social_insurance, 0.92),
        (_re.compile(r'(支付|交|缴).{0,10}(公积金|住房公积金)'), _rule_housing_fund, 0.92),
        (_re.compile(r'(处置|出售|卖出|清理|报废).{0,15}(固定资产|设备|机器)'), _rule_fixed_asset_disposal, 0.91),
        (_re.compile(r'(建造|建设|施工|在建).{0,20}(完工|竣工|验收|转固)'), _rule_cip_transfer, 0.93),
        (_re.compile(r'(出口|外销|外贸).{0,20}(退税|出口退税|退税款)'), _rule_export_rebate, 0.90),
        (_re.compile(r'(采购|购买|购入).{0,15}(预付|预付款|先付|定金).{0,10}(货款|采购)'), _rule_prepay_purchase, 0.93),
        (_re.compile(r'(收到|收).{0,15}(预付|预收|定金|预付款)'), _rule_prepay_received, 0.93),
        (_re.compile(r'(利润|净利润).{0,15}(分配|分红|股利|派息)'), _rule_profit_dist, 0.93),
        (_re.compile(r'(计提|计算).{0,10}(所得税|企业所得税|所得)'), _rule_income_tax, 0.92),
        (_re.compile(r'(结转|转销|核销).{0,10}(坏账|坏账准备|减值)'), _rule_bad_debt, 0.92),
        (_re.compile(r'(收到|收).{0,10}(投资|注资|出资).{0,15}(设备|固定资产|资产)'), _rule_equity_fixed, 0.91),
    ]

    # 尝试内置规则匹配
    for pattern, handler, conf in builtin_complex_rules:
        if pattern.search(text):
            try:
                result = handler(text, amounts)
                if result:
                    desc, ents = result
                    total_dr = sum(e["debit"] for e in ents)
                    total_cr = sum(e["credit"] for e in ents)
                    if abs(total_dr - total_cr) < 0.02:
                        analysis["context_score"] = conf
                        return {
                            "description": desc, "entries": ents,
                            "confidence": conf, "composite": True,
                            "matched_rule": f"builtin:{pattern.pattern[:30]}",
                            "analysis": analysis,
                        }
            except Exception:
                continue

    # ── 3. 尝试 ai_rules_complex 表中的自定义规则 ──
    custom_rules = get_ai_rules_complex(active_only=True)
    for rule in custom_rules:
        try:
            if _re.search(rule["pattern"], text):
                ents_template = _json.loads(rule["entries_json"])
                # 简化: 将模板中的 amount_key 替换为 amounts 中的值
                ents = []
                for et in ents_template:
                    dr = 0
                    cr = 0
                    if "debit_key" in et and amounts:
                        key = et["debit_key"]
                        idx_map = {"material": 0, "freight": 1, "vat": 2, "gross": 0, "tax": 1,
                                   "net": 2, "company": 0, "personal": 1, "original": 0,
                                   "accumulated": 1, "proceeds": 2, "amount": 0, "cash": 1,
                                   "discount": 0, "total": 0, "revenue": 0, "rebate": 1}
                        idx = idx_map.get(key, 0)
                        dr = amounts[idx] if idx < len(amounts) else 0
                    elif "debit" in et:
                        dr = et["debit"]
                    if "credit_key" in et and amounts:
                        key = et["credit_key"]
                        idx_map2 = {"total": 0, "net": 2, "tax": 1, "amount": 0, "original": 0}
                        idx = idx_map2.get(key, 0)
                        cr = amounts[idx] if idx < len(amounts) else 0
                    elif "credit" in et:
                        cr = et["credit"]
                    ents.append(_make_entry(et["account_code"], debit=dr, credit=cr))
                if ents:
                    total_dr = sum(e["debit"] for e in ents)
                    total_cr = sum(e["credit"] for e in ents)
                    if abs(total_dr - total_cr) < 0.02:
                        analysis["context_score"] = 0.85
                        return {
                            "description": rule["description"], "entries": ents,
                            "confidence": 0.85, "composite": True,
                            "matched_rule": f"custom:{rule['name']}",
                            "analysis": analysis,
                        }
        except Exception:
            continue

    # ── 4. 回退到简单规则 ──
    simple_result = generate_voucher_from_text(ledger_id, text)
    simple_result["analysis"] = analysis
    simple_result["matched_rule"] = "simple_fallback"
    return simple_result

def search_vouchers(keyword, limit=10):
    """全局搜索凭证：按凭证号、摘要、金额模糊匹配"""
    conn = get_conn()
    kw = f"%{keyword}%"
    rows = conn.execute("""
        SELECT v.voucher_no, v.date, v.summary, v.total_debit, v.total_credit, v.status
        FROM vouchers v
        WHERE v.voucher_no LIKE ? OR v.summary LIKE ?
        ORDER BY v.date DESC, v.voucher_no DESC
        LIMIT ?
    """, (kw, kw, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def search_vouchers_by_aux(ledger_id, aux_type, aux_id, year=None, month=None):
    """按辅助核算查询凭证"""
    conn = get_conn()
    date_filter = ""
    params = [aux_id, aux_type, ledger_id]
    if year:
        date_filter += " AND strftime('%Y', v.date) = ?"
        params.append(str(year))
    if month:
        date_filter += " AND strftime('%m', v.date) = ?"
        params.append(f"{month:02d}")

    rows = conn.execute(
        "SELECT DISTINCT v.voucher_no, v.date, v.summary, v.total_debit, v.total_credit, v.status "
        "FROM vouchers v "
        "INNER JOIN journal_entries je ON je.voucher_no = v.voucher_no "
        "INNER JOIN voucher_entry_auxiliaries vea ON vea.entry_id = je.id "
        "WHERE vea.aux_id = ? AND vea.aux_type = ? AND v.ledger_id = ? " + date_filter + " "
        "ORDER BY v.date DESC, v.voucher_no DESC",
        params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def search_voucher_history_v2(ledger_id, keyword, limit=5):
    """搜索历史凭证：按摘要模糊匹配（Phase 2 版本，带 ledger_id 过滤）"""
    conn = get_conn()
    kw = f"%{keyword}%"
    rows = conn.execute("""
        SELECT DISTINCT v.description as summary,
               je.account_code, je.account_name,
               AVG(je.debit + je.credit) as avg_amount
        FROM vouchers v
        JOIN journal_entries je ON v.id = je.voucher_id
        WHERE v.ledger_id = ?
          AND v.description LIKE ?
          AND v.status = 'posted'
          AND je.debit + je.credit > 0
        GROUP BY v.description, je.account_code
        ORDER BY v.date DESC
        LIMIT ?
    """, (ledger_id, kw, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_voucher_template(ledger_id: int, name: str, entries: list, description: str = "", voucher_type: str = "记") -> int:
    """保存凭证模板"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO voucher_templates (ledger_id, name, description, voucher_type, entries) VALUES (?,?,?,?,?)",
        (ledger_id, name, description, voucher_type, _json_mod.dumps(entries, ensure_ascii=False))
    )
    conn.commit()
    tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return tid
