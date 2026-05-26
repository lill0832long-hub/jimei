"""Database module: invoice domain"""

from .connection import get_conn, transaction, DB_PATH

def extract_invoice_info(text: str) -> dict:
    """
    从 OCR 文本中提取发票信息
    返回结构化数据
    """
    import re
    result = {
        "invoice_no": None,
        "date": None,
        "amount": None,
        "tax_amount": None,
        "seller": None,
        "buyer": None,
        "items": [],
    }

    # 发票号码 — 支持 "发票号码：xxx", "发票号xxx", "NO.xxx"
    m = re.search(r'发票号码[：:\s]*(\w+)', text)
    if not m:
        m = re.search(r'发票号[：:\s]*(\w+)', text)
    if not m:
        m = re.search(r'(?:^|[^\w])NO\.(\w+)', text)
    if not m:
        m = re.search(r'号码[：:\s]*(\w+)', text)
    if m:
        result["invoice_no"] = m.group(1)

    # 日期 — 支持 "2026-03-15", "2026/03/15", "2026年3月15日"
    m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', text)
    if m:
        result["date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if not result["date"]:
        m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日?', text)
        if m:
            result["date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # 金额 — 支持 "金额5000元", "金额：5000", "5000元", "¥5000", "5000.00", "价税合计"
    m = re.search(r'(?:价税合计|合计|总金额|金额)[：:\s]*[¥￥]?([\d,]+(?:\.\d+)?)', text)
    if not m:
        m = re.search(r'[¥￥]([\d,]+(?:\.\d+)?)', text)
    if not m:
        m = re.search(r'([\d,]+(?:\.\d+)?)\s*元', text)
    if not m:
        m = re.search(r'(?<!\d)(\d[\d,]*(?:\.\d+)?)(?![\d%])', text)
    if m:
        result["amount"] = float(m.group(1).replace(',', ''))

    # 税额 — 支持 "税额：xxx", "税率13%", "13%税率", "税率：13%"
    m = re.search(r'(?:税额|税金)[：:\s]*[¥￥]?([\d,]+(?:\.\d+)?)', text)
    if m:
        result["tax_amount"] = float(m.group(1).replace(',', ''))
    if not result["tax_amount"]:
        m = re.search(r'税率[：:\s]*(\d+\.?\d*)%', text)
        if not m:
            m = re.search(r'(\d+\.?\d*)%\s*税率', text)
        if m and result["amount"]:
            rate = float(m.group(1)) / 100
            result["tax_amount"] = round(result["amount"] * rate / (1 + rate), 2)

    # 销方/购方
    m = re.search(r'销[售方][：:\s]*(\S+)', text)
    if m:
        result["seller"] = m.group(1)
    m = re.search(r'购[买方][：:\s]*(\S+)', text)
    if m:
        result["buyer"] = m.group(1)

    return result

def get_invoices(ledger_id: int, invoice_type: str = None, status: str = None) -> list:
    """获取发票列表"""
    conn = get_conn()
    try:
        query = "SELECT * FROM invoices WHERE ledger_id = ?"
        params = [ledger_id]
        if invoice_type:
            query += " AND invoice_type = ?"
            params.append(invoice_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY invoice_date DESC, created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def add_invoice(ledger_id: int, invoice_type: str, invoice_no: str, **kwargs) -> int:
    """添加发票"""
    conn = get_conn()
    try:
        fields = ["ledger_id", "invoice_type", "invoice_no"]
        values = [ledger_id, invoice_type, invoice_no]
        for k, v in kwargs.items():
            if k in ("invoice_date", "seller_name", "seller_tax_no", "buyer_name", "buyer_tax_no",
                     "total_amount", "tax_amount", "total_with_tax", "status", "ocr_data", "file_path", "remark"):
                fields.append(k)
                values.append(v)
        placeholders = ",".join(["?"] * len(fields))
        conn.execute(f"INSERT INTO invoices ({','.join(fields)}) VALUES ({placeholders})", values)
        conn.commit()
        iid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return iid
    finally:
        conn.close()

def get_invoice_summary(ledger_id: int) -> dict:
    """获取发票汇总统计"""
    conn = get_conn()
    try:
        # 进项发票
        input_count = conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total_with_tax), 0) as total "
            "FROM invoices WHERE ledger_id = ? AND invoice_type = 'input'",
            (ledger_id,)
        ).fetchone()
        # 销项发票
        output_count = conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total_with_tax), 0) as total "
            "FROM invoices WHERE ledger_id = ? AND invoice_type = 'output'",
            (ledger_id,)
        ).fetchone()
        # 未核验
        unverified = conn.execute(
            "SELECT COUNT(*) as cnt FROM invoices WHERE ledger_id = ? AND status = 'unverified'",
            (ledger_id,)
        ).fetchone()["cnt"]
        return {
            "input_count": input_count["cnt"],
            "input_total": input_count["total"],
            "output_count": output_count["cnt"],
            "output_total": output_count["total"],
            "unverified_count": unverified,
        }
    finally:
        conn.close()

def ocr_recognize_invoice(file_path: str) -> dict:
    """
    OCR 识别发票（预留接口）
    返回结构：{invoice_no, invoice_date, seller_name, total_amount, tax_amount, ...}
    """
    # TODO: 接入 OCR 服务（如百度OCR、腾讯云OCR等）
    # 当前返回模拟数据
    return {
        "invoice_no": "",
        "invoice_date": "",
        "seller_name": "",
        "seller_tax_no": "",
        "buyer_name": "",
        "buyer_tax_no": "",
        "total_amount": 0,
        "tax_amount": 0,
        "total_with_tax": 0,
        "status": "mock",
        "message": "OCR接口预留，请接入实际OCR服务",
    }
