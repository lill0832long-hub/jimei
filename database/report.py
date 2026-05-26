"""Database module: report domain"""

from .connection import get_conn, transaction, DB_PATH

def get_balance_sheet(ledger_id, year, month) -> dict:
    """资产负债表 — 中国会计准则格式，支持年初数"""
    conn = get_conn()
    try:

        def _opening_bal(code):
            # 取该科目本年期初余额（支持年中初始化：取最小月份的期初）
            row = conn.execute(
                """SELECT balance FROM opening_balances
                   WHERE ledger_id=? AND account_code=? AND year=?
                   AND month = (SELECT MIN(month) FROM opening_balances
                                WHERE ledger_id=? AND account_code=? AND year=?)""",
                (ledger_id, code, year, ledger_id, code, year)
            ).fetchone()
            if row:
                bal = row["balance"]
                acc = conn.execute("SELECT category FROM accounts WHERE code=? AND is_active=1", (code,)).fetchone()
                cat = acc["category"] if acc else "资产"
                if cat in ("资产", "费用"):
                    return (round(bal, 2), 0.0) if bal >= 0 else (0.0, round(-bal, 2))
                else:
                    return (0.0, round(bal, 2)) if bal >= 0 else (round(-bal, 2), 0.0)
            return (0.0, 0.0)

        def _year_activity(code):
            row = conn.execute(
                """SELECT COALESCE(SUM(je.debit),0) AS dr, COALESCE(SUM(je.credit),0) AS cr
                FROM journal_entries je
                JOIN vouchers v ON je.voucher_id=v.id AND v.status='posted'
                WHERE je.ledger_id=? AND je.account_code=?
                AND strftime('%Y',v.date)=? AND CAST(strftime('%m',v.date) AS INTEGER)<=?
                AND (v.description IS NULL OR v.description NOT LIKE '%结转%')""",
                (ledger_id, code, str(year), month)
            ).fetchone()
            return (round(row["dr"], 2), round(row["cr"], 2))

        def _end_bal(code, cat):
            o_dr, o_cr = _opening_bal(code)
            y_dr, y_cr = _year_activity(code)
            if cat in ("资产", "费用"):
                return (o_dr - o_cr) + (y_dr - y_cr)
            else:
                return (o_cr - o_dr) + (y_cr - y_dr)

        def _open_bal_signed(code, cat):
            o_dr, o_cr = _opening_bal(code)
            if cat in ("资产", "费用"):
                return o_dr - o_cr
            else:
                return o_cr - o_dr

        def _get_cat(code):
            row = conn.execute("SELECT category FROM accounts WHERE code=? AND is_active=1", (code,)).fetchone()
            return row["category"] if row else "资产"

        def _add(target, code, name, level, end_val, open_val, cat, is_parent=False):
            target.append({"code": code, "name": name, "level": level,
                           "end": round(end_val, 2), "open": round(open_val, 2),
                           "cat": cat, **({"is_parent": True} if is_parent else {})})

        def _net_bal(code):
            """返回科目期末净值 (dr-cr for 资产/费用, cr-dr for 负债/权益/收入)"""
            cat = _get_cat(code)
            return _end_bal(code, cat)

        def _net_open(code):
            """返回科目期初净值"""
            cat = _get_cat(code)
            return _open_bal_signed(code, cat)

        # ── 重分类辅助函数 ──
        # _end_bal 对资产/费用返回 dr-cr（正=借方余额，负=贷方余额）
        # _end_bal 对负债/权益/收入返回 cr-dr（正=贷方余额，负=借方余额）
        # 统一规则：
        #   借方余额 = 科目在借方的净额（资产类=正数部分，负债类=负数取反）
        #   贷方余额 = 科目在贷方的净额（资产类=负数取反，负债类=正数部分）

        def _dr_bal(code):
            """科目借方余额（正数）"""
            cat = _get_cat(code)
            bal = _net_bal(code)
            if cat == "资产":
                return max(bal, 0)    # 资产类：dr-cr > 0 → 借方余额
            else:
                return max(-bal, 0)   # 负债类：cr-dr < 0 → 借方余额（取反）

        def _cr_bal(code):
            """科目贷方余额（正数）"""
            cat = _get_cat(code)
            bal = _net_bal(code)
            if cat == "资产":
                return max(-bal, 0)   # 资产类：dr-cr < 0 → 贷方余额（取反）
            else:
                return max(bal, 0)    # 负债类：cr-dr > 0 → 贷方余额

        def _dr_open(code):
            cat = _get_cat(code)
            bal = _net_open(code)
            if cat == "资产":
                return max(bal, 0)
            else:
                return max(-bal, 0)

        def _cr_open(code):
            cat = _get_cat(code)
            bal = _net_open(code)
            if cat == "资产":
                return max(-bal, 0)
            else:
                return max(bal, 0)

        # ── 资产 ──
        assets = []
        ca_end, ca_open = 0.0, 0.0

        # 货币资金 = 库存现金 + 银行存款(含子科目) + 其他货币资金
        cash_codes = [c for c, _ in [("1001","库存现金"),("1002","银行存款"),("1012","其他货币资金")]]
        cash_end = sum(max(_net_bal(c), 0) for c in cash_codes)
        cash_open = sum(max(_net_open(c), 0) for c in cash_codes)
        if cash_end or cash_open:
            _add(assets, "1000", "货币资金", 1, cash_end, cash_open, "流动资产", is_parent=True)
            for c, n in [("1001","库存现金"),("1002","银行存款"),("1012","其他货币资金")]:
                ev, ov = max(_net_bal(c), 0), max(_net_open(c), 0)
                if ev or ov:
                    _add(assets, c, n, 2, ev, ov, "流动资产")
            ca_end += cash_end; ca_open += cash_open

        # 应收票据
        for code, name in [("1121","应收票据")]:
            ev, ov = max(_net_bal(code), 0), max(_net_open(code), 0)
            if ev or ov:
                _add(assets, code, name, 1, ev, ov, "流动资产")
                ca_end += ev; ca_open += ov

        # 应收账款 = 应收账款(借方) + 预收账款(借方余额重分类)
        ar_end = _dr_bal("1122") + _dr_bal("2203")
        ar_open = _dr_open("1122") + _dr_open("2203")
        if ar_end or ar_open:
            _add(assets, "1122", "应收账款", 1, ar_end, ar_open, "流动资产", is_parent=True)
            for c, n in [("1122","应收账款"),("2203","预收账款重分类")]:
                ev, ov = _dr_bal(c), _dr_open(c)
                if ev or ov:
                    _add(assets, c, n, 2, ev, ov, "流动资产")
            ca_end += ar_end; ca_open += ar_open

        # 预付款项 = 预付账款(借方) + 应付账款(借方余额重分类)
        prepay_end = _dr_bal("1123") + _dr_bal("2202")
        prepay_open = _dr_open("1123") + _dr_open("2202")
        if prepay_end or prepay_open:
            _add(assets, "1123", "预付款项", 1, prepay_end, prepay_open, "流动资产", is_parent=True)
            for c, n in [("1123","预付账款"),("2202","应付账款重分类")]:
                ev, ov = _dr_bal(c), _dr_open(c)
                if ev or ov:
                    _add(assets, c, n, 2, ev, ov, "流动资产")
            ca_end += prepay_end; ca_open += prepay_open

        # 其他应收款
        for code, name in [("1221","其他应收款")]:
            ev, ov = max(_net_bal(code), 0), max(_net_open(code), 0)
            if ev or ov:
                _add(assets, code, name, 1, ev, ov, "流动资产")
                ca_end += ev; ca_open += ov
        # 存货 = 材料采购+原材料+在途物资+周转材料+库存商品+发出商品+委托加工物资
        # 注意：5101生产成本(成本类)余额在借方表示在产品，应计入存货；4001为权益类科目不计入
        inv_codes = [
            ("1401","材料采购"), ("1403","原材料"), ("1402","在途物资"),
            ("1411","周转材料"), ("1405","库存商品"), ("1406","发出商品"),
            ("5101","生产成本"), ("1408","委托加工物资"),
        ]
        inv_end = sum(max(_end_bal(c, "资产"), 0) for c, _ in inv_codes)
        inv_open = sum(max(_open_bal_signed(c, "资产"), 0) for c, _ in inv_codes)
        if inv_end or inv_open:
            _add(assets, "1400", "存货", 1, inv_end, inv_open, "流动资产", is_parent=True)
            for c, n in inv_codes:
                ev, ov = max(_end_bal(c, "资产"), 0), max(_open_bal_signed(c, "资产"), 0)
                if ev or ov:
                    _add(assets, c, n, 2, ev, ov, "流动资产")
            ca_end += inv_end; ca_open += inv_open
        _add(assets, "", "流动资产合计", 0, ca_end, ca_open, "流动资产_total")

        # 非流动资产
        nca_end, nca_open = 0.0, 0.0
        # 固定资产 = 原值 - 累计折旧 - 减值准备
        fv_g, fv_g_open = _end_bal("1601","资产"), _open_bal_signed("1601","资产")
        fv_d, fv_d_open = _end_bal("1602","资产"), _open_bal_signed("1602","资产")
        fv_imp, fv_imp_open = _end_bal("1603","资产"), _open_bal_signed("1603","资产")
        # 资产类科目：_end_bal返回(dr-cr)，累计折旧余额在贷方(负数)，减值准备同理
        # 账面价值 = 原价 + 累计折旧 + 减值准备（后两者为负值）
        fv_net = fv_g + fv_d + fv_imp
        fv_net_open = fv_g_open + fv_d_open + fv_imp_open
        if fv_g or fv_g_open or fv_d or fv_d_open or fv_imp or fv_imp_open:
            _add(assets, "1601", "固定资产原价", 1, fv_g, fv_g_open, "非流动资产", is_parent=True)
            _add(assets, "1602", "减：累计折旧", 2, -fv_d, -fv_d_open, "非流动资产")
            _add(assets, "1603", "减：固定资产减值准备", 2, -fv_imp, -fv_imp_open, "非流动资产")
            _add(assets, "1601N", "固定资产账面价值", 2, fv_net, fv_net_open, "非流动资产")
            nca_end += fv_net; nca_open += fv_net_open

        # 无形资产 = 原值 - 累计摊销 - 减值准备
        ia_g, ia_g_open = _end_bal("1701","资产"), _open_bal_signed("1701","资产")
        ia_a, ia_a_open = _end_bal("1702","资产"), _open_bal_signed("1702","资产")
        ia_imp, ia_imp_open = _end_bal("1703","资产"), _open_bal_signed("1703","资产")
        ia_net = ia_g + ia_a + ia_imp
        ia_net_open = ia_g_open + ia_a_open + ia_imp_open
        if ia_g or ia_g_open or ia_a or ia_a_open or ia_imp or ia_imp_open:
            _add(assets, "1701", "无形资产原价", 1, ia_g, ia_g_open, "非流动资产", is_parent=True)
            _add(assets, "1702", "减：累计摊销", 2, -ia_a, -ia_a_open, "非流动资产")
            _add(assets, "1703", "减：无形资产减值准备", 2, -ia_imp, -ia_imp_open, "非流动资产")
            _add(assets, "1701N", "无形资产账面价值", 2, ia_net, ia_net_open, "非流动资产")
            nca_end += ia_net; nca_open += ia_net_open

        for code, name in [("1501","长期债券投资"),("1511","长期股权投资"),("1521","投资性房地产"),
                            ("1604","在建工程"),("1605","工程物资"),("1606","固定资产清理"),
                            ("1801","长期待摊费用"),("1811","递延所得税资产"),
                            ("1901","待处理财产损溢")]:
            ev, ov = max(_net_bal(code), 0), max(_net_open(code), 0)
            if ev or ov:
                _add(assets, code, name, 1, ev, ov, "非流动资产")
                nca_end += ev; nca_open += ov
        _add(assets, "", "非流动资产合计", 0, nca_end, nca_open, "非流动资产_total")

        total_assets = ca_end + nca_end
        total_assets_open = ca_open + nca_open
        _add(assets, "", "资产总计", 0, total_assets, total_assets_open, "total")

        # ── 负债 ──
        liabilities = []
        cl_end, cl_open = 0.0, 0.0

        # 短期借款、应付票据（无需重分类）
        for code, name in [("2001","短期借款"),("2201","应付票据")]:
            ev, ov = max(_net_bal(code), 0), max(_net_open(code), 0)
            if ev or ov:
                _add(liabilities, code, name, 1, ev, ov, "流动负债")
                cl_end += ev; cl_open += ov

        # 应付账款 = 应付账款(贷方) + 预付账款(贷方余额重分类)
        ap_end = _cr_bal("2202") + _cr_bal("1123")
        ap_open = _cr_open("2202") + _cr_open("1123")
        if ap_end or ap_open:
            _add(liabilities, "2202", "应付账款", 1, ap_end, ap_open, "流动负债", is_parent=True)
            for c, n in [("2202","应付账款"),("1123","预付账款重分类")]:
                ev, ov = _cr_bal(c), _cr_open(c)
                if ev or ov:
                    _add(liabilities, c, n, 2, ev, ov, "流动负债")
            cl_end += ap_end; cl_open += ap_open

        # 预收款项 = 预收账款(贷方) + 应收账款(贷方余额重分类)
        unearned_end = _cr_bal("2203") + _cr_bal("1122")
        unearned_open = _cr_open("2203") + _cr_open("1122")
        if unearned_end or unearned_open:
            _add(liabilities, "2203", "预收款项", 1, unearned_end, unearned_open, "流动负债", is_parent=True)
            for c, n in [("2203","预收账款"),("1122","应收账款重分类")]:
                ev, ov = _cr_bal(c), _cr_open(c)
                if ev or ov:
                    _add(liabilities, c, n, 2, ev, ov, "流动负债")
            cl_end += unearned_end; cl_open += unearned_open

        # 其他流动负债（无需重分类）
        for code, name in [("2211","应付职工薪酬"),("2221","应交税费"),
                            ("2231","应付利息"),("2232","应付股利"),("2241","其他应付款")]:
            ev, ov = max(_net_bal(code), 0), max(_net_open(code), 0)
            if ev or ov:
                _add(liabilities, code, name, 1, ev, ov, "流动负债")
                cl_end += ev; cl_open += ov

        _add(liabilities, "", "流动负债合计", 0, cl_end, cl_open, "流动负债_total")

        # 非流动负债
        ncl_end, ncl_open = 0.0, 0.0
        for code, name in [("2501","长期借款"),("2502","应付债券"),("2701","长期应付款"),
                            ("2801","预计负债"),("2401","递延收益"),("2901","递延所得税负债")]:
            ev, ov = max(_net_bal(code), 0), max(_net_open(code), 0)
            if ev or ov:
                _add(liabilities, code, name, 1, ev, ov, "非流动负债")
                ncl_end += ev; ncl_open += ov
        _add(liabilities, "", "非流动负债合计", 0, ncl_end, ncl_open, "非流动负债_total")
        total_liab, total_liab_open = cl_end + ncl_end, cl_open + ncl_open
        _add(liabilities, "", "负债合计", 0, total_liab, total_liab_open, "liab_total")

        # ── 所有者权益 ──
        equity = []
        eq_end, eq_open = 0.0, 0.0
        for code, name in [("4001","实收资本"),("4002","资本公积"),("4101","盈余公积")]:
            ev, ov = _net_bal(code), _net_open(code)
            if ev or ov:
                _add(equity, code, name, 1, ev, ov, "权益")
                eq_end += ev; eq_open += ov

        # 未分配利润 = 利润分配(4104)期末余额 + 本年利润(4103)期末余额
        # 直接查询4103/4104的期末余额（不过滤结转凭证，因为4103的结转凭证是其正常业务）
        def _raw_end_bal(code):
            """查询科目期末余额（含所有已过账凭证，不过滤结转）"""
            row = conn.execute("""
                SELECT COALESCE(ob.balance, 0) as ob,
                       COALESCE(SUM(je.debit), 0) as dr,
                       COALESCE(SUM(je.credit), 0) as cr
                FROM accounts a
                LEFT JOIN opening_balances ob ON ob.account_code=a.code AND ob.ledger_id=? AND ob.year=?
                LEFT JOIN journal_entries je ON je.account_code=a.code AND je.ledger_id=?
                LEFT JOIN vouchers v ON je.voucher_id=v.id AND v.status='posted'
                    AND strftime('%Y',v.date)=? AND CAST(strftime('%m',v.date) AS INTEGER)<=?
                WHERE a.code=?
            """, (ledger_id, year, ledger_id, str(year), month, code)).fetchone()
            cat = _get_cat(code)
            ob = row["ob"] or 0
            dr = row["dr"] or 0
            cr = row["cr"] or 0
            if cat in ("资产", "费用"):
                # 资产类：借方正，贷方负
                o_dr = max(ob, 0)
                o_cr = max(-ob, 0)
                return (o_dr - o_cr) + (dr - cr)
            else:
                # 负债/权益类：贷方正，借方负
                o_cr = max(ob, 0)
                o_dr = max(-ob, 0)
                return (o_cr - o_dr) + (cr - dr)

        def _raw_open_bal(code):
            row = conn.execute(
                "SELECT balance FROM opening_balances WHERE ledger_id=? AND account_code=? AND year=?",
                (ledger_id, code, year)
            ).fetchone()
            return row[0] if row else 0

        rp4104_end = _raw_end_bal("4104")
        rp4103_end = _raw_end_bal("4103")
        rp4104_open = _raw_open_bal("4104")
        rp4103_open = _raw_open_bal("4103")

        rp_end = max(rp4104_end, 0) + rp4103_end
        rp_open = max(rp4104_open, 0) + rp4103_open
        if rp_end or rp_open:
            _add(equity, "4104N", "未分配利润", 1, rp_end, rp_open, "权益")
            eq_end += rp_end; eq_open += rp_open

        total_equity, total_equity_open = eq_end, eq_open
        _add(equity, "", "所有者权益合计", 0, total_equity, total_equity_open, "eq_total")
        _add(equity, "", "负债和所有者权益总计", 0, total_liab + total_equity, total_liab_open + total_equity_open, "grand_total")

    finally:
        conn.close()
    return {
        "date": f"{year}-{month:02d}",
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "total_assets": round(total_assets, 2),
        "total_liab": round(total_liab, 2),
        "total_equity": round(total_equity, 2),
    }

