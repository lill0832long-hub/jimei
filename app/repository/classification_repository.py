"""Classification repository — bank CSV parsing, transaction classification, and rule management."""
import csv
import io
from sqlalchemy import select, and_, func, text
from app.models.voucher import Voucher, JournalEntry
from app.models.base import get_db
from .base import BaseRepository


# Default classification rules (keyword-based)
DEFAULT_CLASSIFICATION_RULES = [
    {"keywords": ["差旅", "交通", "机票", "火车票", "打车"], "account_code": "6602", "account_name": "管理费用-差旅费", "category": "差旅"},
    {"keywords": ["办公", "文具", "打印", "复印"], "account_code": "6602", "account_name": "管理费用-办公费", "category": "办公"},
    {"keywords": ["工资", "薪酬", "社保", "公积金"], "account_code": "2211", "account_name": "应付职工薪酬", "category": "薪酬"},
    {"keywords": ["租金", "房租", "物业"], "account_code": "6602", "account_name": "管理费用-租金", "category": "租金"},
    {"keywords": ["水电", "电费", "水费"], "account_code": "6602", "account_name": "管理费用-水电费", "category": "水电"},
    {"keywords": ["银行", "手续费", "利息"], "account_code": "6603", "account_name": "财务费用", "category": "财务"},
    {"keywords": ["销售", "广告", "推广", "营销"], "account_code": "6601", "account_name": "销售费用", "category": "销售"},
    {"keywords": ["采购", "材料", "原料", "库存"], "account_code": "1403", "account_name": "原材料", "category": "采购"},
    {"keywords": ["收入", "收款", "回款"], "account_code": "6001", "account_name": "主营业务收入", "category": "收入"},
    {"keywords": ["税费", "增值税", "所得税", "税金"], "account_code": "2221", "account_name": "应交税费", "category": "税费"},
    {"keywords": ["固定资产", "设备", "机器"], "account_code": "1601", "account_name": "固定资产", "category": "资产"},
    {"keywords": ["借款", "贷款", "融资"], "account_code": "2001", "account_name": "短期借款", "category": "借款"},
]


