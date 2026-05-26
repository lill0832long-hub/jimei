"""Database module: cash_flow domain"""

from .connection import get_conn, transaction, DB_PATH, clear_query_cache

def get_cash_flow_categories(ledger_id: int) -> list:
    """获取现金流分类列表"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM cash_flow_categories WHERE ledger_id = ? AND is_active = 1 ORDER BY category, code",
            (ledger_id,)
        ).fetchall()

    finally:
        conn.close()
        return [dict(r) for r in rows]


def add_cash_flow_category(ledger_id: int, code: str, name: str, category: str, parent_code: str = None):
    """添加现金流分类"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cash_flow_categories (ledger_id, code, name, category, parent_code) VALUES (?,?,?,?,?)",
            (ledger_id, code, name, category, parent_code)
        )
        conn.commit()

    finally:
        conn.close()
        clear_query_cache()


def get_cash_flow_statement(ledger_id: int, year: int, month: int, method: str = "direct") -> dict:
    """
    生成现金流量表
    method: 'direct' 直接法, 'indirect' 间接法
    """
    conn = get_conn()
    try:

        # ── 投资活动和筹资活动：两种方法通用，按现金流分类汇总 ──
        rows_cf = conn.execute(
            "SELECT je.cash_flow_type, "
            "SUM(CASE WHEN je.debit > 0 THEN je.debit ELSE 0 END) as total_debit, "
            "SUM(CASE WHEN je.credit > 0 THEN je.credit ELSE 0 END) as total_credit "
            "FROM journal_entries je "
            "JOIN vouchers v ON je.voucher_id = v.id "
            "WHERE v.ledger_id = ? AND v.status = 'posted' "
            "AND je.cash_flow_type != '' "
            "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ? "
            "GROUP BY je.cash_flow_type",
            (ledger_id, str(year), f"{month:02d}")
        ).fetchall()

        investing_inflow = 0; investing_outflow = 0
        financing_inflow = 0; financing_outflow = 0
        detail_rows = []

        for row in rows_cf:
            cf_type = row["cash_flow_type"]
            if cf_type.startswith("investing_"):
                if "inflow" in cf_type: investing_inflow += row["total_debit"]
                else: investing_outflow += row["total_credit"]
            elif cf_type.startswith("financing_"):
                if "inflow" in cf_type: financing_inflow += row["total_debit"]
                else: financing_outflow += row["total_credit"]

        # 若无现金流分类数据，用科目自动推断（投资/筹资）
        if not any(r["cash_flow_type"].startswith(("investing_", "financing_")) for r in rows_cf):
            for d in _infer_cash_flow(conn, ledger_id, year, month):
                if d["type"] == "investing_inflow":   investing_inflow += max(d["net"], 0)
                elif d["type"] == "investing_outflow": investing_outflow += abs(min(d["net"], 0))
                elif d["type"] == "financing_inflow":  financing_inflow += max(d["net"], 0)
                elif d["type"] == "financing_outflow": financing_outflow += abs(min(d["net"], 0))

        if method == "indirect":
            # ── D2: 间接法 — 经营活动从净利润出发调整 ──
            # 1. 净利润
            np_row = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN a.category='收入' THEN je.credit-je.debit ELSE 0 END), 0)"
                " - COALESCE(SUM(CASE WHEN a.category='费用' THEN je.debit-je.credit ELSE 0 END), 0) as np "
                "FROM journal_entries je "
                "JOIN vouchers v ON je.voucher_id = v.id "
                "JOIN accounts a ON a.code = je.account_code "
                "WHERE v.ledger_id=? AND v.status='posted' "
                "AND strftime('%Y',v.date)=? AND strftime('%m',v.date)=?",
                (ledger_id, str(year), f"{month:02d}")
            ).fetchone()
            net_profit = round(np_row["np"], 2) if np_row else 0.0

            # 2. 折旧费用
            dep_row = conn.execute(
                "SELECT COALESCE(SUM(je.debit),0) as total FROM journal_entries je "
                "JOIN vouchers v ON je.voucher_id=v.id "
                "WHERE v.ledger_id=? AND v.status='posted' "
                "AND strftime('%Y',v.date)=? AND strftime('%m',v.date)=? "
                "AND (je.account_name LIKE '%折旧%' OR je.account_code IN ('1602','1702'))",
                (ledger_id, str(year), f"{month:02d}")
            ).fetchone()
            depreciation = round(dep_row["total"], 2) if dep_row else 0.0

            # 3. 摊销费用
            amo_row = conn.execute(
                "SELECT COALESCE(SUM(je.debit),0) as total FROM journal_entries je "
                "JOIN vouchers v ON je.voucher_id=v.id "
                "WHERE v.ledger_id=? AND v.status='posted' "
                "AND strftime('%Y',v.date)=? AND strftime('%m',v.date)=? "
                "AND (je.account_name LIKE '%摊销%' OR je.account_code='1801')",
                (ledger_id, str(year), f"{month:02d}")
            ).fetchone()
            amortization = round(amo_row["total"], 2) if amo_row else 0.0

            # 4. 投资收益（减少经营现金流）
            inv_row = conn.execute(
                "SELECT COALESCE(SUM(je.credit-je.debit),0) as total FROM journal_entries je "
                "JOIN vouchers v ON je.voucher_id=v.id "
                "WHERE v.ledger_id=? AND v.status='posted' "
                "AND strftime('%Y',v.date)=? AND strftime('%m',v.date)=? "
                "AND je.account_name LIKE '%投资收益%'",
                (ledger_id, str(year), f"{month:02d}")
            ).fetchone()
            invest_income = round(inv_row["total"], 2) if inv_row else 0.0

            # 5. 间接法计算
            operating_cf = net_profit + depreciation + amortization - invest_income
            operating_inflow = max(operating_cf, 0)
            operating_outflow = abs(min(operating_cf, 0))

            # 间接法 detail 显示调整过程
            detail_rows.append({"type": "indirect_net_profit", "name": "净利润",
                                "section": "operating", "debit": net_profit, "credit": 0, "net": net_profit})
            if depreciation > 0:
                detail_rows.append({"type": "indirect_depreciation", "name": "加：折旧费用",
                                    "section": "operating", "debit": depreciation, "credit": 0, "net": depreciation})
            if amortization > 0:
                detail_rows.append({"type": "indirect_amortization", "name": "加：摊销费用",
                                    "section": "operating", "debit": amortization, "credit": 0, "net": amortization})
            if invest_income != 0:
                detail_rows.append({"type": "indirect_invest_income", "name": "减：投资收益",
                                    "section": "operating", "debit": 0, "credit": invest_income, "net": -invest_income})

            net_operating = operating_cf

            # 间接法也需添加投资/筹资活动的 detail 行
            for row in rows_cf:
                cf_type = row["cash_flow_type"]
                if cf_type.startswith(("investing_", "financing_")):
                    net = row["total_debit"] - row["total_credit"]
                    name_map = {
                        "investing_inflow": "投资活动现金流入", "investing_outflow": "投资活动现金流出",
                        "financing_inflow": "筹资活动现金流入", "financing_outflow": "筹资活动现金流出",
                    }
                    detail_rows.append({"type": cf_type, "name": name_map.get(cf_type, cf_type),
                                        "section": cf_type.split("_")[0], "debit": row["total_debit"],
                                        "credit": row["total_credit"], "net": net})

        else:
            # ── 直接法 — 按现金流分类汇总经营活动 ──
            operating_inflow = 0; operating_outflow = 0
            for row in rows_cf:
                cf_type = row["cash_flow_type"]
                if cf_type == "operating_inflow":   operating_inflow += row["total_debit"]
                elif cf_type == "operating_outflow": operating_outflow += row["total_credit"]

            # 若无经营类现金流数据，用科目自动推断
            if operating_inflow == 0 and operating_outflow == 0:
                for d in _infer_cash_flow(conn, ledger_id, year, month):
                    if d["type"] == "operating_inflow":   operating_inflow += max(d["net"], 0)
                    elif d["type"] == "operating_outflow": operating_outflow += abs(min(d["net"], 0))
                    detail_rows.append(d)

            # 添加经营类 detail
            for row in rows_cf:
                cf_type = row["cash_flow_type"]
                if cf_type.startswith("operating_"):
                    net = row["total_debit"] - row["total_credit"]
                    name = "经营活动现金流入" if "inflow" in cf_type else "经营活动现金流出"
                    detail_rows.append({"type": cf_type, "name": name, "section": "operating",
                                        "debit": row["total_debit"], "credit": row["total_credit"], "net": net})

            net_operating = operating_inflow - operating_outflow

        net_investing = investing_inflow - investing_outflow
        net_financing = financing_inflow - financing_outflow
        net_cash_change = net_operating + net_investing + net_financing


    finally:
        conn.close()

        return {
        "method": method,
        "year": year,
        "month": month,
        "operating": {"inflow": operating_inflow, "outflow": operating_outflow, "net": net_operating},
        "investing": {"inflow": investing_inflow, "outflow": investing_outflow, "net": net_investing},
        "financing": {"inflow": financing_inflow, "outflow": financing_outflow, "net": net_financing},
        "net_cash_change": net_cash_change,
        "detail": detail_rows,
    }