def get_income_statement(ledger_id, year, month) -> dict:
    """利润表 — 支持子项明细 + 本年累计/本月金额
    列：项目 | 行次 | 本年累计金额 | 本月金额
    """
    conn = get_conn()
    try:

        def _period_clause(table="v"):
            # 只排除结转类凭证，不过滤含"年月"的摘要（避免误杀正常凭证）
            return f"strftime('%Y', {table}.date) = ? AND CAST(strftime('%m', {table}.date) AS INTEGER) = ? AND ({table}.description IS NULL OR {table}.description NOT LIKE '%结转%')"

        def _ytd_clause(table="v"):
            return f"strftime('%Y', {table}.date) = ? AND CAST(strftime('%m', {table}.date) AS INTEGER) <= ? AND ({table}.description IS NULL OR {table}.description NOT LIKE '%结转%')"

        def _expense_month(code=None, sub=None):
            where = "a.category = '费用' AND a.is_active = 1"
            params = []
            if code:
                where += " AND a.code = ?"
                params.append(code)
            if sub:
                where += " AND a.sub_category = ?"
                params.append(sub)
            p = [ledger_id, str(year), month] + params
            row = conn.execute(f"""
                SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) AS amt
                FROM accounts a
                LEFT JOIN journal_entries je ON je.account_code = a.code AND je.ledger_id = ?
                INNER JOIN vouchers v ON je.voucher_id = v.id AND v.status = 'posted' AND {_period_clause()}
                WHERE {where}
            """, p).fetchone()
            return round(row["amt"], 2) if row else 0

        def _expense_ytd(code=None, sub=None):
            where = "a.category = '费用' AND a.is_active = 1"
            params = []
            if code:
                where += " AND a.code = ?"
                params.append(code)
            if sub:
                where += " AND a.sub_category = ?"
                params.append(sub)
            p = [ledger_id, str(year), month] + params
            row = conn.execute(f"""
                SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) AS amt
                FROM accounts a
                LEFT JOIN journal_entries je ON je.account_code = a.code AND je.ledger_id = ?
                INNER JOIN vouchers v ON je.voucher_id = v.id AND v.status = 'posted' AND {_ytd_clause()}
                WHERE {where}
            """, p).fetchone()
            return round(row["amt"], 2) if row else 0

        def _revenue_month(code=None, sub=None):
            where = "a.category = '收入' AND a.is_active = 1"
            params = []
            if code:
                where += " AND a.code = ?"
                params.append(code)
            if sub:
                where += " AND a.sub_category = ?"
                params.append(sub)
            p = [ledger_id, str(year), month] + params
            row = conn.execute(f"""
                SELECT COALESCE(SUM(je.credit) - SUM(je.debit), 0) AS amt
                FROM accounts a
                LEFT JOIN journal_entries je ON je.account_code = a.code AND je.ledger_id = ?
                INNER JOIN vouchers v ON je.voucher_id = v.id AND v.status = 'posted' AND {_period_clause()}
                WHERE {where}
            """, p).fetchone()
            return round(row["amt"], 2) if row else 0

        def _revenue_ytd(code=None, sub=None):
            where = "a.category = '收入' AND a.is_active = 1"
            params = []
            if code:
                where += " AND a.code = ?"
                params.append(code)
            if sub:
                where += " AND a.sub_category = ?"
                params.append(sub)
            p = [ledger_id, str(year), month] + params
            row = conn.execute(f"""
                SELECT COALESCE(SUM(je.credit) - SUM(je.debit), 0) AS amt
                FROM accounts a
                LEFT JOIN journal_entries je ON je.account_code = a.code AND je.ledger_id = ?
                INNER JOIN vouchers v ON je.voucher_id = v.id AND v.status = 'posted' AND {_ytd_clause()}
                WHERE {where}
            """, p).fetchone()
            return round(row["amt"], 2) if row else 0

        def _child_accounts(parent_code):
            if not parent_code:
                return []
            rows = conn.execute(
                "SELECT code, name FROM accounts WHERE parent_code = ? AND is_active = 1 ORDER BY code",
                (parent_code,)
            ).fetchall()
            return [dict(r) for r in rows]

        rows = []

        # 一、营业收入
        rows.append({"name": "一、营业收入", "code": "", "level": 0, "month": None, "ytd": None, "type": "header"})
        rev_codes = conn.execute(
            "SELECT code, name FROM accounts WHERE category='收入' AND sub_category='营业收入' AND parent_code IS NULL AND is_active=1 ORDER BY code"
        ).fetchall()
        total_rev_month = 0
        total_rev_ytd = 0
        for r in rev_codes:
            children = _child_accounts(r["code"])
            # 先查父科目本身的数据（即使有子科目，父科目也可能有直接凭证）
            m_parent = _revenue_month(code=r["code"])
            y_parent = _revenue_ytd(code=r["code"])
            if m_parent or y_parent:
                rows.append({"name": r["name"], "code": r["code"], "level": 1, "month": m_parent, "ytd": y_parent, "type": "revenue_item"})
                total_rev_month += m_parent
                total_rev_ytd += y_parent
            # 再查子科目
            if children:
                for ch in children:
                    m = _revenue_month(code=ch["code"])
                    y = _revenue_ytd(code=ch["code"])
                    if m or y:
                        rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "revenue_item"})
                        total_rev_month += m
                        total_rev_ytd += y
        rows.append({"name": "营业收入合计", "code": "", "level": 0, "month": total_rev_month, "ytd": total_rev_ytd, "type": "rev_total"})

        # 减：营业成本
        cogs_month = _expense_month(code="6401")
        cogs_ytd = _expense_ytd(code="6401")
        cogs_children = _child_accounts("6401")
        for ch in cogs_children:
            m = _expense_month(code=ch["code"])
            y = _expense_ytd(code=ch["code"])
            if m or y:
                rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})
        rows.append({"name": "减：营业成本", "code": "", "level": 0, "month": cogs_month, "ytd": cogs_ytd, "type": "expense_header"})

        # 税金及附加（含子项）
        tax_month = _expense_month(code="6403")
        tax_ytd = _expense_ytd(code="6403")
        rows.append({"name": "税金及附加", "code": "6403", "level": 0, "month": tax_month, "ytd": tax_ytd, "type": "expense_header"})
        for ch in _child_accounts("6403"):
            m = _expense_month(code=ch["code"])
            y = _expense_ytd(code=ch["code"])
            if m or y:
                rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})

        # 销售费用（含子项）
        sfa_month = _expense_month(code="6601")
        sfa_ytd = _expense_ytd(code="6601")
        rows.append({"name": "销售费用", "code": "6601", "level": 0, "month": sfa_month, "ytd": sfa_ytd, "type": "expense_header"})
        for ch in _child_accounts("6601"):
            m = _expense_month(code=ch["code"])
            y = _expense_ytd(code=ch["code"])
            if m or y:
                rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})

        # 管理费用（含子项）
        ma_month = _expense_month(code="6602")
        ma_ytd = _expense_ytd(code="6602")
        rows.append({"name": "管理费用", "code": "6602", "level": 0, "month": ma_month, "ytd": ma_ytd, "type": "expense_header"})
        for ch in _child_accounts("6602"):
            m = _expense_month(code=ch["code"])
            y = _expense_ytd(code=ch["code"])
            if m or y:
                rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})

        # 研发费用（5001研发支出转入）
        rd_month = _expense_month(code="5001")
        rd_ytd = _expense_ytd(code="5001")
        rows.append({"name": "研发费用", "code": "5001", "level": 0, "month": rd_month, "ytd": rd_ytd, "type": "expense_header"})

        # 财务费用（含子项）
        fa_month = _expense_month(code="6603")
        fa_ytd = _expense_ytd(code="6603")
        rows.append({"name": "财务费用", "code": "6603", "level": 0, "month": fa_month, "ytd": fa_ytd, "type": "expense_header"})
        for ch in _child_accounts("6603"):
            m = _expense_month(code=ch["code"])
            y = _expense_ytd(code=ch["code"])
            if m or y:
                rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})

        # 加：投资收益
        inv_month = _revenue_month(code="6111")
        inv_ytd = _revenue_ytd(code="6111")
        rows.append({"name": "加：投资收益", "code": "6111", "level": 1, "month": inv_month, "ytd": inv_ytd, "type": "revenue_item"})

        # 加：公允价值变动收益
        fv_month = _revenue_month(code="6101")
        fv_ytd = _revenue_ytd(code="6101")
        rows.append({"name": "加：公允价值变动收益", "code": "6101", "level": 1, "month": fv_month, "ytd": fv_ytd, "type": "revenue_item"})

        # 加：其他收益（营业外收入中的政府补助等）
        # 暂从6301营业外收入中拆分
        oth_rev_month = 0  # 暂缺独立科目，后续可增设6311
        oth_rev_ytd = 0
        rows.append({"name": "加：其他收益", "code": "", "level": 1, "month": oth_rev_month, "ytd": oth_rev_ytd, "type": "revenue_item"})

        # 减：信用减值损失
        cl_month = _expense_month(code="6702")
        cl_ytd = _expense_ytd(code="6702")
        rows.append({"name": "减：信用减值损失", "code": "6702", "level": 0, "month": cl_month, "ytd": cl_ytd, "type": "expense_header"})

        # 减：资产减值损失
        imp_month = _expense_month(code="6701")
        imp_ytd = _expense_ytd(code="6701")
        rows.append({"name": "减：资产减值损失", "code": "6701", "level": 0, "month": imp_month, "ytd": imp_ytd, "type": "expense_header"})

        # 加：资产处置收益（暂缺独立科目6001）
        dp_month = 0
        dp_ytd = 0
        rows.append({"name": "加：资产处置收益", "code": "", "level": 1, "month": dp_month, "ytd": dp_ytd, "type": "revenue_item"})

        # 二、营业利润
        total_expense_month = cogs_month + tax_month + sfa_month + ma_month + rd_month + fa_month + cl_month + imp_month
        total_expense_ytd = cogs_ytd + tax_ytd + sfa_ytd + ma_ytd + rd_ytd + fa_ytd + cl_ytd + imp_ytd
        op_month = total_rev_month - total_expense_month + inv_month + fv_month + oth_rev_month + dp_month
        op_ytd = total_rev_ytd - total_expense_ytd + inv_ytd + fv_ytd + oth_rev_ytd + dp_ytd
        rows.append({"name": "二、营业利润", "code": "", "level": 0, "month": op_month, "ytd": op_ytd, "type": "subtotal"})

        # 加：营业外收入（含子项：政府补助）
        oi_month = _revenue_month(code="6301")
        oi_ytd = _revenue_ytd(code="6301")
        rows.append({"name": "加：营业外收入", "code": "6301", "level": 0, "month": oi_month, "ytd": oi_ytd, "type": "revenue_header"})
        for ch in _child_accounts("6301"):
            m = _revenue_month(code=ch["code"])
            y = _revenue_ytd(code=ch["code"])
            if m or y:
                rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "revenue_item"})

        # 减：营业外支出（含子项）
        oe_month = _expense_month(code="6711")
        oe_ytd = _expense_ytd(code="6711")
        rows.append({"name": "减：营业外支出", "code": "6711", "level": 0, "month": oe_month, "ytd": oe_ytd, "type": "expense_header"})
        for ch in _child_accounts("6711"):
            m = _expense_month(code=ch["code"])
            y = _expense_ytd(code=ch["code"])
            if m or y:
                rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})

        # 三、利润总额
        bt_month = op_month + oi_month - oe_month
        bt_ytd = op_ytd + oi_ytd - oe_ytd
        rows.append({"name": "三、利润总额", "code": "", "level": 0, "month": bt_month, "ytd": bt_ytd, "type": "subtotal"})

        # 减：所得税费用
        tax_exp_month = _expense_month(code="6801")
        tax_exp_ytd = _expense_ytd(code="6801")
        rows.append({"name": "减：所得税费用", "code": "6801", "level": 1, "month": tax_exp_month, "ytd": tax_exp_ytd, "type": "expense_item"})

        # 四、净利润
        np_month = bt_month - tax_exp_month
        np_ytd = bt_ytd - tax_exp_ytd
        rows.append({"name": "四、净利润", "code": "", "level": 0, "month": np_month, "ytd": np_ytd, "type": "total"})

    finally:
        conn.close()

    return {
        "date": f"{year}-{month:02d}",
        "rows": rows,
        "total_revenue": total_rev_month,
        "total_revenue_ytd": total_rev_ytd,
        "total_expense": total_expense_month,
        "total_expense_ytd": total_expense_ytd,
        "cogs": cogs_month,
        "cogs_ytd": cogs_ytd,
        "summary": {
            "total_revenue": total_rev_month,
            "total_revenue_ytd": total_rev_ytd,
            "total_expense": total_expense_month,
            "total_expense_ytd": total_expense_ytd,
            "net_profit": np_month,
            "net_profit_ytd": np_ytd,
        },
        "net_profit": np_month,
        "net_profit_ytd": np_ytd,
    }

