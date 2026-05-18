"""Database module: period domain"""

from .connection import get_conn, transaction, DB_PATH, clear_query_cache

def get_close_period_checklist(ledger_id, year, month) -> list:
    """获取期末结转检查清单（每项含名称/状态/描述）"""
    conn = get_conn()
    items = []

    # 1. 检查是否有未过账凭证
    unposted = conn.execute(
        "SELECT COUNT(*) as cnt FROM vouchers WHERE ledger_id=? AND status!='posted'",
        (ledger_id,)
    ).fetchone()["cnt"]
    items.append({"name": "所有凭证已过账", "ok": unposted == 0,
                  "desc": f"有 {unposted} 张凭证未过账" if unposted else "所有凭证已过账"})

    # 2. 检查借贷平衡
    imbalance = conn.execute(
        "SELECT v.id, v.voucher_no, v.total_debit, v.total_credit "
        "FROM vouchers v WHERE v.ledger_id=? AND v.status='posted' "
        "AND ABS(v.total_debit - v.total_credit) > 0.01",
        (ledger_id,)
    ).fetchall()
    items.append({"name": "借贷平衡检查", "ok": len(imbalance) == 0,
                  "desc": f"{len(imbalance)} 张凭证借贷不平衡" if imbalance else "全部平衡"})

    # 3. 检查损益科目余额
    revenue = conn.execute(
        "SELECT COALESCE(SUM(je.credit - je.debit), 0) as bal "
        "FROM journal_entries je JOIN vouchers v ON je.voucher_id=v.id "
        "WHERE v.ledger_id=? AND v.status='posted' "
        "AND je.account_code LIKE '6%' AND strftime('%Y-%m', v.date) <= ?",
        (ledger_id, f"{year}-{month:02d}")
    ).fetchone()["bal"]
    items.append({"name": "损益科目余额", "ok": True,
                  "desc": f"收入类余额 ¥{revenue:,.2f}，将结转至本年利润"})

    # 4. 检查期间状态
    period_status = get_period_status(ledger_id, year, month)
    items.append({"name": "期间状态", "ok": period_status != "closed",
                  "desc": f"当前状态: {period_status}"})

    conn.close()
    return items

def close_period(ledger_id, year, month, user_id=None, operator_name=None):
    """
    期末损益结转：将所有收入/费用科目余额转入"本年利润"
    生成结转凭证，原收入/费用科目余额归零
    返回结转凭证号，如果没有损益需要结转则返回 None
    """
    import calendar

    conn = get_conn()
    try:
        with transaction(conn):
            # 检查是否已结转
            existing = conn.execute(
                "SELECT id FROM vouchers WHERE ledger_id = ? AND description LIKE ? AND status = 'posted'",
                (ledger_id, f"%结转{year}年{month}月损益%")
            ).fetchone()
            if existing:
                raise ValueError(f"{year}年{month}月已执行过损益结转")

            # 计算各收入/费用科目的本期净额
            # 收入净额 = SUM(credit) - SUM(debit) （贷增借减 → 贷方正数为收入）
            # 费用净额 = SUM(debit) - SUM(credit) （借增贷减 → 借方正数为费用）
            income_expense = conn.execute("""
                SELECT a.code, a.name, a.category,
                       COALESCE(SUM(je.debit), 0) AS total_dr,
                       COALESCE(SUM(je.credit), 0) AS total_cr
                FROM accounts a
                LEFT JOIN journal_entries je ON je.account_code = a.code AND je.ledger_id = ?
                LEFT JOIN vouchers v ON je.voucher_id = v.id AND v.status = 'posted'
                    AND strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) = ?
                WHERE a.category IN ('收入', '费用') AND a.is_active = 1
                GROUP BY a.code
                ORDER BY a.category DESC, a.code
            """, (ledger_id, str(year), month)).fetchall()

            entries = []
            total_income = 0
            total_expense = 0

            for row in income_expense:
                dr = row["total_dr"]
                cr = row["total_cr"]
                if row["category"] == "收入":
                    # 收入净额 = 贷方 - 借方（贷增借减）
                    net = round(cr - dr, 2)
                    if abs(net) > 0.001:
                        # 结转收入：借记收入（冲减贷方余额），贷记本年利润
                        entries.append({
                            "account_code": row["code"],
                            "account_name": row["name"],
                            "debit": net,
                            "credit": 0,
                            "summary": f"结转{year}年{month}月收入",
                        })
                        total_income += net
                elif row["category"] == "费用":
                    # 费用净额 = 借方 - 贷方（借增贷减）
                    net = round(dr - cr, 2)
                    if abs(net) > 0.001:
                        # 结转费用：借记本年利润，贷记费用（冲减借方余额）
                        entries.append({
                            "account_code": row["code"],
                            "account_name": row["name"],
                            "debit": 0,
                            "credit": net,
                            "summary": f"结转{year}年{month}月费用",
                        })
                        total_expense += net

            net_profit = total_income - total_expense

            # 本年利润条目
            if abs(net_profit) > 0.001:
                if net_profit > 0:
                    # 盈利：贷记本年利润
                    entries.append({
                        "account_code": "4103",
                        "account_name": "本年利润",
                        "debit": 0,
                        "credit": round(net_profit, 2),
                        "summary": f"结转{year}年{month}月利润",
                    })
                else:
                    # 亏损：借记本年利润
                    entries.append({
                        "account_code": "4103",
                        "account_name": "本年利润",
                        "debit": round(-net_profit, 2),
                        "credit": 0,
                        "summary": f"结转{year}年{month}月亏损",
                    })

            if not entries:
                return None

            # 验证借贷平衡
            total_dr = sum(e["debit"] for e in entries)
            total_cr = sum(e["credit"] for e in entries)
            if abs(total_dr - total_cr) > 0.01:
                raise ValueError(f"结转凭证借贷不平衡：借方 {total_dr} ≠ 贷方 {total_cr}")

            # 使用当月最后一天作为结转凭证日期
            last_day = calendar.monthrange(year, month)[1]
            date_str = f"{year}-{month:02d}-{last_day:02d}"
            prefix = f"JZ{date_str.replace('-', '')}"
            count = conn.execute(
                "SELECT COUNT(*) FROM vouchers WHERE voucher_no LIKE ? AND ledger_id = ?",
                (prefix + "%", ledger_id)
            ).fetchone()[0]
            voucher_no = f"{prefix}{count+1:04d}"

            # 创建结转凭证
            cur = conn.execute(
                "INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status) VALUES (?,?,?,?,?,?,?)",
                (ledger_id, voucher_no, date_str,
                 f"结转{year}年{month}月损益",
                 total_dr, total_cr, "posted")
            )
            voucher_id = cur.lastrowid

            for e in entries:
                conn.execute(
                    "INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary) VALUES (?,?,?,?,?,?,?)",
                    (ledger_id, voucher_id, e["account_code"], e["account_name"], e["debit"], e["credit"], e["summary"])
                )

            # 审计日志
            add_audit_log(
                ledger_id=ledger_id,
                action="close_period",
                detail=f"结转{year}年{month}月损益 {voucher_no} 净利润={net_profit:,.2f}",
                voucher_id=voucher_id,
                user_id=user_id,
                operator_name=operator_name,
                module="period",
                target_table="vouchers",
                target_id=voucher_id,
                remark=f"{year}-{month}月结转 净利润:{net_profit:,.2f}元",
                conn=conn,
            )

        return voucher_no
    finally:
        conn.close()