def _infer_cash_flow(conn, ledger_id: int, year: int, month: int) -> list:
    """基于科目自动推断现金流分类（简化版）"""
    # 现金类科目
    cash_accounts = ['1001', '1002', '1012']
    rows = conn.execute(
        "SELECT je.account_code, je.account_name, "
        "SUM(je.debit) as total_debit, SUM(je.credit) as total_credit "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' "
        "AND je.account_code IN ({}) "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ? "
        "GROUP BY je.account_code, je.account_name".format(','.join('?' * len(cash_accounts))),
        [ledger_id] + cash_accounts + [str(year), f"{month:02d}"]
    ).fetchall()

    result = []
    for row in rows:
        net = row["total_debit"] - row["total_credit"]
        if net > 0:
            result.append({"type": "operating_inflow", "name": "经营活动现金流入", "section": "operating",
                           "debit": row["total_debit"], "credit": row["total_credit"], "net": net})
        else:
            result.append({"type": "operating_outflow", "name": "经营活动现金流出", "section": "operating",
                           "debit": row["total_debit"], "credit": row["total_credit"], "net": net})
    return result

def init_cash_flow_categories(ledger_id: int):
    """初始化默认现金流分类"""
    default_categories = [
        # 经营活动
        ("OI01", "销售商品/提供劳务收到的现金",  "operating_inflow"),
        ("OI02", "收到的税费返还",                "operating_inflow"),
        ("OI03", "其他经营活动现金流入",          "operating_inflow"),
        ("OO01", "购买商品/接受劳务支付的现金",  "operating_outflow"),
        ("OO02", "支付给职工的现金",              "operating_outflow"),
        ("OO03", "支付的税费",                    "operating_outflow"),
        ("OO04", "其他经营活动现金流出",          "operating_outflow"),
        # 投资活动
        ("II01", "收回投资收到的现金",            "investing_inflow"),
        ("II02", "取得投资收益收到的现金",        "investing_inflow"),
        ("II03", "处置固定资产收回的现金",        "investing_inflow"),
        ("IO01", "购建固定资产支付的现金",        "investing_outflow"),
        ("IO02", "投资支付的现金",                "investing_outflow"),
        # 筹资活动
        ("FI01", "吸收投资收到的现金",            "financing_inflow"),
        ("FI02", "借款收到的现金",                "financing_inflow"),
        ("FO01", "偿还债务支付的现金",            "financing_outflow"),
        ("FO02", "分配利润支付的现金",            "financing_outflow"),
    ]
    for code, name, category in default_categories:
        add_cash_flow_category(ledger_id, code, name, category)