class ClassificationRepository(BaseRepository):
    """Transaction classification and bank CSV parsing."""

    # ── Pure functions (no DB) ──

    @staticmethod
    def parse_bank_csv(file_content, encoding="utf-8"):
        """Parse bank CSV/TSV file, supporting common bank formats.

        Returns list of transaction dicts with keys: date, summary, amount,
        direction, counterparty, balance.
        """
        text_content = file_content.decode(encoding) if isinstance(file_content, bytes) else file_content
        lines = text_content.strip().split("\n")
        if not lines:
            return []
        delimiter = "\t" if "\t" in lines[0] else ","
        reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
        transactions = []
        col_mapping = {
            "date": ["交易日期", "日期", "transaction_date", "日期时间", "记账日期", "交易时间", "时间"],
            "summary": ["摘要", "交易摘要", "备注", "description", "用途", "交易说明", "对方户名摘要", "摘要说明"],
            "amount": ["金额", "交易金额", "amount", "发生额", "金额(元)"],
            "direction": ["借贷", "收支", "direction", "收/支", "交易类型", "借方贷方"],
            "debit": ["借方", "支出", "debit", "借方金额", "支出金额"],
            "credit": ["贷方", "收入", "credit", "贷方金额", "收入金额"],
            "counterparty": ["对方户名", "对方账号", "交易对手", "counterparty", "户名", "对方名称", "收/付款人"],
            "balance": ["余额", "账户余额", "balance", "当前余额"],
        }

        def find_col(row, candidates):
            for c in candidates:
                for key in row.keys():
                    if c in key.strip():
                        return key
            return None

        for row in reader:
            if not any(row.values()):
                continue
            date_col = find_col(row, col_mapping["date"])
            summary_col = find_col(row, col_mapping["summary"])
            amount_col = find_col(row, col_mapping["amount"])
            direction_col = find_col(row, col_mapping["direction"])
            debit_col = find_col(row, col_mapping["debit"])
            credit_col = find_col(row, col_mapping["credit"])
            counterparty_col = find_col(row, col_mapping["counterparty"])
            balance_col = find_col(row, col_mapping["balance"])
            txn = {}
            if date_col and row.get(date_col, "").strip():
                txn["date"] = row[date_col].strip()
            else:
                continue
            txn["summary"] = row[summary_col].strip() if summary_col and row.get(summary_col) else ""
            txn["counterparty"] = row[counterparty_col].strip() if counterparty_col and row.get(counterparty_col) else ""
            amount = 0
            direction = "debit"
            if amount_col and row.get(amount_col, "").strip():
                amt_str = row[amount_col].strip().replace(",", "").replace("¥", "").replace("￥", "")
                try:
                    amount = abs(float(amt_str))
                    direction = "credit" if float(amt_str) > 0 else "debit"
                except ValueError:
                    amount = 0
            elif debit_col or credit_col:
                debit_val = 0
                credit_val = 0
                if debit_col and row.get(debit_col, "").strip():
                    try:
                        debit_val = abs(float(row[debit_col].strip().replace(",", "").replace("¥", "")))
                    except ValueError:
                        pass
                if credit_col and row.get(credit_col, "").strip():
                    try:
                        credit_val = abs(float(row[credit_col].strip().replace(",", "").replace("¥", "")))
                    except ValueError:
                        pass
                if debit_val > 0:
                    amount = debit_val
                    direction = "debit"
                elif credit_val > 0:
                    amount = credit_val
                    direction = "credit"
            if direction_col and row.get(direction_col, "").strip():
                d = row[direction_col].strip()
                if d in ("借", "收", "收入", "CR", "贷方", "存入"):
                    direction = "credit"
                elif d in ("贷", "支", "支出", "DR", "借方", "取出"):
                    direction = "debit"
            txn["amount"] = amount
            txn["direction"] = direction
            if balance_col and row.get(balance_col, "").strip():
                try:
                    txn["balance"] = float(row[balance_col].strip().replace(",", "").replace("¥", ""))
                except ValueError:
                    txn["balance"] = 0
            else:
                txn["balance"] = 0
            if amount > 0:
                transactions.append(txn)
        return transactions

    # ── DB-backed classification ──

    async def classify_transaction(self, ledger_id: int, summary: str, amount: float,
                                   direction: str, counterparty: str = "") -> dict:
        """Classify a single transaction using keyword rules and history matching."""
        text = f"{summary} {counterparty}"

        best_match = None
        best_score = 0
        for rule in DEFAULT_CLASSIFICATION_RULES:
            score = 0
            for kw in rule["keywords"]:
                if kw in text:
                    score += len(kw)
            if score > best_score:
                best_score = score
                best_match = rule

        if best_match and best_score > 0:
            confidence = min(0.5 + best_score * 0.1, 0.95)
            account_code = best_match["account_code"]
            account_name = best_match["account_name"]
            category = best_match["category"]
        else:
            hist_result = await self._match_history(ledger_id, summary)
            if hist_result:
                account_code = hist_result["account_code"]
                account_name = hist_result["account_name"]
                category = "历史匹配"
                confidence = 0.85
            else:
                if direction == "debit":
                    account_code = "6602"
                    account_name = "管理费用-其他"
                else:
                    account_code = "6001"
                    account_name = "主营业务收入"
                category = "默认"
                confidence = 0.30

        is_anomaly, anomaly_reason = await self._detect_anomaly(ledger_id, amount)

        return {
            "account_code": account_code, "account_name": account_name,
            "confidence": confidence, "category": category,
            "is_anomaly": is_anomaly, "anomaly_reason": anomaly_reason,
        }

    async def _match_history(self, ledger_id: int, summary: str) -> dict:
        """Match transaction to historical account by summary keyword."""
        keywords = summary[:10] if len(summary) >= 3 else summary
        async with get_db() as session:
            result = await session.execute(
                text("""
                    SELECT je.account_code, je.account_name, COUNT(*) as freq
                    FROM journal_entries je
                    JOIN vouchers v ON je.voucher_id = v.id
                    WHERE je.ledger_id = :lid AND v.status = 'posted'
                      AND je.summary LIKE :pattern
                    GROUP BY je.account_code
                    ORDER BY freq DESC LIMIT 1
                """),
                {"lid": ledger_id, "pattern": f"%{keywords}%"},
            )
            row = result.fetchone()
            if row:
                r = dict(row._mapping)
                return {"account_code": r["account_code"], "account_name": r["account_name"]}
            return None

    async def _detect_anomaly(self, ledger_id: int, amount: float):
        """Detect anomalous transactions (amount > 3x average)."""
        async with get_db() as session:
            result = await session.execute(
                text("""
                    SELECT COALESCE(AVG(ABS(debit) + ABS(credit)), 0) as avg_amt,
                           COUNT(*) as cnt
                    FROM journal_entries je
                    JOIN vouchers v ON je.voucher_id = v.id
                    WHERE je.ledger_id = :lid AND v.status = 'posted'
                """),
                {"lid": ledger_id},
            )
            row = result.fetchone()
            avg = row[0] if row else 0
            cnt = row[1] if row else 0
            if cnt >= 10 and abs(amount) > avg * 3 and avg > 0:
                return True, f"金额 {abs(amount):,.2f} 超过平均值 {avg:,.2f} 的3倍"
            return False, ""

    async def batch_classify(self, ledger_id: int, transactions: list) -> list:
        """Classify a batch of transactions. Each txn needs summary, amount, direction."""
        results = []
        for txn in transactions:
            classification = await self.classify_transaction(
                ledger_id,
                txn.get("summary", ""),
                txn.get("amount", 0),
                txn.get("direction", "debit"),
                txn.get("counterparty", ""),
            )
            results.append({**txn, **classification})
        return results

    async def get_classification_rules(self, ledger_id: int) -> list:
        """Get user's historical classification rules (frequent account+summary patterns)."""
        async with get_db() as session:
            result = await session.execute(
                text("""
                    SELECT je.account_code, je.account_name, je.summary, COUNT(*) as freq
                    FROM journal_entries je
                    JOIN vouchers v ON je.voucher_id = v.id
                    WHERE je.ledger_id = :lid AND v.status = 'posted'
                    GROUP BY je.account_code, je.summary
                    HAVING freq >= 2
                    ORDER BY freq DESC LIMIT 50
                """),
                {"lid": ledger_id},
            )
            return [dict(r._mapping) for r in result]

    async def save_classified_transactions(self, ledger_id: int, transactions: list) -> list:
        """Save classified transactions as draft vouchers. Returns list of voucher_nos."""
        from datetime import date
        voucher_nos = []
        async with get_db() as session:
            for txn in transactions:
                date_str = txn.get("date", date.today().isoformat())
                summary = txn.get("summary", "")
                amount = txn.get("amount", 0)
                account_code = txn.get("account_code", "6602")
                account_name = txn.get("account_name", "管理费用-其他")
                if txn.get("direction") == "credit":
                    entries = [
                        {"account_code": "1002", "account_name": "银行存款", "debit": amount, "credit": 0, "summary": summary},
                        {"account_code": account_code, "account_name": account_name, "debit": 0, "credit": amount, "summary": summary},
                    ]
                else:
                    entries = [
                        {"account_code": account_code, "account_name": account_name, "debit": amount, "credit": 0, "summary": summary},
                        {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": amount, "summary": summary},
                    ]
                try:
                    total = amount
                    v_result = await session.execute(
                        text(
                            "INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status) "
                            "VALUES (:lid, :vno, :date, :desc, :td, :tc, 'draft')"
                        ),
                        {
                            "lid": ledger_id,
                            "vno": f"YH{date_str.replace('-', '')}{len(voucher_nos) + 1:04d}",
                            "date": date_str,
                            "desc": f"银行流水导入-{summary}",
                            "td": total, "tc": total,
                        },
                    )
                    v_id_result = await session.execute(
                        text("SELECT id FROM vouchers WHERE voucher_no = :vno AND ledger_id = :lid"),
                        {"vno": f"YH{date_str.replace('-', '')}{len(voucher_nos) + 1:04d}", "lid": ledger_id},
                    )
                    voucher_nos.append(f"YH{date_str.replace('-', '')}{len(voucher_nos) + 1:04d}")
                except Exception:
                    pass
        return voucher_nos
