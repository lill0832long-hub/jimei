"""报表服务层 — 使用 Repository 模式"""
from app.services._utils import run_async, to_dict
from app.repository.report_repository import ReportRepository
from app.repository.invoice_repository import InvoiceRepository
from app.repository.cash_flow_repository import CashFlowRepository
from app.repository.dashboard_repository import DashboardRepository
from .budget_service import BudgetService

_report_repo = ReportRepository()
_invoice_repo = InvoiceRepository()
_cash_flow_repo = CashFlowRepository()
_dashboard_repo = DashboardRepository()


class ReportService:
    """报表生成"""

    # ── 科目余额表 ──
    @staticmethod
    def get_account_balances(ledger_id, year, month):
        return to_dict(run_async(_report_repo.get_account_balances(ledger_id, year, month)))

    # ── 资产负债表 ──
    @staticmethod
    def get_balance_sheet(ledger_id, year, month):
        return run_async(_report_repo.get_balance_sheet_data(ledger_id, year, month))

    # ── 利润表 ──
    @staticmethod
    def get_income_statement(ledger_id, year, month):
        return run_async(_report_repo.get_income_statement_data(ledger_id, year, month))

    # ── 现金流 ──
    @staticmethod
    def get_cash_flow_statement(ledger_id, year, month, method="direct"):
        return run_async(_cash_flow_repo.get_cash_flow_statement(ledger_id, year, month, method=method))

    @staticmethod
    def get_cash_flow_categories(ledger_id):
        return run_async(_cash_flow_repo.get_cash_flow_categories(ledger_id))

    @staticmethod
    def add_cash_flow_category(ledger_id, code, name, flow_type):
        return run_async(_cash_flow_repo.add_cash_flow_category(ledger_id, code, name, flow_type))

    @staticmethod
    def init_cash_flow_categories(ledger_id):
        return run_async(_cash_flow_repo.init_cash_flow_categories(ledger_id))

    @staticmethod
    def get_cash_flow_detail(ledger_id, cf_type, year, month):
        return run_async(_cash_flow_repo.get_cash_flow_detail(ledger_id, cf_type, year, month))

    # ── 期间对比 ──
    @staticmethod
    def get_period_compare_income(ledger_id, year, month):
        from app.utils.period import generate_periods
        periods = generate_periods(year, month, 3)
        return run_async(_dashboard_repo.get_period_compare_income(ledger_id, periods))

    @staticmethod
    def get_period_compare_balance(ledger_id, year, month):
        from app.utils.period import generate_periods
        periods = generate_periods(year, month, 3)
        return run_async(_dashboard_repo.get_period_compare_balance(ledger_id, periods))

    # ── Dashboard 指标 ──
    @staticmethod
    def get_dashboard_kpi(ledger_id, year, month):
        return run_async(_dashboard_repo.get_dashboard_kpi(ledger_id, year, month))

    @staticmethod
    def get_monthly_trend(ledger_id, months=6):
        return to_dict(run_async(_report_repo.get_monthly_trend(ledger_id, months=months)))

    @staticmethod
    def get_expense_breakdown(ledger_id, year, month):
        return run_async(_dashboard_repo.get_expense_breakdown(ledger_id, year, month))

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
        return run_async(_invoice_repo.link_voucher(ledger_id, invoice_id, voucher_no))

    @staticmethod
    def get_invoice_vouchers(ledger_id, invoice_id):
        return run_async(_invoice_repo.get_vouchers(ledger_id, invoice_id))

    @staticmethod
    def get_invoice_summary(ledger_id, year=None, month=None):
        return run_async(_invoice_repo.get_summary(ledger_id, year=year, month=month))

    @staticmethod
    def ocr_recognize_invoice(file_path):
        # NOTE: involves file processing + OCR, keep old implementation for now
        from database.invoice import ocr_recognize_invoice
        return ocr_recognize_invoice(file_path)

    # ── CSV/PDF 导出 ──
    # Data fetching uses async repository; file generation (reportlab/openpyxl/csv) stays sync.
    @staticmethod
    def export_balance_sheet_csv(ledger_id, year, month, filepath):
        import csv
        bs = run_async(_report_repo.get_balance_sheet_data(ledger_id, year, month))
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([f'资产负债表', f'编制日期: {bs["date"]}'])
            writer.writerow([])
            writer.writerow(['资产', '期末数', '年初数', '', '负债和所有者权益', '期末数', '年初数'])
            asset_rows = [(item['name'], item['end'], item['open']) for item in bs['assets']]
            liab_eq_rows = [(item['name'], item['end'], item['open']) for item in bs['liabilities']]
            liab_eq_rows += [(item['name'], item['end'], item['open']) for item in bs['equity']]
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

    @staticmethod
    def export_income_statement_csv(ledger_id, year, month, filepath):
        import csv
        inc = run_async(_report_repo.get_income_statement_data(ledger_id, year, month))
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

    @staticmethod
    def export_account_balances_csv(ledger_id, year, month, filepath):
        import csv
        balances = run_async(_report_repo.get_account_balances(ledger_id, year, month))
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['科目余额表', f'{year}-{month:02d}'])
            writer.writerow([])
            writer.writerow(['科目编码', '科目名称', '期初借方', '期初贷方', '本期借方', '本期贷方', '累计借方', '累计贷方', '期末借方', '期末贷方'])
            for b in balances:
                def fmt(v):
                    return round(v, 2) if v else ''
                opening_dr = max(b['opening_balance'], 0) if b['opening_balance'] else 0
                opening_cr = max(-(b['opening_balance'] or 0), 0)
                closing_dr = max(b['closing_balance'], 0) if b['closing_balance'] else 0
                closing_cr = max(-(b['closing_balance'] or 0), 0)
                writer.writerow([b['account_code'], b['account_name'],
                                 fmt(opening_dr), fmt(opening_cr),
                                 fmt(b['period_debit']), fmt(b['period_credit']),
                                 fmt(b['ytd_debit']), fmt(b['ytd_credit']),
                                 fmt(closing_dr), fmt(closing_cr)])
        return len(balances)

    @staticmethod
    def export_vouchers_csv(ledger_id, year, month, filepath):
        import csv
        vouchers = run_async(_report_repo.get_vouchers_for_export(ledger_id, year, month, limit=10000))
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['凭证号', '日期', '摘要', '科目代码', '科目名称', '借方', '贷方', '状态'])
            for v in vouchers:
                status_label = {'draft': '草稿', 'posted': '已过账', 'reversed': '已冲销'}.get(v['status'], v['status'])
                for e in v.get('entries', []):
                    writer.writerow([v['voucher_no'], v['date'], v['description'],
                                     e['account_code'], e['account_name'],
                                     e['debit'] or '', e['credit'] or '', status_label])
        return len(vouchers)

    @staticmethod
    def export_balance_sheet_pdf(ledger_id, year, month, filepath):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from datetime import datetime

        bs = run_async(_report_repo.get_balance_sheet_data(ledger_id, year, month))
        ledger_info = run_async(_report_repo.get_ledger_info(ledger_id))
        company = ledger_info.get("company", "")

        try:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            cjk_font = 'STSong-Light'
        except Exception:
            cjk_font = 'Helvetica'

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                leftMargin=15*mm, rightMargin=15*mm,
                                topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'], fontName=cjk_font, fontSize=16)
        normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName=cjk_font, fontSize=9)
        bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName=cjk_font, fontSize=9, bold=True)

        elements = []
        elements.append(Paragraph("资产负债表", title_style))
        elements.append(Paragraph(f"{company}  {bs['date']}", normal_style))
        elements.append(Spacer(1, 5*mm))

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
            row.append("")
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

        diff = abs(bs['total_assets'] - (bs['total_liab'] + bs['total_equity']))
        balance_text = f"平衡校验：{'平衡' if diff < 0.01 else f'差额 {diff:,.2f}'}"
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(balance_text, normal_style))
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph(f"打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}    第 1 页", normal_style))
        doc.build(elements)

    @staticmethod
    def export_income_statement_pdf(ledger_id, year, month, filepath):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from datetime import datetime

        inc = run_async(_report_repo.get_income_statement_data(ledger_id, year, month))
        ledger_info = run_async(_report_repo.get_ledger_info(ledger_id))
        company = ledger_info.get("company", "")

        try:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            cjk_font = 'STSong-Light'
        except Exception:
            cjk_font = 'Helvetica'

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                leftMargin=15*mm, rightMargin=15*mm,
                                topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'], fontName=cjk_font, fontSize=16)
        normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName=cjk_font, fontSize=9)
        bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName=cjk_font, fontSize=9, bold=True)

        elements = []
        elements.append(Paragraph("利润表", title_style))
        elements.append(Paragraph(f"{company}  {inc['date']}", normal_style))
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

    @staticmethod
    def export_account_balances_pdf(ledger_id, year, month, filepath):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from datetime import datetime

        balances = run_async(_report_repo.get_account_balances(ledger_id, year, month))
        ledger_info = run_async(_report_repo.get_ledger_info(ledger_id))
        company = ledger_info.get("company", "")

        try:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            cjk_font = 'STSong-Light'
        except Exception:
            cjk_font = 'Helvetica'

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                leftMargin=15*mm, rightMargin=15*mm,
                                topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'], fontName=cjk_font, fontSize=16)
        normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName=cjk_font, fontSize=8)
        bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName=cjk_font, fontSize=8, bold=True)

        elements = []
        elements.append(Paragraph("科目余额表", title_style))
        elements.append(Paragraph(f"{company}  {year}年{month}月", normal_style))
        elements.append(Spacer(1, 5*mm))

        header = ["科目代码", "科目名称", "期初借方", "期初贷方", "本期借方", "本期贷方", "期末借方", "期末贷方"]
        data = [[Paragraph(h, bold_style) for h in header]]

        for b in balances:
            indent = "&nbsp;&nbsp;" if b.get("level", 0) > 0 else ""
            name_style = bold_style if b.get("level", 0) == 0 else normal_style
            opening_dr = max(b.get('opening_balance', 0), 0) if b.get('opening_balance') else 0
            opening_cr = max(-(b.get('opening_balance') or 0), 0)
            closing_dr = max(b.get('closing_balance', 0), 0) if b.get('closing_balance') else 0
            closing_cr = max(-(b.get('closing_balance') or 0), 0)
            data.append([
                Paragraph(b["account_code"], normal_style),
                Paragraph(f"{indent}{b['account_name']}", name_style),
                Paragraph(f"{opening_dr:,.2f}" if opening_dr else "", normal_style),
                Paragraph(f"{opening_cr:,.2f}" if opening_cr else "", normal_style),
                Paragraph(f"{b.get('period_debit', 0):,.2f}" if b.get('period_debit') else "", normal_style),
                Paragraph(f"{b.get('period_credit', 0):,.2f}" if b.get('period_credit') else "", normal_style),
                Paragraph(f"{closing_dr:,.2f}" if closing_dr else "", normal_style),
                Paragraph(f"{closing_cr:,.2f}" if closing_cr else "", normal_style),
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

    @staticmethod
    def export_vouchers_pdf(ledger_id, year, month, filepath):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from datetime import datetime

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

        vouchers = run_async(_report_repo.get_vouchers_for_export(ledger_id, year, month, limit=1000))
        for v in vouchers:
            elements.append(Paragraph(
                "凭证号：{}  日期：{}  {}".format(v["voucher_no"], v["date"], v["description"]),
                cn_style
            ))
            table_data = [["科目代码", "科目名称", "借方金额", "贷方金额"]]
            for row in v.get("entries", []):
                table_data.append([
                    row["account_code"], row["account_name"],
                    "{:,.2f}".format(row["debit"]) if row["debit"] else "",
                    "{:,.2f}".format(row["credit"]) if row["credit"] else "",
                ])
            table_data.append(["", "合计", "{:,.2f}".format(v["total_debit"]), "{:,.2f}".format(v["total_credit"])])
            t = Table(table_data, colWidths=[30*mm, 50*mm, 30*mm, 30*mm])
            t.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'STSong-Light'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, -1), (-1, -1), 'STSong-Light'),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 3*mm))

        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph("打印时间：{}    第 1 页".format(datetime.now().strftime('%Y-%m-%d %H:%M')), cn_style))
        doc.build(elements)