def _init_default_cash_flow_categories(c, ledger_id: int):
    """初始化默认现金流分类（使用cursor直接插入）"""
    default_categories = [
        ("OI01", "销售商品/提供劳务收到的现金",  "operating_inflow"),
        ("OI02", "收到的税费返还",                "operating_inflow"),
        ("OO01", "购买商品/接受劳务支付的现金",  "operating_outflow"),
        ("OO02", "支付给职工的现金",              "operating_outflow"),
        ("OO03", "支付的税费",                    "operating_outflow"),
        ("II01", "收回投资收到的现金",            "investing_inflow"),
        ("II02", "取得投资收益收到的现金",        "investing_inflow"),
        ("IO01", "购建固定资产支付的现金",        "investing_outflow"),
        ("IO02", "投资支付的现金",                "investing_outflow"),
        ("FI01", "吸收投资收到的现金",            "financing_inflow"),
        ("FI02", "借款收到的现金",                "financing_inflow"),
        ("FO01", "偿还债务支付的现金",            "financing_outflow"),
        ("FO02", "分配利润支付的现金",            "financing_outflow"),
    ]
    for code, name, category in default_categories:
        c.execute(
            "INSERT OR IGNORE INTO cash_flow_categories (ledger_id, code, name, category) VALUES (?,?,?,?)",
            (ledger_id, code, name, category)
        )