def export_balance_sheet_csv(ledger_id, year, month, filepath):
    """导出资产负债表为 CSV"""
    import csv
    bs = get_balance_sheet(ledger_id, year, month)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([f'资产负债表', f'编制日期: {bs["date"]}'])
        writer.writerow([])
        # 表头：资产 | 负债和所有者权益（两栏式）
        writer.writerow(['资产', '期末数', '年初数', '', '负债和所有者权益', '期末数', '年初数'])
        # 收集资产行
        asset_rows = []
        for item in bs['assets']:
            asset_rows.append((item['name'], item['end'], item['open']))
        # 收集负债+权益行
        liab_eq_rows = []
        for item in bs['liabilities']:
            liab_eq_rows.append((item['name'], item['end'], item['open']))
        for item in bs['equity']:
            liab_eq_rows.append((item['name'], item['end'], item['open']))
        # 对齐输出
        max_rows = max(len(asset_rows), len(liab_eq_rows))
        for i in range(max_rows):
            row = [''] * 7
            if i < len(asset_rows):
                row[0] = asset_rows[i][0]
                row[1] = asset_rows[i][1] if asset_rows[i][1] != 0 else ''
                row[2] = asset_rows[i][2] if asset_rows[i][2] != 0 else ''
            if i < len(liab_eq_rows):
                row[4] = liab_eq_rows[i][0]
                row[5] = liab_eq_rows[i][1] if liab_eq_rows[i][1] != 0 else ''
                row[6] = liab_eq_rows[i][2] if liab_eq_rows[i][2] != 0 else ''
            writer.writerow(row)
    return True

