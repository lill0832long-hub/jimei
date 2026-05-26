"""AI repository — AI business rules (complex rules) and raw query support."""
import json
import os
import sqlite3
from sqlalchemy import select, text
from app.models.ai_rule import AiRuleComplex
from app.models.base import get_db
from .base import BaseRepository

_DB_PATH = None


def _get_db_path():
    """Resolve the SQLite database file path."""
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "finance_v2.db",
        )
    return _DB_PATH


class AiRepository(BaseRepository):
    """AI business rules management."""

    model = AiRuleComplex

    async def get_rules(self, active_only: bool = True) -> list:
        """Get all complex business rules."""
        async with get_db() as session:
            stmt = select(AiRuleComplex).order_by(AiRuleComplex.priority.desc(), AiRuleComplex.id)
            if active_only:
                stmt = stmt.where(AiRuleComplex.is_active == 1)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id, "name": r.name, "pattern": r.pattern,
                    "description": r.description, "entries_json": r.entries_json,
                    "priority": r.priority, "usage_count": r.usage_count,
                    "is_active": r.is_active,
                }
                for r in rows
            ]

    async def add_rule(self, name: str, pattern: str, description: str,
                       entries_json: list, priority: int = 50) -> dict:
        """Add a complex business rule."""
        async with get_db() as session:
            rule = AiRuleComplex(
                name=name, pattern=pattern, description=description,
                entries_json=json.dumps(entries_json, ensure_ascii=False),
                priority=priority,
            )
            session.add(rule)
            await session.flush()
            await session.refresh(rule)
            return {
                "id": rule.id, "name": rule.name, "pattern": rule.pattern,
                "description": rule.description, "entries_json": rule.entries_json,
                "priority": rule.priority, "is_active": rule.is_active,
            }

    async def delete_rule(self, rule_id: int) -> bool:
        """Delete a complex business rule."""
        async with get_db() as session:
            rule = await session.get(AiRuleComplex, rule_id)
            if rule:
                await session.delete(rule)
                return True
            return False

    async def toggle_rule(self, rule_id: int) -> dict:
        """Toggle a rule's active status. Returns dict with new is_active state."""
        async with get_db() as session:
            rule = await session.get(AiRuleComplex, rule_id)
            if rule:
                rule.is_active = 0 if rule.is_active else 1
                return {"id": rule.id, "is_active": rule.is_active}
            return None

    @staticmethod
    def query_db(sql: str, params: tuple = ()) -> list:
        """Execute a raw SQL query and return list of dicts.

        This is a synchronous convenience method for complex ad-hoc queries
        that don't fit the ORM pattern. Use sparingly.
        """
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    async def init_builtin_rules(self):
        """Initialize built-in complex business rules if table is empty."""
        async with get_db() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM ai_rules_complex"))
            if result.fetchone()[0] > 0:
                return

            builtin_rules = [
                {
                    "name": "采购含运费",
                    "pattern": "采购.*运费",
                    "description": "采购材料并支付运费",
                    "priority": 90,
                    "entries": [
                        {"account_code": "1403", "account_name": "原材料", "debit_key": "material", "credit": 0},
                        {"account_code": "6601", "account_name": "销售费用-运费", "debit_key": "freight", "credit": 0},
                        {"account_code": "222101", "account_name": "应交增值税(进项)", "debit_key": "vat", "credit": 0},
                        {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit_key": "total"},
                    ],
                },
                {
                    "name": "销售含折扣",
                    "pattern": "销售.*折扣",
                    "description": "销售商品并给予折扣",
                    "priority": 90,
                    "entries": [
                        {"account_code": "1002", "account_name": "银行存款", "debit_key": "cash", "credit": 0},
                        {"account_code": "6601", "account_name": "销售费用-折扣", "debit_key": "discount", "credit": 0},
                        {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit_key": "total"},
                    ],
                },
                {
                    "name": "工资发放代扣个税",
                    "pattern": "发放工资.*个税",
                    "description": "发放工资并代扣个人所得税",
                    "priority": 85,
                    "entries": [
                        {"account_code": "2211", "account_name": "应付职工薪酬", "debit_key": "gross", "credit": 0},
                        {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit_key": "net"},
                        {"account_code": "222102", "account_name": "应交税费-个税", "debit": 0, "credit_key": "tax"},
                    ],
                },
                {
                    "name": "固定资产处置",
                    "pattern": "处置.*固定资产",
                    "description": "处置固定资产（报废/出售）",
                    "priority": 80,
                    "entries": [
                        {"account_code": "1602", "account_name": "累计折旧", "debit_key": "accumulated", "credit": 0},
                        {"account_code": "1601", "account_name": "固定资产清理", "debit_key": "net", "credit": 0},
                        {"account_code": "1601", "account_name": "固定资产", "debit": 0, "credit_key": "original"},
                        {"account_code": "1002", "account_name": "银行存款", "debit_key": "proceeds", "credit": 0},
                    ],
                },
                {
                    "name": "在建工程转固",
                    "pattern": "在建工程.*完工",
                    "description": "在建工程完工结转固定资产",
                    "priority": 85,
                    "entries": [
                        {"account_code": "1601", "account_name": "固定资产", "debit_key": "amount", "credit": 0},
                        {"account_code": "1604", "account_name": "在建工程", "debit": 0, "credit_key": "amount"},
                    ],
                },
            ]

            for rule in builtin_rules:
                entries = rule.pop("entries")
                r = AiRuleComplex(
                    name=rule["name"], pattern=rule["pattern"],
                    description=rule["description"],
                    entries_json=json.dumps(entries, ensure_ascii=False),
                    priority=rule["priority"],
                )
                session.add(r)
            await session.flush()