def get_cash_flow_statement_direct(ledger_id, year, month):
    """现金流量表（直接法）- 简化版，按对方科目类别归类"""
    conn = get_conn()
    try:

        def _cash_flow_by_counterpart(counter_clause, cash_direction):
            """按对方科目计算现金流入/流出
            cash_direction: 'debit'=现金借方(流入), 'credit'=现金贷方(流出)
            """
            cash_codes = "('1001','1002','1012')"
            row = conn.execute(f"""
                SELECT COALESCE(SUM(je_cash.{cash_direction}), 0) as total
                FROM journal_entries je_cash
                JOIN vouchers v ON je_cash.voucher_id = v.id
                INNER JOIN journal_entries je_other
                    ON je_other.voucher_id = v.id
                    AND je_other.account_code NOT IN {cash_codes}
                    AND {counter_clause}
                WHERE je_cash.ledger_id = ?
                  AND je_cash.account_code IN {cash_codes}
                  AND strftime('%Y', v.date) = ?
                  AND CAST(strftime('%m', v.date) AS INTEGER) <= ?
                  AND v.status = 'posted'
                  AND (v.description IS NULL OR v.description NOT LIKE '%结转%')
            """, [ledger_id, str(year), month]).fetchone()
            return round(row["total"], 2) if row else 0.0

        # 经营活动
        sales_inflow = _cash_flow_by_counterpart("a.category = '收入'", "debit")
        purchase_outflow = _cash_flow_by_counterpart("a.category = '费用'", "credit")

        # 获取所有经营现金流入/流出
        total_op_in = _cash_flow_by_counterpart("1=1", "debit")
        total_op_out = _cash_flow_by_counterpart("1=1", "credit")

        # 投资活动
        invest_codes = "('1601','1602','1604','1701','1702','1501','1511','1801')"
        invest_in = conn.execute(f"""
            SELECT COALESCE(SUM(je_cash.debit), 0) as total
            FROM journal_entries je_cash
            JOIN vouchers v ON je_cash.voucher_id = v.id
            INNER JOIN journal_entries je_other ON je_other.voucher_id = v.id
                AND je_other.account_code IN {invest_codes}
            WHERE je_cash.ledger_id = ? AND je_cash.account_code IN ('1001','1002','1012')
              AND strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) <= ?
              AND v.status = 'posted'
        """, [ledger_id, str(year), month]).fetchone()
        invest_in = round(invest_in["total"], 2) if invest_in else 0.0

        invest_out = conn.execute(f"""
            SELECT COALESCE(SUM(je_cash.credit), 0) as total
            FROM journal_entries je_cash
            JOIN vouchers v ON je_cash.voucher_id = v.id
            INNER JOIN journal_entries je_other ON je_other.voucher_id = v.id
                AND je_other.account_code IN {invest_codes}
            WHERE je_cash.ledger_id = ? AND je_cash.account_code IN ('1001','1002','1012')
              AND strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) <= ?
              AND v.status = 'posted'
        """, [ledger_id, str(year), month]).fetchone()
        invest_out = round(invest_out["total"], 2) if invest_out else 0.0

        # 筹资活动
        finance_codes = "('2001','2501','2701','2801','4001','4002')"
        finance_in = conn.execute(f"""
            SELECT COALESCE(SUM(je_cash.debit), 0) as total
            FROM journal_entries je_cash
            JOIN vouchers v ON je_cash.voucher_id = v.id
            INNER JOIN journal_entries je_other ON je_other.voucher_id = v.id
                AND je_other.account_code IN {finance_codes}
            WHERE je_cash.ledger_id = ? AND je_cash.account_code IN ('1001','1002','1012')
              AND strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) <= ?
              AND v.status = 'posted'
        """, [ledger_id, str(year), month]).fetchone()
        finance_in = round(finance_in["total"], 2) if finance_in else 0.0

        finance_out = conn.execute(f"""
            SELECT COALESCE(SUM(je_cash.credit), 0) as total
            FROM journal_entries je_cash
            JOIN vouchers v ON je_cash.voucher_id = v.id
            INNER JOIN journal_entries je_other ON je_other.voucher_id = v.id
                AND je_other.account_code IN {finance_codes}
            WHERE je_cash.ledger_id = ? AND je_cash.account_code IN ('1001','1002','1012')
              AND strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) <= ?
              AND v.status = 'posted'
        """, [ledger_id, str(year), month]).fetchone()
        finance_out = round(finance_out["total"], 2) if finance_out else 0.0

    finally:
        conn.close()

        op_net = total_op_in - total_op_out
        inv_net = invest_in - invest_out
        fin_net = finance_in - finance_out

        return {
        "date": f"{year}-{month:02d}",
        "operating": {
            "inflow": total_op_in,
            "outflow": total_op_out,
            "net": op_net,
            "details": [
                {"name": "销售商品、提供劳务收到的现金", "amount": sales_inflow},
                {"name": "购买商品、接受劳务支付的现金", "amount": -purchase_outflow},
                {"name": "收到其他与经营活动有关的现金", "amount": total_op_in - sales_inflow},
                {"name": "支付其他与经营活动有关的现金", "amount": -(total_op_out - purchase_outflow)},
            ],
        },
        "investing": {
            "inflow": invest_in,
            "outflow": invest_out,
            "net": inv_net,
            "details": [
                {"name": "处置固定资产收回的现金净额", "amount": invest_in},
                {"name": "购建固定资产支付的现金", "amount": -invest_out},
            ],
        },
        "financing": {
            "inflow": finance_in,
            "outflow": finance_out,
            "net": fin_net,
            "details": [
                {"name": "取得借款收到的现金", "amount": finance_in},
                {"name": "偿还债务支付的现金", "amount": -finance_out},
            ],
        },
        "net_increase": op_net + inv_net + fin_net,
        }
