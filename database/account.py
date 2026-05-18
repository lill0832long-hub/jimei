"""Database module: account domain"""

from .connection import get_conn, release_conn, transaction, DB_PATH, clear_query_cache

def get_account_balances(ledger_id, year, month) -> list[dict]:
    """科目余额表 — 6列金额：期初借贷/本期借贷/本年累计借贷/期末借贷"""
    conn = get_conn()
    accounts = conn.execute("""
        SELECT a.*, p.name as parent_name
        FROM accounts a
        LEFT JOIN accounts p ON a.parent_code = p.code
        WHERE a.is_active = 1
        ORDER BY a.code
    """).fetchall()
    results = []

    for acc in accounts:
        code = acc["code"]
        cat = acc["category"]

        # 年初余额（手动设置的期初）
        opening = get_opening_balance(ledger_id, code, year, month)

        # 年初到上月末的累计发生额
        prev = conn.execute("""
            SELECT COALESCE(SUM(je.debit), 0) AS dr, COALESCE(SUM(je.credit), 0) AS cr
            FROM journal_entries je
            JOIN vouchers v ON je.voucher_id = v.id AND v.status = 'posted'
            WHERE je.ledger_id = ? AND je.account_code = ?
            AND (strftime('%Y', v.date) < ? OR (strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) < ?))
        """, (ledger_id, code, str(year), str(year), month)).fetchone()
        prev_dr = prev["dr"] if prev else 0
        prev_cr = prev["cr"] if prev else 0

        # 本期（当月）发生额
        curr = conn.execute("""
            SELECT COALESCE(SUM(je.debit), 0) AS dr, COALESCE(SUM(je.credit), 0) AS cr
            FROM journal_entries je
            JOIN vouchers v ON je.voucher_id = v.id AND v.status = 'posted'
            WHERE je.ledger_id = ? AND je.account_code = ?
            AND strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) = ?
        """, (ledger_id, code, str(year), month)).fetchone()
        curr_dr = curr["dr"] if curr else 0
        curr_cr = curr["cr"] if curr else 0

        # 本年累计发生额（年初到当月）
        ytd_dr = prev_dr + curr_dr
        ytd_cr = prev_cr + curr_cr

        # 计算期初余额的借贷方向
        if cat in ("资产", "费用"):
            # 借增贷减：借方余额为正
            net_opening = opening + prev_dr - prev_cr
            opening_dr = round(net_opening, 2) if net_opening > 0 else 0
            opening_cr = round(-net_opening, 2) if net_opening < 0 else 0
        else:
            # 贷增借减：贷方余额为正
            net_opening = opening + prev_cr - prev_dr
            opening_cr = round(net_opening, 2) if net_opening > 0 else 0
            opening_dr = round(-net_opening, 2) if net_opening < 0 else 0

        # 计算期末余额的借贷方向
        if cat in ("资产", "费用"):
            net_closing = opening_dr - opening_cr + curr_dr - curr_cr
            closing_dr = round(net_closing, 2) if net_closing > 0 else 0
            closing_cr = round(-net_closing, 2) if net_closing < 0 else 0
        else:
            net_closing = opening_cr - opening_dr + curr_cr - curr_dr
            closing_cr = round(net_closing, 2) if net_closing > 0 else 0
            closing_dr = round(-net_closing, 2) if net_closing < 0 else 0

        # 层级
        level = 2 if acc["parent_code"] else 1

        # 只显示有数据的科目
        if any(v > 0.001 for v in [opening_dr, opening_cr, curr_dr, curr_cr, ytd_dr, ytd_cr, closing_dr, closing_cr]):
            results.append({
                "code": code, "name": acc["name"],
                "category": cat,
                "sub_category": acc["sub_category"] if "sub_category" in acc.keys() else "",
                "parent_code": acc["parent_code"],
                "level": level,
                "opening_dr": opening_dr, "opening_cr": opening_cr,
                "curr_dr": round(curr_dr, 2), "curr_cr": round(curr_cr, 2),
                "ytd_dr": round(ytd_dr, 2), "ytd_cr": round(ytd_cr, 2),
                "closing_dr": closing_dr, "closing_cr": closing_cr,
            })

    conn.close()

    # 添加合计行
    if results:
        total = {
            "code": "", "name": "合 计", "category": "", "sub_category": "",
            "parent_code": None, "level": 0,
            "opening_dr": round(sum(r["opening_dr"] for r in results), 2),
            "opening_cr": round(sum(r["opening_cr"] for r in results), 2),
            "curr_dr": round(sum(r["curr_dr"] for r in results), 2),
            "curr_cr": round(sum(r["curr_cr"] for r in results), 2),
            "ytd_dr": round(sum(r["ytd_dr"] for r in results), 2),
            "ytd_cr": round(sum(r["ytd_cr"] for r in results), 2),
            "closing_dr": round(sum(r["closing_dr"] for r in results), 2),
            "closing_cr": round(sum(r["closing_cr"] for r in results), 2),
        }
        results.append(total)

    return results