def export_income_statement_csv(ledger_id, year, month, filepath):
    """导出利润表为 CSV"""
    import csv
    inc = get_income_statement(ledger_id, year, month)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([f'利润表', f'期间: {inc["date"]}'])
        writer.writerow([])
        writer.writerow(['项目', '行次', '本年累计', '本月金额'])
        line_no = 0
        for r in inc['rows']:
            t = r['type']
            if t in ('revenue_header', 'expense_header'):
                line_no += 1
                ytd_val = round(r['ytd'], 2) if r['ytd'] is not None and r['ytd'] != 0 else ''
                month_val = round(r['month'], 2) if r['month'] is not None and r['month'] != 0 else ''
                writer.writerow([r['name'], line_no, ytd_val, month_val])
            elif t in ('revenue_item', 'expense_item'):
                ytd_val = round(r['ytd'], 2) if r['ytd'] is not None and r['ytd'] != 0 else ''
                month_val = round(r['month'], 2) if r['month'] is not None and r['month'] != 0 else ''
                indent = '  ' if r.get('level', 1) > 1 else ''
                writer.writerow([indent + r['name'], '', ytd_val, month_val])
            elif t in ('subtotal', 'total'):
                line_no += 1
                ytd_val = round(r['ytd'], 2) if r['ytd'] is not None and r['ytd'] != 0 else ''
                month_val = round(r['month'], 2) if r['month'] is not None and r['month'] != 0 else ''
                writer.writerow([r['name'], line_no, ytd_val, month_val])
    return True