def get_period_status(ledger_id, year, month):
    """获取会计期间状态（是否已结转）"""
    conn = get_conn()
    row = conn.execute(
        "SELECT voucher_no, created_at FROM vouchers WHERE ledger_id = ? AND description LIKE ? AND status = 'posted' ORDER BY date DESC LIMIT 1",
        (ledger_id, f"%结转{year}年{month}月损益%")
    ).fetchone()
    conn.close()
    if row:
        return {"closed": True, "voucher_no": row["voucher_no"], "closed_at": row["created_at"]}
    return {"closed": False, "voucher_no": None, "closed_at": None}

def reverse_close_period(ledger_id, year, month):
    """反结账"""
    period = f"{year}-{month:02d}"
    conn = get_conn()
    
    # 检查下一期间是否已结账
    if month < 12:
        next_period = f"{year}-{month+1:02d}"
    else:
        next_period = f"{year+1}-01"
    
    next_closed = conn.execute("""
        SELECT COUNT(*) as cnt FROM closing_entries
        WHERE ledger_id = ? AND period = ? AND status = 'completed'
    """, (ledger_id, next_period)).fetchone()['cnt']
    
    if next_closed > 0:
        conn.close()
        return {'success': False, 'message': f'下一期间 {next_period} 已结账，无法反结账'}
    
    # 删除结转记录
    conn.execute("DELETE FROM closing_entries WHERE ledger_id = ? AND period = ?",
                 (ledger_id, period))
    
    conn.commit()
    conn.close()
    clear_query_cache()

def set_opening_balance(ledger_id, account_code, year, month, balance):
    """设置科目期初余额"""
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO opening_balances (ledger_id, account_code, year, month, balance)
        VALUES (?,?,?,?,?)
    """, (ledger_id, account_code, year, month, balance))
    conn.commit()
    conn.close()
    clear_query_cache()

def get_opening_balance(ledger_id, account_code, year, month):
    """获取科目期初余额：返回小于等于查询月份的最近一条期初余额"""
    conn = get_conn()
    row = conn.execute("""
        SELECT balance FROM opening_balances
        WHERE ledger_id = ? AND account_code = ?
          AND (year < ? OR (year = ? AND month <= ?))
        ORDER BY year DESC, month DESC
        LIMIT 1
    """, (ledger_id, account_code, year, year, month)).fetchone()
    conn.close()
    return row["balance"] if row else 0
