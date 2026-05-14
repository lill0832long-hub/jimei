"""报表服务层 — 使用 Repository 模式"""
from app.services._utils import run_async, to_dict
from app.repository.report_repository import ReportRepository
from app.repository.invoice_repository import InvoiceRepository
from .budget_service import BudgetService

_report_repo = ReportRepository()
_invoice_repo = InvoiceRepository()


class ReportService:
    """报表生成"""

    # ── 科目余额表 ──
    @staticmethod
    def get_account_balances(ledger_id, year, month):
        return to_dict(run_async(_report_repo.get_account_balances(ledger_id, year, month)))

    # ── 资产负债表 ──
    @staticmethod
    def get_balance_sheet(ledger_id, year, month):
        balances = run_async(_report_repo.get_account_balances(ledger_id, year, month))
        # Return flat lists for assets/liabilities/equity with row-level details
        assets = []
        liabilities = []
        equity = []
        total_assets = 0
        total_liab = 0
        total_equity = 0

        for b in balances:
            cat = b["category"]
            closing = b["closing_balance"]
            row = {
                "name": b["account_name"],
                "code": b["account_code"],
                "end": closing,
                "open": b["opening_balance"],
                "level": 1,
            }
            if cat == "资产":
                assets.append(row)
                total_assets += closing
            elif cat == "负债":
                liabilities.append(row)
                total_liab += closing
            elif cat == "权益":
                equity.append(row)
                total_equity += closing

        return {
            "date": f"{year}-{month:02d}",
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "total_assets": total_assets,
            "total_liab": total_liab,
            "total_equity": total_equity,
            "total_liabilities_equity": total_liab + total_equity,
        }

    # ── 利润表 ──
    @staticmethod
    def get_income_statement(ledger_id, year, month):
        balances = run_async(_report_repo.get_account_balances(ledger_id, year, month))
        rows = []
        total_revenue = 0
        total_expense = 0

        # Revenue items
        rows.append({"name": "一、营业收入", "code": "", "level": 0, "month": None, "ytd": None, "type": "header"})
        for b in balances:
            if b["category"] == "收入":
                ytd = b["period_credit"]
                rows.append({
                    "name": b["account_name"],
                    "code": b["account_code"],
                    "level": 1,
                    "month": ytd,
                    "ytd": ytd,
                    "type": "revenue_item",
                })
                total_revenue += ytd
        rows.append({"name": "营业收入合计", "code": "", "level": 0, "month": total_revenue, "ytd": total_revenue, "type": "rev_total"})

        # Expense items
        rows.append({"name": "减：营业成本及费用", "code": "", "level": 0, "month": None, "ytd": None, "type": "expense_header"})
        for b in balances:
            if b["category"] == "费用":
                ytd = b["period_debit"]
                rows.append({
                    "name": b["account_name"],
                    "code": b["account_code"],
                    "level": 1,
                    "month": ytd,
                    "ytd": ytd,
                    "type": "expense_item",
                })
                total_expense += ytd
        rows.append({"name": "费用合计", "code": "", "level": 0, "month": total_expense, "ytd": total_expense, "type": "subtotal"})

        net = total_revenue - total_expense
        rows.append({"name": "净利润", "code": "", "level": 0, "month": net, "ytd": net, "type": "total"})

        return {
            "rows": rows,
            "revenue": [b for b in balances if b["category"] == "收入"],
            "expenses": [b for b in balances if b["category"] == "费用"],
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_income": net,
            "net_profit": net,
        }

    # ── 现金流（暂保留旧实现） ──
    @staticmethod
    def get_cash_flow_statement(ledger_id, year, month):
        # TODO: migrate to repository pattern
        from database.cash_flow import get_cash_flow_statement
        return get_cash_flow_statement(ledger_id, year, month)

    @staticmethod
    def get_cash_flow_categories(ledger_id):
        # TODO: migrate to repository pattern
        from database.cash_flow import get_cash_flow_categories
        return get_cash_flow_categories(ledger_id)

    @staticmethod
    def add_cash_flow_category(ledger_id, name, flow_type):
        # TODO: migrate to repository pattern
        from database.cash_flow import add_cash_flow_category
        return add_cash_flow_category(ledger_id, name, flow_type)

    @staticmethod
    def init_cash_flow_categories(ledger_id):
        # TODO: migrate to repository pattern
        from database.cash_flow import init_cash_flow_categories
        return init_cash_flow_categories(ledger_id)

    @staticmethod
    def get_cash_flow_detail(ledger_id, cf_type, year, month):
        # TODO: migrate to repository pattern
        from database.connection import get_conn
        conn = get_conn()
        rows = conn.execute("""
            SELECT v.voucher_no, v.date, v.summary,
                   a.code as acct_code, a.name as acct_name,
                   e.debit, e.credit
            FROM vouchers v
            JOIN entries e ON e.voucher_id = v.id
            JOIN accounts a ON a.id = e.account_id
            JOIN entry_cash_flow ecf ON ecf.entry_id = e.id
            JOIN cash_flow_categories cfc ON cfc.id = ecf.cf_category_id
            WHERE v.ledger_id = ? AND cfc.code = ?
              AND strftime('%Y-%m', v.date) = ?
            ORDER BY v.date DESC
            LIMIT 50
        """, (ledger_id, cf_type, f"{year}-{month:02d}")).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── 期间对比（暂保留旧实现） ──
    @staticmethod
    def get_period_compare_income(ledger_id, year, month):
        from app.utils.period import generate_periods
        periods = generate_periods(year, month, 3)
        from database.dashboard import get_period_compare_income
        return get_period_compare_income(ledger_id, periods)

    @staticmethod
    def get_period_compare_balance(ledger_id, year, month):
        from app.utils.period import generate_periods
        periods = generate_periods(year, month, 3)
        from database.dashboard import get_period_compare_balance
        return get_period_compare_balance(ledger_id, periods)

    # ── Dashboard 指标 ──
    @staticmethod
    def get_dashboard_kpi(ledger_id, year, month):
        # TODO: migrate to repository pattern
        from database.dashboard import get_dashboard_kpi
        return get_dashboard_kpi(ledger_id, year, month)

    @staticmethod
    def get_monthly_trend(ledger_id, months=6):
        return to_dict(run_async(_report_repo.get_monthly_trend(ledger_id, months=months)))

    @staticmethod
    def get_expense_breakdown(ledger_id, year, month):
        # TODO: migrate to repository pattern
        from database.dashboard import get_expense_breakdown
        return get_expense_breakdown(ledger_id, year, month)

    # ── 预算汇总（委托给 BudgetService） ──
    @staticmethod
    def get_budgets(ledger_id, year=None):
        return BudgetService.get_all(ledger_id, year)

    @staticmethod
    def set_budget(ledger_id, account_code, year, month, amount):
        return BudgetService.set(ledger_id, account_code, None, year, month, amount)

    @staticmethod
    def get_budget_execution(ledger_id, year, month):
        return BudgetService.get_execution(ledger_id, year, month)

    @staticmethod
    def get_budget_summary(ledger_id, year):
        return BudgetService.get_summary(ledger_id, year)

    # ── 发票 ──
    @staticmethod
    def get_invoices(ledger_id, **kwargs):
        return to_dict(run_async(_invoice_repo.get_by_ledger(ledger_id, **kwargs)))

    @staticmethod
    def add_invoice(ledger_id, **kwargs):
        return to_dict(run_async(_invoice_repo.create(ledger_id=ledger_id, **kwargs)))

    @staticmethod
    def link_invoice_voucher(ledger_id, invoice_id, voucher_no):
        # TODO: migrate to repository pattern
        from database.voucher import link_invoice_voucher
        return link_invoice_voucher(ledger_id, invoice_id, voucher_no)

    @staticmethod
    def get_invoice_vouchers(ledger_id, invoice_id):
        # TODO: migrate to repository pattern
        from database.voucher import get_invoice_vouchers
        return get_invoice_vouchers(ledger_id, invoice_id)

    @staticmethod
    def get_invoice_summary(ledger_id, year=None, month=None):
        # TODO: migrate to repository pattern
        from database.invoice import get_invoice_summary
        return get_invoice_summary(ledger_id)

    @staticmethod
    def ocr_recognize_invoice(file_path):
        # TODO: migrate to repository pattern
        from database.invoice import ocr_recognize_invoice
        return ocr_recognize_invoice(file_path)

    # ── CSV/PDF 导出（暂保留旧实现） ──
    @staticmethod
    def export_balance_sheet_csv(ledger_id, year, month, filepath):
        # TODO: migrate to repository pattern
        from database.report import export_balance_sheet_csv
        return export_balance_sheet_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_income_statement_csv(ledger_id, year, month, filepath):
        # TODO: migrate to repository pattern
        from database.report import export_income_statement_csv
        return export_income_statement_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_account_balances_csv(ledger_id, year, month, filepath):
        # TODO: migrate to repository pattern
        from database.report import export_account_balances_csv
        return export_account_balances_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_vouchers_csv(ledger_id, year, month, filepath):
        # TODO: migrate to repository pattern
        from database.report import export_vouchers_csv
        return export_vouchers_csv(ledger_id, year, month, filepath)

    @staticmethod
    def export_balance_sheet_pdf(ledger_id, year, month, filepath):
        # TODO: migrate to repository pattern
        from database.report import export_balance_sheet_pdf
        return export_balance_sheet_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_income_statement_pdf(ledger_id, year, month, filepath):
        # TODO: migrate to repository pattern
        from database.report import export_income_statement_pdf
        return export_income_statement_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_account_balances_pdf(ledger_id, year, month, filepath):
        # TODO: migrate to repository pattern
        from database.report import export_account_balances_pdf
        return export_account_balances_pdf(ledger_id, year, month, filepath)

    @staticmethod
    def export_vouchers_pdf(ledger_id, year, month, filepath):
        # TODO: migrate to repository pattern
        from database.report import export_vouchers_pdf
        return export_vouchers_pdf(ledger_id, year, month, filepath)