def export_balance_sheet_pdf(ledger_id: int, year: int, month: int, filepath: str):
    """导出资产负债表为PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    bs = get_balance_sheet(ledger_id, year, month)
    ledger = get_ledger(ledger_id)
    cjk_font = _get_cjk_font()

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontName=cjk_font, fontSize=16)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName=cjk_font, fontSize=9)
    bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName=cjk_font, fontSize=9, bold=True)

    elements = []

    # 标题
    elements.append(Paragraph(f"资产负债表", title_style))
    elements.append(Paragraph(f"{ledger['company']}  {bs['date']}", normal_style))
    elements.append(Spacer(1, 5*mm))

    # 表头
    header = ["资产", "期末数", "年初数", "", "负债和所有者权益", "期末数", "年初数"]
    data = [[Paragraph(h, bold_style) for h in header]]

    max_rows = max(len(bs["assets"]), len(bs["liabilities"]) + len(bs["equity"]))
    for i in range(max_rows):
        row = []
        if i < len(bs["assets"]):
            a = bs["assets"][i]
            indent = "&nbsp;&nbsp;" if a.get("level", 0) > 1 else ""
            name_style = bold_style if a.get("level", 0) == 0 else normal_style
            row.append(Paragraph(f"{indent}{a['name']}", name_style))
            end_v = f"{a.get('end', 0):,.2f}" if a.get('end') is not None else "-"
            open_v = f"{a.get('open', 0):,.2f}" if a.get('open') is not None else "-"
            row.append(Paragraph(end_v, normal_style))
            row.append(Paragraph(open_v, normal_style))
        else:
            row.extend(["", "", ""])

        row.append("")  # 分隔列

        eq_items = bs["liabilities"] + bs["equity"]
        if i < len(eq_items):
            e = eq_items[i]
            indent = "&nbsp;&nbsp;" if e.get("level", 0) > 1 else ""
            name_style = bold_style if e.get("level", 0) == 0 else normal_style
            row.append(Paragraph(f"{indent}{e['name']}", name_style))
            end_v = f"{e.get('end', 0):,.2f}" if e.get('end') is not None else "-"
            open_v = f"{e.get('open', 0):,.2f}" if e.get('open') is not None else "-"
            row.append(Paragraph(end_v, normal_style))
            row.append(Paragraph(open_v, normal_style))
        else:
            row.extend(["", "", ""])

        data.append(row)

    # 合计行
    total_row = [
        Paragraph("<b>资产总计</b>", bold_style),
        Paragraph(f"<b>{bs['total_assets']:,.2f}</b>", bold_style),
        "", "",
        Paragraph("<b>负债和所有者权益总计</b>", bold_style),
        Paragraph(f"<b>{bs['total_liab'] + bs['total_equity']:,.2f}</b>", bold_style),
        "",
    ]
    data.append(total_row)

    col_widths = [45*mm, 25*mm, 25*mm, 10*mm, 45*mm, 25*mm, 25*mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), cjk_font),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (4, 1), (4, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
        ('LINEBEFORE', (3, 0), (3, -1), 1.5, colors.black),
        ('FONTNAME', (0, -1), (-1, -1), cjk_font),
    ]))
    elements.append(table)

    # 平衡校验
    diff = abs(bs['total_assets'] - (bs['total_liab'] + bs['total_equity']))
    balance_text = f"平衡校验：{'✅ 平衡' if diff < 0.01 else f'❌ 差额 {diff:,.2f}'}"
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph(balance_text, normal_style))

    # 页脚
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(f"打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}    第 1 页", normal_style))

    doc.build(elements)

def export_income_statement_pdf(ledger_id: int, year: int, month: int, filepath: str):
    """导出利润表为PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    inc = get_income_statement(ledger_id, year, month)
    ledger = get_ledger(ledger_id)
    cjk_font = _get_cjk_font()

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontName=cjk_font, fontSize=16)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName=cjk_font, fontSize=9)
    bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName=cjk_font, fontSize=9, bold=True)

    elements = []
    elements.append(Paragraph("利润表", title_style))
    elements.append(Paragraph(f"{ledger['company']}  {inc['date']}", normal_style))
    elements.append(Spacer(1, 5*mm))

    header = ["项目", "行次", "本年累计金额", "本月金额"]
    data = [[Paragraph(h, bold_style) for h in header]]

    for r in inc["rows"]:
        indent = "&nbsp;&nbsp;" if r.get("level", 1) > 0 else ""
        name_style = bold_style if r.get("type") in ("header", "subtotal", "total") else normal_style
        name = f"{indent}{r['name']}"
        ytd_v = f"{r['ytd']:,.2f}" if r.get('ytd') is not None else ""
        month_v = f"{r['month']:,.2f}" if r.get('month') is not None else ""
        data.append([
            Paragraph(name, name_style),
            Paragraph(r.get("code", "") or "", normal_style),
            Paragraph(ytd_v, normal_style),
            Paragraph(month_v, normal_style),
        ])

    col_widths = [70*mm, 20*mm, 40*mm, 40*mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), cjk_font),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, -1), (-1, -1), cjk_font),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(f"打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}    第 1 页", normal_style))
    doc.build(elements)

