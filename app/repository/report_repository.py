"""Report data repository — provides data for financial reports."""
from sqlalchemy import select, and_, func, case, literal_column, Integer
from app.models.voucher import Voucher, JournalEntry
from app.models.account import Account
from app.models.opening_balance import OpeningBalance
from app.models.ledger import Ledger
from app.models.base import get_db


class ReportRepository:
    """Read-only queries for report generation."""

    async def get_account_balances(self, ledger_id: int, year: int, month: int):
        """Get account balances with opening + period activity.

        Uses batch GROUP BY queries instead of per-account N+1 queries.
        3 queries total regardless of account count.
        """
        async with get_db() as session:
            date_prefix = f"{year:04d}-{month:02d}"
            year_prefix = f"{year:04d}-"
            month_end = f"{year:04d}-{month:02d}-31"

            # 1. Get all active accounts
            stmt = select(Account).where(Account.is_active == 1).order_by(Account.code)
            result = await session.execute(stmt)
            accounts = result.scalars().all()
            account_codes = [a.code for a in accounts]

            if not accounts:
                return []

            # 2. Batch: opening balances for all accounts
            ob_stmt = select(
                OpeningBalance.account_code,
                OpeningBalance.balance,
            ).where(
                and_(
                    OpeningBalance.ledger_id == ledger_id,
                    OpeningBalance.account_code.in_(account_codes),
                    OpeningBalance.year == year,
                    OpeningBalance.month <= month,
                )
            ).order_by(OpeningBalance.account_code, OpeningBalance.year.desc(), OpeningBalance.month.desc())
            ob_result = await session.execute(ob_stmt)
            # Take the latest opening balance per account_code
            opening_map = {}
            for ob_row in ob_result.all():
                if ob_row.account_code not in opening_map:
                    opening_map[ob_row.account_code] = ob_row.balance

            # 3. Batch: period debit/credit (current month) — GROUP BY account_code
            period_stmt = select(
                JournalEntry.account_code,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    JournalEntry.ledger_id == ledger_id,
                    JournalEntry.account_code.in_(account_codes),
                    Voucher.date.like(f"{date_prefix}%"),
                    Voucher.status == "posted",
                )
            ).group_by(JournalEntry.account_code)
            period_result = await session.execute(period_stmt)
            period_map = {r.account_code: (r.total_debit, r.total_credit) for r in period_result.all()}

            # 4. Batch: YTD debit/credit (Jan through current month) — GROUP BY account_code
            ytd_stmt = select(
                JournalEntry.account_code,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    JournalEntry.ledger_id == ledger_id,
                    JournalEntry.account_code.in_(account_codes),
                    Voucher.date.like(f"{year_prefix}%"),
                    Voucher.date <= month_end,
                    Voucher.status == "posted",
                )
            ).group_by(JournalEntry.account_code)
            ytd_result = await session.execute(ytd_stmt)
            ytd_map = {r.account_code: (r.total_debit, r.total_credit) for r in ytd_result.all()}

            # 5. Assemble results (no more DB queries)
            balances = []
            for acct in accounts:
                opening = opening_map.get(acct.code, 0)
                period_debit, period_credit = period_map.get(acct.code, (0, 0))
                ytd_debit, ytd_credit = ytd_map.get(acct.code, (0, 0))

                if acct.category in ("资产", "费用"):
                    closing = opening + period_debit - period_credit
                else:
                    closing = opening + period_credit - period_debit

                balances.append({
                    "account_code": acct.code,
                    "account_name": acct.name,
                    "category": acct.category,
                    "opening_balance": opening,
                    "period_debit": period_debit,
                    "period_credit": period_credit,
                    "closing_balance": closing,
                    "ytd_debit": ytd_debit,
                    "ytd_credit": ytd_credit,
                })

            return balances

    async def get_monthly_trend(self, ledger_id: int, months: int = 6):
        """Get monthly revenue/expense trend."""
        async with get_db() as session:
            # Get income accounts (收入类)
            income_stmt = select(func.substr(Voucher.date, 1, 7).label("month"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("income"),
            ).join(JournalEntry, Voucher.id == JournalEntry.voucher_id).where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    Voucher.status == "posted",
                    JournalEntry.account_code >= "6000",
                    JournalEntry.account_code < "7000",
                )
            ).group_by(func.substr(Voucher.date, 1, 7)).order_by(
                func.substr(Voucher.date, 1, 7).desc()
            ).limit(months)
            result = await session.execute(income_stmt)
            income_rows = result.all()

            # Get expense accounts (费用类)
            expense_stmt = select(func.substr(Voucher.date, 1, 7).label("month"),
                func.coalesce(func.sum(JournalEntry.debit), 0).label("expense"),
            ).join(JournalEntry, Voucher.id == JournalEntry.voucher_id).where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    Voucher.status == "posted",
                    JournalEntry.account_code >= "5000",
                    JournalEntry.account_code < "6000",
                )
            ).group_by(func.substr(Voucher.date, 1, 7)).order_by(
                func.substr(Voucher.date, 1, 7).desc()
            ).limit(months)
            result = await session.execute(expense_stmt)
            expense_rows = result.all()

            return {"income": list(income_rows), "expense": list(expense_rows)}

    async def get_balance_sheet_data(self, ledger_id: int, year: int, month: int) -> dict:
        """Get balance sheet data using batch queries (fixes N+1 problem).

        Returns the same structure as database.report.get_balance_sheet().
        Uses 4 batch queries total instead of 30+ per-account queries.
        """
        async with get_db() as session:
            # 1. Get all active accounts with their categories
            acct_stmt = select(Account).where(Account.is_active == 1).order_by(Account.code)
            acct_result = await session.execute(acct_stmt)
            accounts = acct_result.scalars().all()
            account_codes = [a.code for a in accounts]
            acct_map = {a.code: a for a in accounts}

            if not accounts:
                return {
                    "date": f"{year}-{month:02d}",
                    "assets": [], "liabilities": [], "equity": [],
                    "total_assets": 0, "total_liab": 0, "total_equity": 0,
                }

            # 2. Batch: opening balances
            ob_stmt = select(
                OpeningBalance.account_code,
                OpeningBalance.balance,
            ).where(
                and_(
                    OpeningBalance.ledger_id == ledger_id,
                    OpeningBalance.account_code.in_(account_codes),
                    OpeningBalance.year == year,
                    OpeningBalance.month <= month,
                )
            ).order_by(OpeningBalance.account_code, OpeningBalance.month.desc())
            ob_result = await session.execute(ob_stmt)
            opening_map = {}
            for ob_row in ob_result.all():
                if ob_row.account_code not in opening_map:
                    opening_map[ob_row.account_code] = ob_row.balance

            # 3. Batch: YTD activity excluding closing entries (for most accounts)
            ytd_activity_stmt = select(
                JournalEntry.account_code,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    JournalEntry.ledger_id == ledger_id,
                    JournalEntry.account_code.in_(account_codes),
                    func.strftime("%Y", Voucher.date) == str(year),
                    func.cast(func.strftime("%m", Voucher.date), Integer) <= month,
                    Voucher.status == "posted",
                    (Voucher.description.is_(None) | ~Voucher.description.like("%结转%")),
                )
            ).group_by(JournalEntry.account_code)
            ytd_result = await session.execute(ytd_activity_stmt)
            ytd_map = {r.account_code: (r.total_debit, r.total_credit) for r in ytd_result.all()}

            # 4. Batch: raw YTD activity including closing entries (for 4103/4104)
            raw_ytd_stmt = select(
                JournalEntry.account_code,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    JournalEntry.ledger_id == ledger_id,
                    JournalEntry.account_code.in_(account_codes),
                    func.strftime("%Y", Voucher.date) == str(year),
                    func.cast(func.strftime("%m", Voucher.date), Integer) <= month,
                    Voucher.status == "posted",
                )
            ).group_by(JournalEntry.account_code)
            raw_ytd_result = await session.execute(raw_ytd_stmt)
            raw_ytd_map = {r.account_code: (r.total_debit, r.total_credit) for r in raw_ytd_result.all()}

            # ── Helper functions (pure computation, no DB access) ──

            def _end_bal(code):
                acct = acct_map.get(code)
                if not acct:
                    return 0.0
                cat = acct.category
                ob = opening_map.get(code, 0) or 0
                y_dr, y_cr = ytd_map.get(code, (0, 0))
                if cat in ("资产", "费用"):
                    o_dr = max(ob, 0)
                    o_cr = max(-ob, 0)
                    return (o_dr - o_cr) + (y_dr - y_cr)
                else:
                    o_cr = max(ob, 0)
                    o_dr = max(-ob, 0)
                    return (o_cr - o_dr) + (y_cr - y_dr)

            def _open_bal_signed(code):
                acct = acct_map.get(code)
                if not acct:
                    return 0.0
                cat = acct.category
                ob = opening_map.get(code, 0) or 0
                if cat in ("资产", "费用"):
                    return max(ob, 0) - max(-ob, 0)
                else:
                    return max(ob, 0) - max(-ob, 0)

            def _raw_end_bal(code):
                acct = acct_map.get(code)
                if not acct:
                    return 0.0
                cat = acct.category
                ob = opening_map.get(code, 0) or 0
                dr, cr = raw_ytd_map.get(code, (0, 0))
                if cat in ("资产", "费用"):
                    o_dr = max(ob, 0)
                    o_cr = max(-ob, 0)
                    return (o_dr - o_cr) + (dr - cr)
                else:
                    o_cr = max(ob, 0)
                    o_dr = max(-ob, 0)
                    return (o_cr - o_dr) + (cr - dr)

            def _raw_open_bal(code):
                return opening_map.get(code, 0) or 0

            def _dr_bal(code):
                acct = acct_map.get(code)
                if not acct:
                    return 0.0
                bal = _end_bal(code)
                if acct.category == "资产":
                    return max(bal, 0)
                else:
                    return max(-bal, 0)

            def _cr_bal(code):
                acct = acct_map.get(code)
                if not acct:
                    return 0.0
                bal = _end_bal(code)
                if acct.category == "资产":
                    return max(-bal, 0)
                else:
                    return max(bal, 0)

            def _dr_open(code):
                acct = acct_map.get(code)
                if not acct:
                    return 0.0
                bal = _open_bal_signed(code)
                if acct.category == "资产":
                    return max(bal, 0)
                else:
                    return max(-bal, 0)

            def _cr_open(code):
                acct = acct_map.get(code)
                if not acct:
                    return 0.0
                bal = _open_bal_signed(code)
                if acct.category == "资产":
                    return max(-bal, 0)
                else:
                    return max(bal, 0)

            def _add(target, code, name, level, end_val, open_val, cat, is_parent=False):
                target.append({
                    "code": code, "name": name, "level": level,
                    "end": round(end_val, 2), "open": round(open_val, 2),
                    "cat": cat, **({"is_parent": True} if is_parent else {}),
                })

            # ── Assets ──
            assets = []
            ca_end, ca_open = 0.0, 0.0

            # 货币资金
            cash_codes = [("1001", "库存现金"), ("1002", "银行存款"), ("1012", "其他货币资金")]
            cash_end = sum(max(_end_bal(c), 0) for c, _ in cash_codes)
            cash_open = sum(max(_open_bal_signed(c), 0) for c, _ in cash_codes)
            if cash_end or cash_open:
                _add(assets, "1000", "货币资金", 1, cash_end, cash_open, "流动资产", is_parent=True)
                for c, n in cash_codes:
                    ev, ov = max(_end_bal(c), 0), max(_open_bal_signed(c), 0)
                    if ev or ov:
                        _add(assets, c, n, 2, ev, ov, "流动资产")
                ca_end += cash_end
                ca_open += cash_open

            # 应收票据
            for code, name in [("1121", "应收票据")]:
                ev, ov = max(_end_bal(code), 0), max(_open_bal_signed(code), 0)
                if ev or ov:
                    _add(assets, code, name, 1, ev, ov, "流动资产")
                    ca_end += ev
                    ca_open += ov

            # 应收账款 = 应收账款(借方) + 预收账款(借方余额重分类)
            ar_end = _dr_bal("1122") + _dr_bal("2203")
            ar_open = _dr_open("1122") + _dr_open("2203")
            if ar_end or ar_open:
                _add(assets, "1122", "应收账款", 1, ar_end, ar_open, "流动资产", is_parent=True)
                for c, n in [("1122", "应收账款"), ("2203", "预收账款重分类")]:
                    ev, ov = _dr_bal(c), _dr_open(c)
                    if ev or ov:
                        _add(assets, c, n, 2, ev, ov, "流动资产")
                ca_end += ar_end
                ca_open += ar_open

            # 预付款项 = 预付账款(借方) + 应付账款(借方余额重分类)
            prepay_end = _dr_bal("1123") + _dr_bal("2202")
            prepay_open = _dr_open("1123") + _dr_open("2202")
            if prepay_end or prepay_open:
                _add(assets, "1123", "预付款项", 1, prepay_end, prepay_open, "流动资产", is_parent=True)
                for c, n in [("1123", "预付账款"), ("2202", "应付账款重分类")]:
                    ev, ov = _dr_bal(c), _dr_open(c)
                    if ev or ov:
                        _add(assets, c, n, 2, ev, ov, "流动资产")
                ca_end += prepay_end
                ca_open += prepay_open

            # 其他应收款
            for code, name in [("1221", "其他应收款")]:
                ev, ov = max(_end_bal(code), 0), max(_open_bal_signed(code), 0)
                if ev or ov:
                    _add(assets, code, name, 1, ev, ov, "流动资产")
                    ca_end += ev
                    ca_open += ov

            # 存货
            inv_codes = [
                ("1401", "材料采购"), ("1403", "原材料"), ("1402", "在途物资"),
                ("1411", "周转材料"), ("1405", "库存商品"), ("1406", "发出商品"),
                ("5101", "生产成本"), ("1408", "委托加工物资"),
            ]
            inv_end = sum(max(_end_bal(c), 0) for c, _ in inv_codes)
            inv_open = sum(max(_open_bal_signed(c), 0) for c, _ in inv_codes)
            if inv_end or inv_open:
                _add(assets, "1400", "存货", 1, inv_end, inv_open, "流动资产", is_parent=True)
                for c, n in inv_codes:
                    ev, ov = max(_end_bal(c), 0), max(_open_bal_signed(c), 0)
                    if ev or ov:
                        _add(assets, c, n, 2, ev, ov, "流动资产")
                ca_end += inv_end
                ca_open += inv_end
            _add(assets, "", "流动资产合计", 0, ca_end, ca_open, "流动资产_total")

            # 非流动资产
            nca_end, nca_open = 0.0, 0.0
            fv_g = _end_bal("1601")
            fv_g_open = _open_bal_signed("1601")
            fv_d = _end_bal("1602")
            fv_d_open = _open_bal_signed("1602")
            fv_imp = _end_bal("1603")
            fv_imp_open = _open_bal_signed("1603")
            fv_net = fv_g + fv_d + fv_imp
            fv_net_open = fv_g_open + fv_d_open + fv_imp_open
            if fv_g or fv_g_open or fv_d or fv_d_open or fv_imp or fv_imp_open:
                _add(assets, "1601", "固定资产原价", 1, fv_g, fv_g_open, "非流动资产", is_parent=True)
                _add(assets, "1602", "减：累计折旧", 2, -fv_d, -fv_d_open, "非流动资产")
                _add(assets, "1603", "减：固定资产减值准备", 2, -fv_imp, -fv_imp_open, "非流动资产")
                _add(assets, "1601N", "固定资产账面价值", 2, fv_net, fv_net_open, "非流动资产")
                nca_end += fv_net
                nca_open += fv_net_open

            # 无形资产
            ia_g = _end_bal("1701")
            ia_g_open = _open_bal_signed("1701")
            ia_a = _end_bal("1702")
            ia_a_open = _open_bal_signed("1702")
            ia_imp = _end_bal("1703")
            ia_imp_open = _open_bal_signed("1703")
            ia_net = ia_g + ia_a + ia_imp
            ia_net_open = ia_g_open + ia_a_open + ia_imp_open
            if ia_g or ia_g_open or ia_a or ia_a_open or ia_imp or ia_imp_open:
                _add(assets, "1701", "无形资产原价", 1, ia_g, ia_g_open, "非流动资产", is_parent=True)
                _add(assets, "1702", "减：累计摊销", 2, -ia_a, -ia_a_open, "非流动资产")
                _add(assets, "1703", "减：无形资产减值准备", 2, -ia_imp, -ia_imp_open, "非流动资产")
                _add(assets, "1701N", "无形资产账面价值", 2, ia_net, ia_net_open, "非流动资产")
                nca_end += ia_net
                nca_open += ia_net_open

            for code, name in [
                ("1501", "长期债券投资"), ("1511", "长期股权投资"), ("1521", "投资性房地产"),
                ("1604", "在建工程"), ("1605", "工程物资"), ("1606", "固定资产清理"),
                ("1801", "长期待摊费用"), ("1811", "递延所得税资产"),
                ("1901", "待处理财产损溢"),
            ]:
                ev, ov = max(_end_bal(code), 0), max(_open_bal_signed(code), 0)
                if ev or ov:
                    _add(assets, code, name, 1, ev, ov, "非流动资产")
                    nca_end += ev
                    nca_open += ov
            _add(assets, "", "非流动资产合计", 0, nca_end, nca_open, "非流动资产_total")

            total_assets = ca_end + nca_end
            total_assets_open = ca_open + nca_open
            _add(assets, "", "资产总计", 0, total_assets, total_assets_open, "total")

            # ── Liabilities ──
            liabilities = []
            cl_end, cl_open = 0.0, 0.0

            for code, name in [("2001", "短期借款"), ("2201", "应付票据")]:
                ev, ov = max(_end_bal(code), 0), max(_open_bal_signed(code), 0)
                if ev or ov:
                    _add(liabilities, code, name, 1, ev, ov, "流动负债")
                    cl_end += ev
                    cl_open += ov

            # 应付账款 = 应付账款(贷方) + 预付账款(贷方余额重分类)
            ap_end = _cr_bal("2202") + _cr_bal("1123")
            ap_open = _cr_open("2202") + _cr_open("1123")
            if ap_end or ap_open:
                _add(liabilities, "2202", "应付账款", 1, ap_end, ap_open, "流动负债", is_parent=True)
                for c, n in [("2202", "应付账款"), ("1123", "预付账款重分类")]:
                    ev, ov = _cr_bal(c), _cr_open(c)
                    if ev or ov:
                        _add(liabilities, c, n, 2, ev, ov, "流动负债")
                cl_end += ap_end
                cl_open += ap_open

            # 预收款项 = 预收账款(贷方) + 应收账款(贷方余额重分类)
            unearned_end = _cr_bal("2203") + _cr_bal("1122")
            unearned_open = _cr_open("2203") + _cr_open("1122")
            if unearned_end or unearned_open:
                _add(liabilities, "2203", "预收款项", 1, unearned_end, unearned_open, "流动负债", is_parent=True)
                for c, n in [("2203", "预收账款"), ("1122", "应收账款重分类")]:
                    ev, ov = _cr_bal(c), _cr_open(c)
                    if ev or ov:
                        _add(liabilities, c, n, 2, ev, ov, "流动负债")
                cl_end += unearned_end
                cl_open += unearned_open

            for code, name in [
                ("2211", "应付职工薪酬"), ("2221", "应交税费"),
                ("2231", "应付利息"), ("2232", "应付股利"), ("2241", "其他应付款"),
            ]:
                ev, ov = max(_end_bal(code), 0), max(_open_bal_signed(code), 0)
                if ev or ov:
                    _add(liabilities, code, name, 1, ev, ov, "流动负债")
                    cl_end += ev
                    cl_open += ov

            _add(liabilities, "", "流动负债合计", 0, cl_end, cl_open, "流动负债_total")

            # 非流动负债
            ncl_end, ncl_open = 0.0, 0.0
            for code, name in [
                ("2501", "长期借款"), ("2502", "应付债券"), ("2701", "长期应付款"),
                ("2801", "预计负债"), ("2401", "递延收益"), ("2901", "递延所得税负债"),
            ]:
                ev, ov = max(_end_bal(code), 0), max(_open_bal_signed(code), 0)
                if ev or ov:
                    _add(liabilities, code, name, 1, ev, ov, "非流动负债")
                    ncl_end += ev
                    ncl_open += ov
            _add(liabilities, "", "非流动负债合计", 0, ncl_end, ncl_open, "非流动负债_total")
            total_liab = cl_end + ncl_end
            _add(liabilities, "", "负债合计", 0, total_liab, cl_open + ncl_open, "liab_total")

            # ── Equity ──
            equity = []
            eq_end, eq_open = 0.0, 0.0
            for code, name in [("4001", "实收资本"), ("4002", "资本公积"), ("4101", "盈余公积")]:
                ev, ov = _end_bal(code), _open_bal_signed(code)
                if ev or ov:
                    _add(equity, code, name, 1, ev, ov, "权益")
                    eq_end += ev
                    eq_open += ov

            # 未分配利润 = 利润分配(4104) + 本年利润(4103) — use raw balances (incl. closing entries)
            rp4104_end = _raw_end_bal("4104")
            rp4103_end = _raw_end_bal("4103")
            rp4104_open = _raw_open_bal("4104")
            rp4103_open = _raw_open_bal("4103")
            rp_end = max(rp4104_end, 0) + rp4103_end
            rp_open = max(rp4104_open, 0) + rp4103_open
            if rp_end or rp_open:
                _add(equity, "4104N", "未分配利润", 1, rp_end, rp_open, "权益")
                eq_end += rp_end
                eq_open += rp_open

            total_equity = eq_end
            total_equity_open = eq_open
            _add(equity, "", "所有者权益合计", 0, total_equity, total_equity_open, "eq_total")
            _add(equity, "", "负债和所有者权益总计", 0,
                 total_liab + total_equity, cl_open + ncl_open + total_equity_open, "grand_total")

            return {
                "date": f"{year}-{month:02d}",
                "assets": assets, "liabilities": liabilities, "equity": equity,
                "total_assets": round(total_assets, 2),
                "total_liab": round(total_liab, 2),
                "total_equity": round(total_equity, 2),
            }

    async def get_income_statement_data(self, ledger_id: int, year: int, month: int) -> dict:
        """Get income statement data using batch queries (fixes N+1 problem).

        Returns the same structure as database.report.get_income_statement().
        Uses 4 batch queries total instead of 20+ per-account queries.
        """
        async with get_db() as session:
            # 1. Get all active accounts
            acct_stmt = select(Account).where(Account.is_active == 1).order_by(Account.code)
            acct_result = await session.execute(acct_stmt)
            accounts = acct_result.scalars().all()
            account_codes = [a.code for a in accounts]
            acct_map = {a.code: a for a in accounts}

            if not accounts:
                return {
                    "date": f"{year}-{month:02d}",
                    "rows": [],
                    "total_revenue": 0, "total_revenue_ytd": 0,
                    "total_expense": 0, "total_expense_ytd": 0,
                    "net_profit": 0, "net_profit_ytd": 0,
                    "summary": {
                        "total_revenue": 0, "total_revenue_ytd": 0,
                        "total_expense": 0, "total_expense_ytd": 0,
                        "net_profit": 0, "net_profit_ytd": 0,
                    },
                }

            # 2. Batch: period (current month) debit/credit excluding closing entries
            period_stmt = select(
                JournalEntry.account_code,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    JournalEntry.ledger_id == ledger_id,
                    JournalEntry.account_code.in_(account_codes),
                    func.strftime("%Y", Voucher.date) == str(year),
                    func.strftime("%m", Voucher.date) == f"{month:02d}",
                    Voucher.status == "posted",
                    (Voucher.description.is_(None) | ~Voucher.description.like("%结转%")),
                )
            ).group_by(JournalEntry.account_code)
            period_result = await session.execute(period_stmt)
            period_map = {r.account_code: (r.total_debit, r.total_credit) for r in period_result.all()}

            # 3. Batch: YTD (Jan-month) debit/credit excluding closing entries
            ytd_stmt = select(
                JournalEntry.account_code,
                func.coalesce(func.sum(JournalEntry.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntry.credit), 0).label("total_credit"),
            ).join(Voucher, JournalEntry.voucher_id == Voucher.id).where(
                and_(
                    JournalEntry.ledger_id == ledger_id,
                    JournalEntry.account_code.in_(account_codes),
                    func.strftime("%Y", Voucher.date) == str(year),
                    func.cast(func.strftime("%m", Voucher.date), Integer) <= month,
                    Voucher.status == "posted",
                    (Voucher.description.is_(None) | ~Voucher.description.like("%结转%")),
                )
            ).group_by(JournalEntry.account_code)
            ytd_result = await session.execute(ytd_stmt)
            ytd_map = {r.account_code: (r.total_debit, r.total_credit) for r in ytd_result.all()}

            # 4. Batch: child accounts (parent_code -> children mapping)
            child_stmt = select(Account.code, Account.name, Account.parent_code).where(
                and_(Account.parent_code.isnot(None), Account.is_active == 1)
            ).order_by(Account.code)
            child_result = await session.execute(child_stmt)
            children_map = {}
            for row in child_result.all():
                children_map.setdefault(row.parent_code, []).append(
                    {"code": row.code, "name": row.name}
                )

            def _period_vals(code):
                dr, cr = period_map.get(code, (0, 0))
                return dr, cr

            def _ytd_vals(code):
                dr, cr = ytd_map.get(code, (0, 0))
                return dr, cr

            def _expense_month(code=None, sub=None):
                acct = acct_map.get(code) if code else None
                if acct and acct.category == "费用":
                    dr, cr = _period_vals(code)
                    return round(dr - cr, 2)
                return 0

            def _expense_ytd(code=None, sub=None):
                acct = acct_map.get(code) if code else None
                if acct and acct.category == "费用":
                    dr, cr = _ytd_vals(code)
                    return round(dr - cr, 2)
                return 0

            def _revenue_month(code=None, sub=None):
                acct = acct_map.get(code) if code else None
                if acct and acct.category == "收入":
                    dr, cr = _period_vals(code)
                    return round(cr - dr, 2)
                return 0

            def _revenue_ytd(code=None, sub=None):
                acct = acct_map.get(code) if code else None
                if acct and acct.category == "收入":
                    dr, cr = _ytd_vals(code)
                    return round(cr - dr, 2)
                return 0

            def _child_accounts(parent_code):
                return children_map.get(parent_code, [])

            rows = []

            # 一、营业收入
            rows.append({"name": "一、营业收入", "code": "", "level": 0, "month": None, "ytd": None, "type": "header"})
            rev_codes = [a for a in accounts if a.category == "收入" and a.sub_category == "营业收入" and not a.parent_code]
            total_rev_month = 0
            total_rev_ytd = 0
            for r in rev_codes:
                children = _child_accounts(r.code)
                m_parent = _revenue_month(code=r.code)
                y_parent = _revenue_ytd(code=r.code)
                if m_parent or y_parent:
                    rows.append({"name": r.name, "code": r.code, "level": 1, "month": m_parent, "ytd": y_parent, "type": "revenue_item"})
                    total_rev_month += m_parent
                    total_rev_ytd += y_parent
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
            for ch in _child_accounts("6401"):
                m = _expense_month(code=ch["code"])
                y = _expense_ytd(code=ch["code"])
                if m or y:
                    rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})
            rows.append({"name": "减：营业成本", "code": "", "level": 0, "month": cogs_month, "ytd": cogs_ytd, "type": "expense_header"})

            # 税金及附加
            tax_month = _expense_month(code="6403")
            tax_ytd = _expense_ytd(code="6403")
            rows.append({"name": "税金及附加", "code": "6403", "level": 0, "month": tax_month, "ytd": tax_ytd, "type": "expense_header"})
            for ch in _child_accounts("6403"):
                m = _expense_month(code=ch["code"])
                y = _expense_ytd(code=ch["code"])
                if m or y:
                    rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})

            # 销售费用
            sfa_month = _expense_month(code="6601")
            sfa_ytd = _expense_ytd(code="6601")
            rows.append({"name": "销售费用", "code": "6601", "level": 0, "month": sfa_month, "ytd": sfa_ytd, "type": "expense_header"})
            for ch in _child_accounts("6601"):
                m = _expense_month(code=ch["code"])
                y = _expense_ytd(code=ch["code"])
                if m or y:
                    rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})

            # 管理费用
            ma_month = _expense_month(code="6602")
            ma_ytd = _expense_ytd(code="6602")
            rows.append({"name": "管理费用", "code": "6602", "level": 0, "month": ma_month, "ytd": ma_ytd, "type": "expense_header"})
            for ch in _child_accounts("6602"):
                m = _expense_month(code=ch["code"])
                y = _expense_ytd(code=ch["code"])
                if m or y:
                    rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "expense_item"})

            # 研发费用
            rd_month = _expense_month(code="5001")
            rd_ytd = _expense_ytd(code="5001")
            rows.append({"name": "研发费用", "code": "5001", "level": 0, "month": rd_month, "ytd": rd_ytd, "type": "expense_header"})

            # 财务费用
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

            # 加：其他收益
            rows.append({"name": "加：其他收益", "code": "", "level": 1, "month": 0, "ytd": 0, "type": "revenue_item"})

            # 减：信用减值损失
            cl_month = _expense_month(code="6702")
            cl_ytd = _expense_ytd(code="6702")
            rows.append({"name": "减：信用减值损失", "code": "6702", "level": 0, "month": cl_month, "ytd": cl_ytd, "type": "expense_header"})

            # 减：资产减值损失
            imp_month = _expense_month(code="6701")
            imp_ytd = _expense_ytd(code="6701")
            rows.append({"name": "减：资产减值损失", "code": "6701", "level": 0, "month": imp_month, "ytd": imp_ytd, "type": "expense_header"})

            # 加：资产处置收益
            rows.append({"name": "加：资产处置收益", "code": "", "level": 1, "month": 0, "ytd": 0, "type": "revenue_item"})

            # 二、营业利润
            total_expense_month = cogs_month + tax_month + sfa_month + ma_month + rd_month + fa_month + cl_month + imp_month
            total_expense_ytd = cogs_ytd + tax_ytd + sfa_ytd + ma_ytd + rd_ytd + fa_ytd + cl_ytd + imp_ytd
            op_month = total_rev_month - total_expense_month + inv_month + fv_month
            op_ytd = total_rev_ytd - total_expense_ytd + inv_ytd + fv_ytd
            rows.append({"name": "二、营业利润", "code": "", "level": 0, "month": op_month, "ytd": op_ytd, "type": "subtotal"})

            # 加：营业外收入
            oi_month = _revenue_month(code="6301")
            oi_ytd = _revenue_ytd(code="6301")
            rows.append({"name": "加：营业外收入", "code": "6301", "level": 0, "month": oi_month, "ytd": oi_ytd, "type": "revenue_header"})
            for ch in _child_accounts("6301"):
                m = _revenue_month(code=ch["code"])
                y = _revenue_ytd(code=ch["code"])
                if m or y:
                    rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "revenue_item"})

            # 减：营业外支出
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

    async def get_ledger_info(self, ledger_id: int) -> dict:
        """Get ledger/company info for report headers."""
        async with get_db() as session:
            stmt = select(Ledger).where(Ledger.id == ledger_id)
            result = await session.execute(stmt)
            ledger = result.scalar_one_or_none()
            if not ledger:
                return {"company": "", "id": ledger_id}
            return {
                "id": ledger.id,
                "company": ledger.company if hasattr(ledger, "company") else "",
            }

    async def get_vouchers_for_export(self, ledger_id: int, year: int, month: int, limit: int = 10000) -> list:
        """Get vouchers with entries for CSV/PDF export."""
        async with get_db() as session:
            # Get vouchers for the period
            voucher_stmt = select(Voucher).where(
                and_(
                    Voucher.ledger_id == ledger_id,
                    func.strftime("%Y", Voucher.date) == str(year),
                    func.strftime("%m", Voucher.date) == f"{month:02d}",
                    Voucher.status == "posted",
                )
            ).order_by(Voucher.date, Voucher.voucher_no).limit(limit)
            voucher_result = await session.execute(voucher_stmt)
            vouchers = voucher_result.scalars().all()

            result = []
            for v in vouchers:
                # Get entries for each voucher
                entry_stmt = select(JournalEntry).where(
                    JournalEntry.voucher_id == v.id
                ).order_by(JournalEntry.id)
                entry_result = await session.execute(entry_stmt)
                entries = entry_result.scalars().all()

                entry_dicts = []
                for e in entries:
                    entry_dicts.append({
                        "account_code": e.account_code,
                        "account_name": e.account_name,
                        "debit": e.debit,
                        "credit": e.credit,
                    })

                result.append({
                    "voucher_no": v.voucher_no,
                    "date": v.date,
                    "description": v.description or "",
                    "status": v.status,
                    "total_debit": v.total_debit,
                    "total_credit": v.total_credit,
                    "entries": entry_dicts,
                })

            return result