def get_accounts(category=None):
    conn = get_conn()
    if category:
        rows = conn.execute("SELECT * FROM accounts WHERE category = ? AND is_active = 1 ORDER BY code", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM accounts WHERE is_active = 1 ORDER BY code").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_account(code, name, category, sub_category=None, parent_code=None):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO accounts (code, name, category, sub_category, parent_code) VALUES (?,?,?,?,?)",
        (code, name, category, sub_category, parent_code)
    )
    conn.commit()
    conn.close()
    clear_query_cache()

def search_accounts_by_kw(keyword, limit=10):
    """全局搜索科目：按科目编码、名称模糊匹配"""
    conn = get_conn()
    kw = f"%{keyword}%"
    rows = conn.execute("""
        SELECT code, name, category, sub_category, is_active
        FROM accounts
        WHERE is_active = 1 AND (code LIKE ? OR name LIKE ?)
        ORDER BY code
        LIMIT ?
    """, (kw, kw, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_bank_account(bank_id, **kwargs):
    """更新银行账户信息"""
    allowed = {"account_no", "bank_name", "account_name", "currency_code", "subject_code", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn = get_conn()
    conn.execute(f"UPDATE bank_accounts SET {set_clause} WHERE id = ?",
                 list(updates.values()) + [bank_id])
    conn.commit()
    conn.close()
    clear_query_cache()

def delete_bank_account(bank_id):
    """软删除银行账户"""
    conn = get_conn()
    conn.execute("UPDATE bank_accounts SET is_active = 0 WHERE id = ?", (bank_id,))
    conn.commit()
    conn.close()
    clear_query_cache()

def create_bank_account(ledger_id, account_no, bank_name, account_name=None,
                        currency_code='CNY', opening_balance=0, subject_code=None):
    """创建银行账户"""
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO bank_accounts (ledger_id, account_no, bank_name, account_name,
                                   currency_code, opening_balance, current_balance, subject_code)
        VALUES (?,?,?,?,?,?,?,?)
    """, (ledger_id, account_no, bank_name, account_name or bank_name,
          currency_code, opening_balance, opening_balance, subject_code))
    bank_id = cur.lastrowid
    conn.commit()
    conn.close()
    clear_query_cache()
    return bank_id

def get_bank_accounts(ledger_id):
    """获取银行账户列表"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM bank_accounts WHERE ledger_id = ? AND is_active = 1 ORDER BY bank_name",
        (ledger_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def import_bank_statement(bank_account_id, rows):
    """导入银行对账单
    rows: list of {statement_date, transaction_date, summary, debit, credit, reference_no}
    debit=银行借方(企业收入), credit=银行贷方(企业支出)
    """
    conn = get_conn()
    imported = 0
    for row in rows:
        conn.execute("""
            INSERT INTO bank_statements (bank_account_id, statement_date, transaction_date, summary, debit, credit, reference_no)
            VALUES (?,?,?,?,?,?,?)
        """, (bank_account_id, row.get('statement_date'), row.get('transaction_date'),
              row.get('summary', ''), int(row.get('debit') or 0), int(row.get('credit') or 0),
              row.get('reference_no', '')))
        imported += 1
    conn.commit()
    release_conn(conn)
    clear_query_cache()
    return imported

def get_default_accounts(system_type="small_business"):
    """返回预设科目列表
    system_type: 'small_business'=小企业会计准则, 'enterprise'=企业会计准则
    """
    small_business = [
        ("1001", "库存现金", "资产", "流动资产", None),
        ("1002", "银行存款", "资产", "流动资产", None),
        ("100201", "银行存款-基本户", "资产", "流动资产", "1002"),
        ("100202", "银行存款-一般户", "资产", "流动资产", "1002"),
        ("1101", "短期投资", "资产", "流动资产", None),
        ("1121", "应收票据", "资产", "流动资产", None),
        ("1122", "应收账款", "资产", "流动资产", None),
        ("1123", "预付账款", "资产", "流动资产", None),
        ("1221", "其他应收款", "资产", "流动资产", None),
        ("1401", "材料采购", "资产", "流动资产", None),
        ("1403", "原材料", "资产", "流动资产", None),
        ("1405", "库存商品", "资产", "流动资产", None),
        ("1411", "周转材料", "资产", "流动资产", None),
        ("1601", "固定资产", "资产", "非流动资产", None),
        ("1602", "累计折旧", "资产", "非流动资产", None),
        ("1604", "在建工程", "资产", "非流动资产", None),
        ("1701", "无形资产", "资产", "非流动资产", None),
        ("1702", "累计摊销", "资产", "非流动资产", None),
        ("1801", "长期待摊费用", "资产", "非流动资产", None),
        ("1901", "待处理财产损溢", "资产", "流动资产", None),
        ("2001", "短期借款", "负债", "流动负债", None),
        ("2201", "应付票据", "负债", "流动负债", None),
        ("2202", "应付账款", "负债", "流动负债", None),
        ("2203", "预收账款", "负债", "流动负债", None),
        ("2211", "应付职工薪酬", "负债", "流动负债", None),
        ("2221", "应交税费", "负债", "流动负债", None),
        ("222101", "应交增值税", "负债", "流动负债", "2221"),
        ("222102", "应交所得税", "负债", "流动负债", "2221"),
        ("222103", "应交城市维护建设税", "负债", "流动负债", "2221"),
        ("222104", "应交教育费附加", "负债", "流动负债", "2221"),
        ("2231", "应付利息", "负债", "流动负债", None),
        ("2232", "应付股利", "负债", "流动负债", None),
        ("2241", "其他应付款", "负债", "流动负债", None),
        ("2501", "长期借款", "负债", "非流动负债", None),
        ("2701", "长期应付款", "负债", "非流动负债", None),
        ("3001", "实收资本", "权益", "所有者权益", None),
        ("3002", "资本公积", "权益", "所有者权益", None),
        ("3101", "盈余公积", "权益", "所有者权益", None),
        ("3103", "本年利润", "权益", "所有者权益", None),
        ("3104", "利润分配", "权益", "所有者权益", None),
        ("4001", "生产成本", "费用", "营业成本", None),
        ("4101", "制造费用", "费用", "营业成本", None),
        ("5001", "主营业务收入", "收入", "营业收入", None),
        ("5051", "其他业务收入", "收入", "营业收入", None),
        ("5111", "投资收益", "收入", "营业外收入", None),
        ("5301", "营业外收入", "收入", "营业外收入", None),
        ("5401", "主营业务成本", "费用", "营业成本", None),
        ("5402", "其他业务成本", "费用", "营业成本", None),
        ("5403", "税金及附加", "费用", "营业成本", None),
        ("5601", "销售费用", "费用", "期间费用", None),
        ("5602", "管理费用", "费用", "期间费用", None),
        ("560201", "管理费用-差旅费", "费用", "期间费用", "5602"),
        ("560202", "管理费用-办公费", "费用", "期间费用", "5602"),
        ("560203", "管理费用-工资", "费用", "期间费用", "5602"),
        ("560204", "管理费用-折旧费", "费用", "期间费用", "5602"),
        ("5603", "财务费用", "费用", "期间费用", None),
        ("5711", "营业外支出", "费用", "营业外支出", None),
        ("5801", "所得税费用", "费用", "期间费用", None),
    ]

    enterprise = [
        ("1001", "库存现金", "资产", "流动资产", None),
        ("1002", "银行存款", "资产", "流动资产", None),
        ("100201", "银行存款-基本户", "资产", "流动资产", "1002"),
        ("100202", "银行存款-一般户", "资产", "流动资产", "1002"),
        ("1012", "其他货币资金", "资产", "流动资产", None),
        ("1101", "交易性金融资产", "资产", "流动资产", None),
        ("1121", "应收票据", "资产", "流动资产", None),
        ("1122", "应收账款", "资产", "流动资产", None),
        ("1123", "预付账款", "资产", "流动资产", None),
        ("1131", "应收股利", "资产", "流动资产", None),
        ("1132", "应收利息", "资产", "流动资产", None),
        ("1221", "其他应收款", "资产", "流动资产", None),
        ("1401", "材料采购", "资产", "流动资产", None),
        ("1402", "在途物资", "资产", "流动资产", None),
        ("1403", "原材料", "资产", "流动资产", None),
        ("1405", "库存商品", "资产", "流动资产", None),
        ("1406", "发出商品", "资产", "流动资产", None),
        ("1408", "委托加工物资", "资产", "流动资产", None),
        ("1471", "存货跌价准备", "资产", "流动资产", None),
        ("1601", "固定资产", "资产", "非流动资产", None),
        ("1602", "累计折旧", "资产", "非流动资产", None),
        ("1603", "固定资产减值准备", "资产", "非流动资产", None),
        ("1604", "在建工程", "资产", "非流动资产", None),
        ("1701", "无形资产", "资产", "非流动资产", None),
        ("1702", "累计摊销", "资产", "非流动资产", None),
        ("1801", "长期待摊费用", "资产", "非流动资产", None),
        ("1901", "待处理财产损溢", "资产", "流动资产", None),
        ("2001", "短期借款", "负债", "流动负债", None),
        ("2101", "交易性金融负债", "负债", "流动负债", None),
        ("2201", "应付票据", "负债", "流动负债", None),
        ("2202", "应付账款", "负债", "流动负债", None),
        ("2203", "预收账款", "负债", "流动负债", None),
        ("2211", "应付职工薪酬", "负债", "流动负债", None),
        ("2221", "应交税费", "负债", "流动负债", None),
        ("222101", "应交增值税", "负债", "流动负债", "2221"),
        ("222102", "应交所得税", "负债", "流动负债", "2221"),
        ("222103", "应交城市维护建设税", "负债", "流动负债", "2221"),
        ("222104", "应交教育费附加", "负债", "流动负债", "2221"),
        ("2231", "应付利息", "负债", "流动负债", None),
        ("2232", "应付股利", "负债", "流动负债", None),
        ("2241", "其他应付款", "负债", "流动负债", None),
        ("2501", "长期借款", "负债", "非流动负债", None),
        ("2502", "应付债券", "负债", "非流动负债", None),
        ("2701", "长期应付款", "负债", "非流动负债", None),
        ("4001", "实收资本", "权益", "所有者权益", None),
        ("4002", "资本公积", "权益", "所有者权益", None),
        ("4101", "盈余公积", "权益", "所有者权益", None),
        ("4103", "本年利润", "权益", "所有者权益", None),
        ("4104", "利润分配", "权益", "所有者权益", None),
        ("5001", "生产成本", "费用", "营业成本", None),
        ("5101", "制造费用", "费用", "营业成本", None),
        ("5201", "劳务成本", "费用", "营业成本", None),
        ("6001", "主营业务收入", "收入", "营业收入", None),
        ("6051", "其他业务收入", "收入", "营业收入", None),
        ("6111", "投资收益", "收入", "营业外收入", None),
        ("6301", "营业外收入", "收入", "营业外收入", None),
        ("6601", "公允价值变动损益", "收入", "营业外收入", None),
        ("6401", "主营业务成本", "费用", "营业成本", None),
        ("6402", "其他业务成本", "费用", "营业成本", None),
        ("6403", "税金及附加", "费用", "营业成本", None),
        ("6601", "销售费用", "费用", "期间费用", None),
        ("6602", "管理费用", "费用", "期间费用", None),
        ("660201", "管理费用-差旅费", "费用", "期间费用", "6602"),
        ("660202", "管理费用-办公费", "费用", "期间费用", "6602"),
        ("660203", "管理费用-工资", "费用", "期间费用", "6602"),
        ("660204", "管理费用-折旧费", "费用", "期间费用", "6602"),
        ("6603", "财务费用", "费用", "期间费用", None),
        ("6701", "资产减值损失", "费用", "期间费用", None),
        ("6711", "营业外支出", "费用", "营业外支出", None),
        ("6801", "所得税费用", "费用", "期间费用", None),
    ]

    if system_type == "enterprise":
        return enterprise
    return small_business

def import_accounts_from_template(ledger_id, system_type="small_business"):
    """从模板导入预设科目"""
    accounts = get_default_accounts(system_type)
    conn = get_conn()
    imported = 0
    for acc in accounts:
        code, name, cat, sub, parent = acc
        try:
            conn.execute(
                "INSERT OR IGNORE INTO accounts (code, name, category, sub_category, parent_code) VALUES (?,?,?,?,?)",
                (code, name, cat, sub, parent)
            )
            imported += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    clear_query_cache()
    return imported

def get_account_suggestions(ledger_id, keyword, limit=5):
    """根据摘要关键词推荐科目"""
    keyword_map = {
        "差旅": ["560201", "660201"],
        "办公": ["560202", "660202"],
        "工资": ["560203", "660203", "2211"],
        "折旧": ["560204", "660204", "1602"],
        "租金": ["5602", "6602"],
        "水电": ["5602", "6602"],
        "银行": ["1002", "5603", "6603"],
        "利息": ["5603", "6603"],
        "销售": ["5601", "6601"],
        "广告": ["5601", "6601"],
        "采购": ["1401", "1403", "5001", "6401"],
        "存货": ["1405", "5001", "6401"],
        "收入": ["5001", "6001"],
        "收款": ["1002", "1122"],
        "付款": ["1002", "2202"],
        "税费": ["2221", "5403", "6403"],
        "所得税": ["5801", "6801"],
        "固定资产": ["1601", "1602"],
        "借款": ["2001", "2501"],
    }

    matched_codes = set()
    for kw, codes in keyword_map.items():
        if kw in keyword:
            matched_codes.update(codes)

    if not matched_codes:
        return []

    conn = get_conn()
    placeholders = ",".join(["?" for _ in matched_codes])
    rows = conn.execute(f"""
        SELECT code, name, category FROM accounts
        WHERE code IN ({placeholders}) AND is_active = 1
        ORDER BY code
        LIMIT ?
    """, list(matched_codes) + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_avg_amount_for_account(ledger_id, account_code, months=3):
    """获取某科目最近 N 个月的平均发生金额"""
    conn = get_conn()
    row = conn.execute("""
        SELECT AVG(je.debit + je.credit) as avg_amount
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND je.account_code = ?
          AND v.status = 'posted'
          AND v.date >= date('now', ?)
    """, (ledger_id, account_code, f"-{months} months")).fetchone()
    conn.close()
    return row["avg_amount"] if row and row["avg_amount"] else 0

def auto_match_bank_statement(bank_account_id):
    """自动银行对账（按金额+日期匹配）"""
    conn = get_conn()
    statements = conn.execute("""
        SELECT * FROM bank_statements 
        WHERE bank_account_id = ? AND is_matched = 0
        ORDER BY transaction_date
    """, (bank_account_id,)).fetchall()
    
    matched = 0
    for stmt in statements:
        stmt_amount = stmt['debit'] - stmt['credit']  # 银行视角
        # 查找匹配的凭证分录
        entries = conn.execute("""
            SELECT je.* FROM journal_entries je
            JOIN vouchers v ON je.voucher_id = v.id
            WHERE v.ledger_id = (SELECT ledger_id FROM bank_accounts WHERE id = ?)
            AND v.date = ?
            AND ((je.debit = ? AND ? > 0) OR (je.credit = ? AND ? < 0))
            LIMIT 1
        """, (bank_account_id, stmt['transaction_date'],
              stmt['debit'], stmt['debit'], stmt['credit'], stmt['credit'])).fetchall()
        
        if entries:
            conn.execute("UPDATE bank_statements SET is_matched = 1 WHERE id = ?", (stmt['id'],))
            matched += 1

    conn.commit()
    release_conn(conn)
    clear_query_cache()
    return matched

def get_bank_reconciliation(bank_account_id, period):
    """获取余额调节表数据"""
    conn = get_conn()
    
    # 银行对账单余额
    bank_balance = conn.execute("""
        SELECT COALESCE(SUM(debit - credit), 0) as balance
        FROM bank_statements WHERE bank_account_id = ?
    """, (bank_account_id,)).fetchone()['balance']
    
    # 企业账面余额
    book_balance = conn.execute("""
        SELECT current_balance FROM bank_accounts WHERE id = ?
    """, (bank_account_id,)).fetchone()['current_balance']
    
    # 银行已收企业未收
    bank_recv_not_book = conn.execute("""
        SELECT COALESCE(SUM(debit), 0) as total
        FROM bank_statements WHERE bank_account_id = ? AND is_matched = 0 AND debit > 0
    """, (bank_account_id,)).fetchone()['total']
    
    # 银行已付企业未付
    bank_pay_not_book = conn.execute("""
        SELECT COALESCE(SUM(credit), 0) as total
        FROM bank_statements WHERE bank_account_id = ? AND is_matched = 0 AND credit > 0
    """, (bank_account_id,)).fetchone()['total']
    
    conn.close()
    
    adjusted_bank = bank_balance + bank_recv_not_book - bank_pay_not_book
    
    return {
        'bank_balance': bank_balance,
        'book_balance': book_balance,
        'bank_recv_not_book': bank_recv_not_book,
        'bank_pay_not_book': bank_pay_not_book,
        'adjusted_bank_balance': adjusted_bank,
        'difference': book_balance - adjusted_bank
    }

def match_bank_statement(stmt_id, journal_id):
    """手动匹配"""
    conn = get_conn()
    conn.execute("UPDATE bank_statements SET is_matched = 1, matched_journal_id = ? WHERE id = ?",
                 (journal_id, stmt_id))
    conn.commit()
    conn.close()
    clear_query_cache()

def unmatch_bank_statement(stmt_id):
    """取消匹配"""
    conn = get_conn()
    conn.execute("UPDATE bank_statements SET is_matched = 0, matched_journal_id = NULL WHERE id = ?",
                 (stmt_id,))
    conn.commit()
    conn.close()
    clear_query_cache()

def get_unmatched_items(bank_account_id):
    """获取未达账项"""
    conn = get_conn()
    bank_recv = conn.execute("""
        SELECT * FROM bank_statements
        WHERE bank_account_id = ? AND is_matched = 0 AND debit > 0
        ORDER BY transaction_date
    """, (bank_account_id,)).fetchall()
    bank_pay = conn.execute("""
        SELECT * FROM bank_statements
        WHERE bank_account_id = ? AND is_matched = 0 AND credit > 0
        ORDER BY transaction_date
    """, (bank_account_id,)).fetchall()
    book_recv = conn.execute("""
        SELECT je.*, v.voucher_no, v.date as voucher_date, v.description
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN bank_accounts ba ON ba.ledger_id = je.ledger_id
        WHERE ba.id = ? AND je.debit > 0
          AND je.account_code = ba.subject_code
          AND v.status = 'posted'
          AND je.id NOT IN (
              SELECT matched_journal_id FROM bank_statements
              WHERE bank_account_id = ? AND matched_journal_id IS NOT NULL
          )
        ORDER BY v.date
    """, (bank_account_id, bank_account_id)).fetchall()
    book_pay = conn.execute("""
        SELECT je.*, v.voucher_no, v.date as voucher_date, v.description
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN bank_accounts ba ON ba.ledger_id = je.ledger_id
        WHERE ba.id = ? AND je.credit > 0
          AND je.account_code = ba.subject_code
          AND v.status = 'posted'
          AND je.id NOT IN (
              SELECT matched_journal_id FROM bank_statements
              WHERE bank_account_id = ? AND matched_journal_id IS NOT NULL
          )
        ORDER BY v.date
    """, (bank_account_id, bank_account_id)).fetchall()
    conn.close()
    return {
        "bank_recv_not_book": [dict(r) for r in bank_recv],
        "bank_pay_not_book": [dict(r) for r in bank_pay],
        "book_recv_not_bank": [dict(r) for r in book_recv],
        "book_pay_not_bank": [dict(r) for r in book_pay],
    }

def get_bank_statements_list(bank_account_id, matched=None):
    """获取银行对账单列表"""
    conn = get_conn()
    query = "SELECT * FROM bank_statements WHERE bank_account_id = ?"
    params = [bank_account_id]
    if matched is not None:
        query += " AND is_matched = ?"
        params.append(1 if matched else 0)
    query += " ORDER BY transaction_date DESC, id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