def export_account_balances_csv(ledger_id, year, month, filepath):
    """导出科目余额表为 CSV"""
    import csv
    balances = get_account_balances(ledger_id, year, month)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['科目余额表', f'{year}-{month:02d}'])
        writer.writerow([])
        writer.writerow(['科目编码', '科目名称', '期初借方', '期初贷方', '本期借方', '本期贷方', '累计借方', '累计贷方', '期末借方', '期末贷方'])
        for b in balances:
            def fmt(v):
                return round(v, 2) if v else ''
            writer.writerow([b['code'], b['name'],
                             fmt(b['opening_dr']), fmt(b['opening_cr']),
                             fmt(b['curr_dr']), fmt(b['curr_cr']),
                             fmt(b['ytd_dr']), fmt(b['ytd_cr']),
                             fmt(b['closing_dr']), fmt(b['closing_cr'])])
    return len(balances)

def export_account_balances_pdf(ledger_id: int, year: int, month: int, filepath: str):
    """导出科目余额表为PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    balances = get_account_balances(ledger_id, year, month)
    ledger = get_ledger(ledger_id)
    cjk_font = _get_cjk_font()

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontName=cjk_font, fontSize=16)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName=cjk_font, fontSize=8)
    bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName=cjk_font, fontSize=8, bold=True)

    elements = []
    elements.append(Paragraph("科目余额表", title_style))
    elements.append(Paragraph(f"{ledger['company']}  {year}年{month}月", normal_style))
    elements.append(Spacer(1, 5*mm))

    header = ["科目代码", "科目名称", "期初借方", "期初贷方", "本期借方", "本期贷方", "期末借方", "期末贷方"]
    data = [[Paragraph(h, bold_style) for h in header]]

    for b in balances:
        indent = "&nbsp;&nbsp;" if b.get("level", 0) > 0 else ""
        name_style = bold_style if b.get("level", 0) == 0 else normal_style
        data.append([
            Paragraph(b["code"], normal_style),
            Paragraph(f"{indent}{b['name']}", name_style),
            Paragraph(f"{b.get('opening_dr', 0):,.2f}" if b.get('opening_dr') else "", normal_style),
            Paragraph(f"{b.get('opening_cr', 0):,.2f}" if b.get('opening_cr') else "", normal_style),
            Paragraph(f"{b.get('curr_dr', 0):,.2f}" if b.get('curr_dr') else "", normal_style),
            Paragraph(f"{b.get('curr_cr', 0):,.2f}" if b.get('curr_cr') else "", normal_style),
            Paragraph(f"{b.get('closing_dr', 0):,.2f}" if b.get('closing_dr') else "", normal_style),
            Paragraph(f"{b.get('closing_cr', 0):,.2f}" if b.get('closing_cr') else "", normal_style),
        ])

    col_widths = [20*mm, 35*mm, 22*mm, 22*mm, 22*mm, 22*mm, 22*mm, 22*mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), cjk_font),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(f"打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}    第 1 页", normal_style))
    doc.build(elements)

def export_vouchers_csv(ledger_id, year, month, filepath):
    """导出凭证为 CSV"""
    import csv
    vouchers = get_vouchers(ledger_id, year, month, limit=10000)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['凭证号', '日期', '摘要', '科目代码', '科目名称', '借方', '贷方', '状态'])
        for v in vouchers:
            detail = get_voucher_detail(ledger_id, v['voucher_no'])
            for e in detail.get('entries', []):
                status_label = {'draft':'草稿','posted':'已过账','reversed':'已冲销'}.get(v['status'], v['status'])
                writer.writerow([v['voucher_no'], v['date'], v['description'],
                                 e['account_code'], e['account_name'],
                                 e['debit'] or '', e['credit'] or '', status_label])
    return len(vouchers)

def export_vouchers_pdf(ledger_id: int, year: int, month: int, filepath: str):
    """导出凭证列表为PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    cn_style = ParagraphStyle('Chinese', parent=styles['Normal'], fontName='STSong-Light', fontSize=9)
    cn_bold = ParagraphStyle('ChineseBold', parent=styles['Normal'], fontName='STSong-Light', fontSize=10, leading=14)

    elements = []
    elements.append(Paragraph("凭证列表 - {}年{}月".format(year, month), cn_bold))
    elements.append(Spacer(1, 5*mm))

    vouchers = get_vouchers(ledger_id, year, month, limit=1000)
    for v in vouchers:
        elements.append(Paragraph("凭证号：{}  日期：{}  {}".format(v["voucher_no"], v["date"], v["description"]), cn_style))
        detail = get_voucher_detail(ledger_id, v["voucher_no"])
        table_data = [["科目代码", "科目名称", "借方金额", "贷方金额"]]
        for row in detail["entries"]:
            table_data.append([
                row["account_code"], row["account_name"],
                "{:,.2f}".format(row["debit"]) if row["debit"] else "",
                "{:,.2f}".format(row["credit"]) if row["credit"] else "",
            ])
        table_data.append(["", "合计", "{:,.2f}".format(v["total_debit"]), "{:,.2f}".format(v["total_credit"])])
        t = Table(table_data, colWidths=[30*mm, 50*mm, 30*mm, 30*mm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'STSong-Light'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a3a5c')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,-1), (-1,-1), 'STSong-Light'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 3*mm))

    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph("打印时间：{}    第 1 页".format(datetime.now().strftime('%Y-%m-%d %H:%M')), cn_style))
    doc.build(elements)

def _flatten_bs(section):
    """将资产负债结构扁平化为条目列表"""
    result = []
    for sub_cat, items in section.items():
        if sub_cat == "total" or not items:
            continue
        result.extend(items)
    return result

def _get_cjk_font():
    """获取中文字体名称（使用reportlab内置CID字体）"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    try:
        font = UnicodeCIDFont('STSong-Light')
        pdfmetrics.registerFont(font)
        return 'STSong-Light'
    except:
        return 'Helvetica'
