"""
AI 财务系统 - 数据库模块 v2
升级：多账套 / 期初余额 / 凭证状态管理 / 审计日志
"""

import sqlite3
import os
import functools
from contextlib import contextmanager
from datetime import datetime, date
from enum import Enum

DB_PATH = os.path.join(os.path.dirname(__file__), "finance_v2.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


@contextmanager
def transaction(conn):
    """事务管理上下文管理器 — 自动 commit/rollback"""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── 账套管理 ──

def create_ledger(name, company="默认公司", currency="CNY", fiscal_start=None, fiscal_end=None, settings=None):
    """创建新账套"""
    import json
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO ledgers (name, company, currency, fiscal_year_start, fiscal_year_end, settings) VALUES (?,?,?,?,?,?)",
        (name, company, currency,
         fiscal_start or f"{datetime.now().year}-01-01",
         fiscal_end or f"{datetime.now().year}-12-31",
         json.dumps(settings) if settings else None)
    )
    ledger_id = cur.lastrowid
    conn.commit()
    conn.close()
    clear_query_cache()
    return ledger_id


@functools.lru_cache(maxsize=8)
def get_ledgers():
    """获取所有账套"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ledgers ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ledger(ledger_id):
    """获取单个账套"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM ledgers WHERE id = ?", (ledger_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_ledger(ledger_id, **kwargs):
    """更新账套信息"""
    import json
    allowed = {"name", "company", "currency", "fiscal_year_start", "fiscal_year_end", "status", "settings"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if "settings" in updates and isinstance(updates["settings"], dict):
        updates["settings"] = json.dumps(updates["settings"])
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn = get_conn()
    conn.execute(f"UPDATE ledgers SET {set_clause}, updated_at = datetime('now','localtime') WHERE id = ?",
                 list(updates.values()) + [ledger_id])
    conn.commit()
    conn.close()
    clear_query_cache()


def delete_ledger(ledger_id):
    """删除账套（级联删除所有相关数据）"""
    conn = get_conn()
    conn.execute("DELETE FROM audit_logs WHERE ledger_id = ?", (ledger_id,))
    conn.execute("DELETE FROM journal_entries WHERE ledger_id = ?", (ledger_id,))
    conn.execute("DELETE FROM vouchers WHERE ledger_id = ?", (ledger_id,))
    conn.execute("DELETE FROM opening_balances WHERE ledger_id = ?", (ledger_id,))
    conn.execute("DELETE FROM documents WHERE ledger_id = ?", (ledger_id,))
    conn.execute("DELETE FROM ledgers WHERE id = ?", (ledger_id,))
    conn.commit()
    conn.close()
    clear_query_cache()


# ── 期初余额 ──

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


# ── 凭证操作（升级） ──

def create_voucher(ledger_id, date_str, description, entries, status="posted", voucher_no=None, user_id=None, operator_name=None):
    """
    创建记账凭证（支持多状态）
    entries: [{"account_code": "1002", "debit": 10000, "credit": 0, "summary": ""}, ...]
    account_name 会自动从 accounts 表查找填充
    voucher_no: 自定义凭证编号，为 None 时自动生成
    """
    conn = get_conn()
    try:
        with transaction(conn):
            if not voucher_no:
                prefix = f"PZ{date_str.replace('-', '')}"
                count = conn.execute("SELECT COUNT(*) FROM vouchers WHERE voucher_no LIKE ? AND ledger_id = ?",
                                     (prefix + "%", ledger_id)).fetchone()[0]
                voucher_no = f"{prefix}{count+1:04d}"

            total_debit = sum(e.get("debit", 0) for e in entries)
            total_credit = sum(e.get("credit", 0) for e in entries)

            if abs(total_debit - total_credit) > 0.01:
                raise ValueError(f"借贷不平衡：借方 {total_debit} ≠ 贷方 {total_credit}")

            cur = conn.execute(
                "INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status, currency) VALUES (?,?,?,?,?,?,?,?)",
                (ledger_id, voucher_no, date_str, description, total_debit, total_credit, status, "CNY")
            )
            voucher_id = cur.lastrowid

            for e in entries:
                account_code = e.get("account_code", "")
                account_name = e.get("account_name")
                if not account_name:
                    row = conn.execute("SELECT name FROM accounts WHERE code = ?", (account_code,)).fetchone()
                    account_name = row["name"] if row else account_code
                conn.execute(
                    "INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary, foreign_currency, foreign_amount, exchange_rate) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (ledger_id, voucher_id, account_code, account_name, e.get("debit", 0), e.get("credit", 0), e.get("summary", ""),
                     e.get("foreign_currency", ""), e.get("foreign_amount", 0), e.get("exchange_rate", 1))
                )

            # 审计日志（在事务内，保证原子性）
            add_audit_log(
                ledger_id=ledger_id,
                action="create_voucher",
                detail=f"创建凭证 {voucher_no}",
                voucher_id=voucher_id,
                module="voucher",
                target_table="vouchers",
                target_id=voucher_id,
                user_id=user_id,
                operator_name=operator_name,
                remark=f"凭证号:{voucher_no}",
            )
        return voucher_no
    finally:
        conn.close()


def update_voucher(voucher_no, date_str=None, description=None, entries=None, user_id=None, operator_name=None):
    """更新凭证（仅限 draft 状态）"""
    conn = get_conn()
    try:
        with transaction(conn):
            v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
            if not v:
                raise ValueError("凭证不存在")
            if v["status"] != "draft":
                raise ValueError(f"只能编辑草稿状态的凭证（当前状态：{v['status']}）")

            if date_str:
                conn.execute("UPDATE vouchers SET date = ? WHERE id = ?", (date_str, v["id"]))
            if description:
                conn.execute("UPDATE vouchers SET description = ? WHERE id = ?", (description, v["id"]))
            if entries:
                conn.execute("DELETE FROM journal_entries WHERE voucher_id = ?", (v["id"],))
                total_debit = sum(e.get("debit", 0) for e in entries)
                total_credit = sum(e.get("credit", 0) for e in entries)
                if abs(total_debit - total_credit) > 0.01:
                    raise ValueError("借贷不平衡")
                for e in entries:
                    account_code = e.get("account_code", "")
                    account_name = e.get("account_name")
                    if not account_name:
                        row = conn.execute("SELECT name FROM accounts WHERE code = ?", (account_code,)).fetchone()
                        account_name = row["name"] if row else account_code
                    conn.execute(
                        "INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary, foreign_currency, foreign_amount, exchange_rate) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (v["ledger_id"], v["id"], account_code, account_name, e.get("debit", 0), e.get("credit", 0), e.get("summary", ""),
                         e.get("foreign_currency", ""), e.get("foreign_amount", 0), e.get("exchange_rate", 1))
                    )
                conn.execute("UPDATE vouchers SET total_debit = ?, total_credit = ? WHERE id = ?", (total_debit, total_credit, v["id"]))

            conn.execute("UPDATE vouchers SET updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
            add_audit_log(
                ledger_id=v["ledger_id"],
                action="update_voucher",
                detail=f"更新凭证 {voucher_no}",
                voucher_id=v["id"],
                module="voucher",
                target_table="vouchers",
                target_id=v["id"],
                user_id=user_id,
                operator_name=operator_name,
                remark=f"凭证号:{voucher_no}",
            )
    finally:
        conn.close()


def post_voucher(ledger_id, voucher_no=None, user_id=None, operator_name=None):
    """审核并过账（验证凭证属于指定账套）
    兼容两种调用方式：
    - post_voucher(ledger_id, voucher_no)  # 显式指定账套
    - post_voucher(voucher_no)             # 仅凭证号（从凭证中推断账套）
    """
    # 处理向后兼容：如果只传一个参数，则视为 voucher_no
    if voucher_no is None:
        voucher_no = ledger_id
        ledger_id = None

    conn = get_conn()
    if ledger_id is not None:
        v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    else:
        v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
    if not v:
        conn.close()
        raise ValueError("凭证不存在或不属于该账套")
    if v["status"] == "posted":
        conn.close()
        return  # 已过账
    conn.execute("UPDATE vouchers SET status = 'posted', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=v["ledger_id"],
        action="post_voucher",
        detail=f"过账凭证 {voucher_no}",
        voucher_id=v["id"],
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        remark=f"凭证号:{voucher_no}",
    )
    conn.commit()
    conn.close()
    clear_query_cache()


def submit_for_review(ledger_id, voucher_no, user_id=None):
    """submit_for_review: draft/reversed -> pending_review"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    if not v:
        conn.close()
        raise ValueError("voucher not found")
    if v["status"] not in ("draft", "reversed"):
        conn.close()
        raise ValueError("only draft/reversed can submit for review")
    conn.execute("UPDATE vouchers SET status = 'pending_review', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=ledger_id,
        action="submit_review",
        detail="提交审核 " + voucher_no,
        voucher_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        remark=f"凭证号:{voucher_no}",
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    add_workflow_log(ledger_id, v["id"], "submit", v["status"], "pending_review", user_id)


def approve_voucher(ledger_id, voucher_no, user_id=None):
    """approve_voucher: pending_review -> posted"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    if not v:
        conn.close()
        raise ValueError("voucher not found")
    if v["status"] != "pending_review":
        conn.close()
        raise ValueError("only pending_review can approve")
    conn.execute("UPDATE vouchers SET status = 'posted', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=ledger_id,
        action="approve_voucher",
        detail="审核通过 " + voucher_no,
        voucher_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        remark=f"凭证号:{voucher_no}",
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    add_workflow_log(ledger_id, v["id"], "approve", "pending_review", "posted", user_id)


def reject_voucher(ledger_id, voucher_no, reason="", user_id=None):
    """reject_voucher: pending_review -> draft"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    if not v:
        conn.close()
        raise ValueError("voucher not found")
    if v["status"] != "pending_review":
        conn.close()
        raise ValueError("only pending_review can reject")
    conn.execute("UPDATE vouchers SET status = 'draft', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=ledger_id,
        action="reject_voucher",
        detail="驳回 " + voucher_no + " 原因:" + reason,
        voucher_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        remark=reason,
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    add_workflow_log(ledger_id, v["id"], "reject", "pending_review", "draft", user_id, reason)


def reverse_voucher(voucher_no, reason="", user_id=None, operator_name=None):
    """reverse_voucher"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
    if not v:
        raise ValueError("凭证不存在")
    if v["status"] != "posted":
        raise ValueError("只能冲销已过账的凭证")

    # 创建冲销凭证号
    prefix = f"CH{v['date'].replace('-', '')}"
    count = conn.execute("SELECT COUNT(*) FROM vouchers WHERE voucher_no LIKE ? AND ledger_id = ?",
                         (prefix + "%", v["ledger_id"])).fetchone()[0]
    reverse_no = f"{prefix}{count+1:04d}"

    entries = conn.execute("SELECT * FROM journal_entries WHERE voucher_id = ?", (v["id"],)).fetchall()

    # 红字冲销：保持原借贷方向，金额为负数（用正数存储但在凭证摘要中标注红字）
    # 冲销凭证的借贷总额与原凭证相同（用于冲销）
    reverse_entries = [{
        "account_code": e["account_code"],
        "account_name": e["account_name"],
        "debit": round(-e["debit"], 2),   # 红字：原借方变负数
        "credit": round(-e["credit"], 2),  # 红字：原贷方变负数
        "summary": f"红字冲销{voucher_no}: {e['summary']}",
    } for e in entries]

    total_dr = sum(e["debit"] for e in reverse_entries)
    total_cr = sum(e["credit"] for e in reverse_entries)

    cur = conn.execute(
        "INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status, currency) VALUES (?,?,?,?,?,?,?,?)",
        (v["ledger_id"], reverse_no, date.today().isoformat(),
         f"红字冲销 {voucher_no}" + (f" - {reason}" if reason else ""),
         total_dr, total_cr, "posted", v.get("currency", "CNY"))
    )
    reverse_id = cur.lastrowid

    for e in reverse_entries:
        conn.execute(
            "INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary, foreign_currency, foreign_amount, exchange_rate) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (v["ledger_id"], reverse_id, e["account_code"], e["account_name"], e["debit"], e["credit"], e["summary"],
             e.get("foreign_currency", ""), e.get("foreign_amount", 0), e.get("exchange_rate", 1))
        )

    conn.execute("UPDATE vouchers SET status = 'reversed', updated_at = datetime('now','localtime') WHERE id = ?", (v["id"],))
    add_audit_log(
        ledger_id=v["ledger_id"],
        action="reverse_voucher",
        detail=f"冲销凭证 {voucher_no} -> {reverse_no}: {reason}",
        voucher_id=v["id"],
        module="voucher",
        target_table="vouchers",
        target_id=v["id"],
        user_id=user_id,
        operator_name=operator_name,
        remark=f"原凭证:{voucher_no} 冲销:{reverse_no}",
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    return reverse_no


def delete_voucher(voucher_no, ledger_id=None, user_id=None, operator_name=None):
    """删除凭证（仅限 draft 状态）
    ledger_id 为可选参数，用于验证凭证归属（推荐传入以提升安全性）
    """
    conn = get_conn()
    try:
        with transaction(conn):
            if ledger_id is not None:
                v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
            else:
                v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
            if not v:
                raise ValueError("凭证不存在或不属于该账套")
            if v["status"] != "draft":
                raise ValueError("只能删除草稿状态的凭证，已过账请使用冲销")
            conn.execute("DELETE FROM journal_entries WHERE voucher_id = ?", (v["id"],))
            conn.execute("DELETE FROM vouchers WHERE id = ?", (v["id"],))
            add_audit_log(
                ledger_id=v["ledger_id"],
                action="delete_voucher",
                detail=f"删除凭证 {voucher_no}",
                voucher_id=None,
                module="voucher",
                target_table="vouchers",
                target_id=v["id"],
                user_id=user_id,
                operator_name=operator_name,
                remark=f"凭证号:{voucher_no}",
            )
    finally:
        conn.close()


@functools.lru_cache(maxsize=64)
def get_vouchers(ledger_id, year=None, month=None, status=None, limit=100):
    """查询凭证列表"""
    conn = get_conn()
    sql = "SELECT * FROM vouchers WHERE ledger_id = ?"
    params = [ledger_id]
    if year:
        sql += " AND strftime('%Y', date) = ?"
        params.append(str(year))
    if month:
        sql += " AND strftime('%m', date) = ?"
        params.append(f"{month:02d}")
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY date DESC, voucher_no DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


def get_voucher_detail(ledger_id, voucher_no):
    """获取凭证详情（验证凭证属于指定账套）"""
    conn = get_conn()
    v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ? AND ledger_id = ?", (voucher_no, ledger_id)).fetchone()
    if not v:
        conn.close()
        return None
    entries = conn.execute("SELECT * FROM journal_entries WHERE voucher_id = ?", (v["id"],)).fetchall()
    result = dict(v)
    result["entries"] = [dict(e) for e in entries]
    conn.close()
    return result


# ── 科目余额（升级：支持账套和期初余额） ──

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

# ── 资产负债表（支持账套） ──

@functools.lru_cache(maxsize=32)
def get_balance_sheet(ledger_id, year, month) -> dict:
    """资产负债表 — 中国会计准则格式，支持年初数"""
    conn = get_conn()

    def _opening_bal(code):
        row = conn.execute(
            "SELECT balance FROM opening_balances WHERE ledger_id=? AND account_code=? AND year=? AND month=1",
            (ledger_id, code, year)
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

    # ── 资产 ──
    assets = []
    ca_end, ca_open = 0.0, 0.0
    for code, name in [("1001","库存现金"),("1002","银行存款"),("1121","收票据"),
                        ("1122","应收账款"),("1123","预付账款"),("1221","其他应收款")]:
        cat = _get_cat(code)
        ev, ov = _end_bal(code, cat), _open_bal_signed(code, cat)
        if ev or ov:
            _add(assets, code, name, 1, ev, ov, "流动资产")
            ca_end += ev; ca_open += ov
    # 存货
    inv_codes = [("1403","原材料"),("1405","库存商品"),("1406","周转材料")]
    inv_end = sum(_end_bal(c, "资产") for c, _ in inv_codes)
    inv_open = sum(_open_bal_signed(c, "资产") for c, _ in inv_codes)
    if inv_end or inv_open:
        _add(assets, "1400", "存货", 1, inv_end, inv_open, "流动资产", is_parent=True)
        for c, n in inv_codes:
            ev, ov = _end_bal(c, "资产"), _open_bal_signed(c, "资产")
            if ev or ov:
                _add(assets, c, n, 2, ev, ov, "流动资产")
        ca_end += inv_end; ca_open += inv_open
    _add(assets, "", "流动资产合计", 0, ca_end, ca_open, "流动资产_total")

    # 非流动资产
    nca_end, nca_open = 0.0, 0.0
    # 固定资产
    fv_g, fv_g_open = _end_bal("1601","资产"), _open_bal_signed("1601","资产")
    fv_d, fv_d_open = _end_bal("1602","资产"), _open_bal_signed("1602","资产")
    fv_net, fv_net_open = fv_g + fv_d, fv_g_open + fv_d_open
    if fv_g or fv_g_open or fv_d or fv_d_open:
        _add(assets, "1601", "固定资产原价", 1, fv_g, fv_g_open, "非流动资产", is_parent=True)
        _add(assets, "1602", "减：累计折旧", 2, -fv_d, -fv_d_open, "非流动资产")
        _add(assets, "1601N", "固定资产账面价值", 2, fv_net, fv_net_open, "非流动资产")
        nca_end += fv_net; nca_open += fv_net_open
    for code, name in [("1501","长期债券投资"),("1511","长期股权投资"),("1604","在建工程"),
                        ("1701","无形资产"),("1801","长期待摊费用"),("1901","待处理财产损溢")]:
        cat = _get_cat(code)
        ev, ov = _end_bal(code, cat), _open_bal_signed(code, cat)
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
    for code, name in [("2001","短期借款"),("2201","应付票据"),("2202","应付账款"),
                        ("2203","预收账款"),("2211","应付职工薪酬"),("2221","应交税费"),
                        ("2231","应付利息"),("2232","应付股利"),("2241","其他应付款")]:
        cat = _get_cat(code)
        ev, ov = _end_bal(code, cat), _open_bal_signed(code, cat)
        if ev or ov:
            _add(liabilities, code, name, 1, ev, ov, "流动负债")
            cl_end += ev; cl_open += ov
    _add(liabilities, "", "流动负债合计", 0, cl_end, cl_open, "流动负债_total")
    ncl_end, ncl_open = 0.0, 0.0
    for code, name in [("2501","长期借款"),("2701","长期应付款"),("2801","递延收益")]:
        cat = _get_cat(code)
        ev, ov = _end_bal(code, cat), _open_bal_signed(code, cat)
        if ev or ov:
            _add(liabilities, code, name, 1, ev, ov, "非流动负债")
            ncl_end += ev; ncl_open += ov
    _add(liabilities, "", "非流动负债合计", 0, ncl_end, ncl_open, "非流动负债_total")
    total_liab, total_liab_open = cl_end + ncl_end, cl_open + ncl_open
    _add(liabilities, "", "负债合计", 0, total_liab, total_liab_open, "liab_total")

    # ── 所有者权益 ──
    equity = []
    eq_end, eq_open = 0.0, 0.0
    for code, name in [("4001","实收资本"),("4002","资本公积"),("4101","盈余公积"),("4104","利润分配")]:
        cat = _get_cat(code)
        ev, ov = _end_bal(code, cat), _open_bal_signed(code, cat)
        if ev or ov:
            _add(equity, code, name, 1, ev, ov, "权益")
            eq_end += ev; eq_open += ov
    # 本年利润 = 期初 + 本期净利润
    np_open = _open_bal_signed("4103", "权益")
    rev_ytd = conn.execute(
        "SELECT COALESCE(SUM(je.credit)-SUM(je.debit),0) FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id=v.id AND v.status='posted' "
        "JOIN accounts a ON je.account_code=a.code "
        "WHERE je.ledger_id=? AND a.category='收入' AND strftime('%Y',v.date)=? AND CAST(strftime('%m',v.date) AS INTEGER)<=? "
        "AND (v.description IS NULL OR v.description NOT LIKE '%结转%')",
        (ledger_id, str(year), month)
    ).fetchone()[0] or 0
    exp_ytd = conn.execute(
        "SELECT COALESCE(SUM(je.debit)-SUM(je.credit),0) FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id=v.id AND v.status='posted' "
        "JOIN accounts a ON je.account_code=a.code "
        "WHERE je.ledger_id=? AND a.category='费用' AND strftime('%Y',v.date)=? AND CAST(strftime('%m',v.date) AS INTEGER)<=? "
        "AND (v.description IS NULL OR v.description NOT LIKE '%结转%')",
        (ledger_id, str(year), month)
    ).fetchone()[0] or 0
    net_profit = round(rev_ytd - exp_ytd, 2)
    _add(equity, "4103", "本年利润", 1, np_open + net_profit, np_open, "权益")
    eq_end += np_open + net_profit
    total_equity, total_equity_open = eq_end, eq_open
    _add(equity, "", "所有者权益合计", 0, total_equity, total_equity_open, "eq_total")
    _add(equity, "", "负债和所有者权益总计", 0, total_liab + total_equity, total_liab_open + total_equity_open, "grand_total")

    conn.close()
    return {
        "date": f"{year}-{month:02d}",
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "total_assets": round(total_assets, 2),
        "total_liab": round(total_liab, 2),
        "total_equity": round(total_equity, 2),
    }

@functools.lru_cache(maxsize=32)
def get_income_statement(ledger_id, year, month) -> dict:
    """利润表 — 支持子项明细 + 本年累计/本月金额
    列：项目 | 行次 | 本年累计金额 | 本月金额
    """
    conn = get_conn()

    def _period_clause(table="v"):
        return f"strftime('%Y', {table}.date) = ? AND CAST(strftime('%m', {table}.date) AS INTEGER) = ? AND ({table}.description IS NULL OR {table}.description NOT LIKE '%年%月%')"

    def _ytd_clause(table="v"):
        return f"strftime('%Y', {table}.date) = ? AND CAST(strftime('%m', {table}.date) AS INTEGER) <= ? AND ({table}.description IS NULL OR {table}.description NOT LIKE '%年%月%')"

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
        if children:
            for ch in children:
                m = _revenue_month(code=ch["code"])
                y = _revenue_ytd(code=ch["code"])
                if m or y:
                    rows.append({"name": ch["name"], "code": ch["code"], "level": 2, "month": m, "ytd": y, "type": "revenue_item"})
                    total_rev_month += m
                    total_rev_ytd += y
        else:
            m = _revenue_month(code=r["code"])
            y = _revenue_ytd(code=r["code"])
            if m or y:
                rows.append({"name": r["name"], "code": r["code"], "level": 1, "month": m, "ytd": y, "type": "revenue_item"})
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

    # 二、营业利润
    total_expense_month = cogs_month + tax_month + sfa_month + ma_month + fa_month
    total_expense_ytd = cogs_ytd + tax_ytd + sfa_ytd + ma_ytd + fa_ytd
    op_month = total_rev_month - total_expense_month + inv_month
    op_ytd = total_rev_ytd - total_expense_ytd + inv_ytd
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


# ── AI 智能凭证 ──

def generate_voucher_from_text(ledger_id: int, text: str) -> dict:
    """
    从自然语言描述生成分录建议
    返回 {"description": str, "entries": [...], "confidence": float, "composite": bool, "currency": str, "exchange_rate": float}
    规则引擎实现（基于关键词匹配 + 金额提取）
    支持：简单一借一贷 / 复合多借多贷 / 外币金额
    """
    import re
    text = str(text).strip()
    entries = []
    description = text
    confidence = 0.5
    currency = "CNY"
    exchange_rate = 1.0
    is_composite = False

    def _extract_amount(t):
        """提取金额，支持'万'单位和逗号"""
        m = re.search(r'(\d[\d,]*\.?\d*)\s*[万wW]', t)
        if m:
            return float(m.group(1).replace(',', '')) * 10000
        m = re.search(r'(\d[\d,]*\.?\d*)', t.replace(',', ''))
        if m:
            return float(m.group(1))
        return None

    def _extract_currency(t):
        """提取外币币种"""
        currency_map = {
            'USD': ['USD', '美元', '\\$'], 'EUR': ['EUR', '欧元'],
            'JPY': ['JPY', '日元'], 'HKD': ['HKD', '港币', '港元'],
            'GBP': ['GBP', '英镑'],
        }
        for code, keywords in currency_map.items():
            for kw in keywords:
                if kw in t:
                    return code
        return 'CNY'

    def _extract_all_amounts(t):
        """提取文本中所有金额，支持万/w/元"""
        amounts = []
        # 先匹配 数字+万/w
        for m in re.finditer(r'(\d[\d,]*\.?\d*)\s*[万wW]', t):
            amounts.append(float(m.group(1).replace(',', '')) * 10000)
        # 再匹配 数字+元（排除已匹配的万/w数字）
        if not amounts:
            for m in re.finditer(r'(\d[\d,]*\.?\d*)\s*元', t):
                amounts.append(float(m.group(1).replace(',', '')))
        # 最后匹配纯数字（排除已匹配的）
        if not amounts:
            for m in re.finditer(r'(\d[\d,]*\.?\d*)', t.replace(',', '')):
                amounts.append(float(m.group(1)))
        return amounts

    # 复合业务解析器
    def _parse_partial_cash_credit(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 3:
            total, cash, credit = amounts[0], amounts[1], amounts[2]
        elif len(amounts) == 2:
            total, cash = amounts[0], amounts[1]
            credit = total - cash
        else:
            total = amounts[0] if amounts else 0
            cash = total * 0.6
            credit = total - cash
        is_fixed = any(kw in t for kw in ['设备', '机器', '固定资产'])
        debit_code = '1601' if is_fixed else '1403'
        debit_name = '固定资产' if is_fixed else '原材料'
        return [
            {"account_code": debit_code, "account_name": debit_name, "debit": round(total, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(cash, 2)},
            {"account_code": "2202", "account_name": "应付账款", "debit": 0, "credit": round(credit, 2)},
        ]

    def _parse_partial_cash_ar(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 3:
            total, cash, ar = amounts[0], amounts[1], amounts[2]
        elif len(amounts) == 2:
            total, cash = amounts[0], amounts[1]
            ar = total - cash
        else:
            total = amounts[0] if amounts else 0
            cash = total * 0.6
            ar = total - cash
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(cash, 2), "credit": 0},
            {"account_code": "1122", "account_name": "应收账款", "debit": round(ar, 2), "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_expense_reimbursement(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 3:
            total, cash, loan = amounts[0], amounts[1], amounts[2]
        elif len(amounts) == 2:
            total, cash = amounts[0], amounts[1]
            loan = total - cash
        else:
            total = amounts[0] if amounts else 0
            cash = total * 0.6
            loan = total - cash
        return [
            {"account_code": "6602", "account_name": "管理费用", "debit": round(total, 2), "credit": 0},
            {"account_code": "1001", "account_name": "库存现金", "debit": 0, "credit": round(cash, 2)},
            {"account_code": "1221", "account_name": "其他应收款", "debit": 0, "credit": round(loan, 2)},
        ]

    def _parse_purchase_with_vat(t):
        amounts = _extract_all_amounts(t)
        rate_match = re.search(r'税率[：:\s]*(\d+\.?\d*)%', t)
        rate = float(rate_match.group(1)) / 100 if rate_match else 0.13
        if len(amounts) >= 2:
            if '不含税' in t:
                ex_tax = amounts[0]
                vat = round(ex_tax * rate, 2)
                total = ex_tax + vat
            elif len(amounts) >= 3:
                ex_tax, vat = amounts[0], amounts[1]
                total = ex_tax + vat
            else:
                total_or_ex = amounts[0]
                if '价税合计' in t or '总价' in t:
                    ex_tax = round(total_or_ex / (1 + rate), 2)
                    vat = total_or_ex - ex_tax
                    total = total_or_ex
                else:
                    ex_tax = total_or_ex
                    vat = round(ex_tax * rate, 2)
                    total = ex_tax + vat
        else:
            ex_tax = amounts[0] if amounts else 0
            vat = round(ex_tax * rate, 2)
            total = ex_tax + vat
        is_fixed = any(kw in t for kw in ['设备', '机器', '固定资产'])
        debit_code = '1601' if is_fixed else '1403'
        debit_name = '固定资产' if is_fixed else '原材料'
        return [
            {"account_code": debit_code, "account_name": debit_name, "debit": round(ex_tax, 2), "credit": 0},
            {"account_code": "222101", "account_name": "应交增值税(进项税额)", "debit": round(vat, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_salary_allocation(t):
        amounts = _extract_all_amounts(t)
        if not amounts:
            return None
        dept_keywords = [
            ('生产成本', ['生产', '车间', '制造'], '5001'),
            ('管理费用', ['管理', '行政', '财务', '人事'], '6602'),
            ('销售费用', ['销售', '营销', '市场'], '6601'),
            ('研发支出', ['研发', '开发', '技术'], '5301'),
        ]
        matched_depts = []
        for dept_name, keywords, acct_code in dept_keywords:
            if any(kw in t for kw in keywords):
                matched_depts.append((dept_name, acct_code))
        if not matched_depts:
            matched_depts = [
                ('生产成本', '5001'),
                ('管理费用', '6602'),
                ('销售费用', '6601'),
            ]
        # Assign amounts to departments in order
        depts = []
        for i, (dept_name, acct_code) in enumerate(matched_depts):
            if i < len(amounts):
                dept_amt = round(amounts[i], 2)
            else:
                dept_amt = 0
            depts.append({"account_code": acct_code, "account_name": dept_name,
                          "debit": dept_amt, "credit": 0})
        total = sum(d['debit'] for d in depts)
        depts.append({"account_code": "2211", "account_name": "应付职工薪酬", "debit": 0, "credit": round(total, 2)})
        return depts

    def _parse_loan_repayment_with_interest(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 2:
            principal, interest = amounts[0], amounts[1]
        else:
            principal = amounts[0] if amounts else 0
            interest = round(principal * 0.05, 2)
        return [
            {"account_code": "2001", "account_name": "短期借款", "debit": round(principal, 2), "credit": 0},
            {"account_code": "6603", "account_name": "财务费用", "debit": round(interest, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(principal + interest, 2)},
        ]

    def _parse_investment_and_loan(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 2:
            invest, loan = amounts[0], amounts[1]
        else:
            invest = amounts[0] if amounts else 0
            loan = round(invest * 0.5, 2)
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(invest + loan, 2), "credit": 0},
            {"account_code": "4001", "account_name": "实收资本", "debit": 0, "credit": round(invest, 2)},
            {"account_code": "2001", "account_name": "短期借款", "debit": 0, "credit": round(loan, 2)},
        ]

    def _parse_depr_and_amort(t):
        amounts = _extract_all_amounts(t)
        if len(amounts) >= 2:
            depr, amort = amounts[0], amounts[1]
        else:
            depr = amounts[0] if amounts else 0
            amort = round(depr * 0.3, 2)
        return [
            {"account_code": "6602", "account_name": "管理费用-折旧", "debit": round(depr, 2), "credit": 0},
            {"account_code": "6602", "account_name": "管理费用-摊销", "debit": round(amort, 2), "credit": 0},
            {"account_code": "1602", "account_name": "累计折旧", "debit": 0, "credit": round(depr, 2)},
            {"account_code": "1702", "account_name": "累计摊销", "debit": 0, "credit": round(amort, 2)},
        ]

    def _parse_purchase_with_freight(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        freight = round(total * 0.05, 2) if len(amounts) < 2 else amounts[1]
        goods = total - freight
        return [
            {"account_code": "1403", "account_name": "原材料", "debit": round(goods, 2), "credit": 0},
            {"account_code": "6602", "account_name": "管理费用-运费", "debit": round(freight, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_sale_with_discount(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        discount = round(total * 0.1, 2) if len(amounts) < 2 else amounts[1]
        net = total - discount
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(net, 2), "credit": 0},
            {"account_code": "6601", "account_name": "销售费用-折扣", "debit": round(discount, 2), "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_equity_investment_fixed(t):
        amounts = _extract_all_amounts(t)
        val = amounts[0] if amounts else 0
        return [
            {"account_code": "1601", "account_name": "固定资产", "debit": round(val, 2), "credit": 0},
            {"account_code": "4001", "account_name": "实收资本", "debit": 0, "credit": round(val, 2)},
        ]

    def _parse_income_tax(t):
        amounts = _extract_all_amounts(t)
        tax = amounts[0] if amounts else 0
        return [
            {"account_code": "6801", "account_name": "所得税费用", "debit": round(tax, 2), "credit": 0},
            {"account_code": "2231", "account_name": "应交税费-应交所得税", "debit": 0, "credit": round(tax, 2)},
        ]

    def _parse_profit_distribution(t):
        amounts = _extract_all_amounts(t)
        profit = amounts[0] if amounts else 0
        dividend = round(profit * 0.3, 2)
        return [
            {"account_code": "4104", "account_name": "利润分配-未分配利润", "debit": round(dividend, 2), "credit": 0},
            {"account_code": "2232", "account_name": "应付股利", "debit": 0, "credit": round(dividend, 2)},
        ]

    def _parse_prepayment_purchase(t):
        amounts = _extract_all_amounts(t)
        amt = amounts[0] if amounts else 0
        return [
            {"account_code": "1123", "account_name": "预付账款", "debit": round(amt, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(amt, 2)},
        ]

    def _parse_social_insurance(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        company = round(total * 0.7, 2)
        return [
            {"account_code": "6601", "account_name": "管理费用-社保", "debit": round(company, 2), "credit": 0},
            {"account_code": "2211", "account_name": "应付职工薪酬-社保", "debit": 0, "credit": round(total, 2)},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_housing_fund(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        return [
            {"account_code": "6601", "account_name": "管理费用-公积金", "debit": round(total, 2), "credit": 0},
            {"account_code": "2211", "account_name": "应付职工薪酬-公积金", "debit": 0, "credit": round(total, 2)},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(total, 2)},
        ]

    def _parse_fixed_asset_disposal(t):
        amounts = _extract_all_amounts(t)
        proceeds = amounts[0] if amounts else 1000
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(proceeds, 2), "credit": 0},
            {"account_code": "1601", "account_name": "固定资产", "debit": 0, "credit": round(proceeds * 1.2, 2)},
            {"account_code": "1602", "account_name": "累计折旧", "debit": round(proceeds * 0.2, 2), "credit": 0},
        ]

    def _parse_prepayment_received(t):
        amounts = _extract_all_amounts(t)
        amt = amounts[0] if amounts else 0
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(amt, 2), "credit": 0},
            {"account_code": "2203", "account_name": "预收账款", "debit": 0, "credit": round(amt, 2)},
        ]

    def _parse_bad_debt_writeoff(t):
        amounts = _extract_all_amounts(t)
        amt = amounts[0] if amounts else 0
        return [
            {"account_code": "1231", "account_name": "坏账准备", "debit": round(amt, 2), "credit": 0},
            {"account_code": "1122", "account_name": "应收账款", "debit": 0, "credit": round(amt, 2)},
        ]

    def _parse_export_with_rebate(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        rebate = round(total * 0.13, 2)
        return [
            {"account_code": "1002", "account_name": "银行存款", "debit": round(total + rebate, 2), "credit": 0},
            {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": round(total, 2)},
            {"account_code": "2231", "account_name": "应交税费-出口退税", "debit": 0, "credit": round(rebate, 2)},
        ]

    def _parse_cip_to_fixed(t):
        amounts = _extract_all_amounts(t)
        val = amounts[0] if amounts else 0
        return [
            {"account_code": "1601", "account_name": "固定资产", "debit": round(val, 2), "credit": 0},
            {"account_code": "1604", "account_name": "在建工程", "debit": 0, "credit": round(val, 2)},
        ]

    def _parse_salary_with_tax(t):
        amounts = _extract_all_amounts(t)
        total = amounts[0] if amounts else 0
        tax = round(total * 0.1, 2)
        net = total - tax
        return [
            {"account_code": "2211", "account_name": "应付职工薪酬", "debit": round(total, 2), "credit": 0},
            {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": round(net, 2)},
            {"account_code": "2231", "account_name": "应交税费-个人所得税", "debit": 0, "credit": round(tax, 2)},
        ]

    # 复合业务规则（优先匹配）
    composite_rules = [
        {"pattern": r'(购入|购买|采购|购)(设备|机器|材料|原材料|商品|货物).+(其中|一部?分?).+(支付|付现|银行存款|现金).+(余款|剩余|欠|赊|应付)',
         "desc_fn": lambda m: f"购入{m.group(2)}，部分付现部分赊购", "parser": _parse_partial_cash_credit, "confidence": 0.95},
        {"pattern": r'(销售|卖出|出售|销)(商品|货物|产品|材料).+(其中|一部?分?).+(收现|收到|银行存款|现金).+(余款|剩余|赊|应收|欠款)',
         "desc_fn": lambda m: "销售商品，部分收现部分赊销", "parser": _parse_partial_cash_ar, "confidence": 0.95},
        {"pattern": r'(报销|差旅费|出差).+(其中|一部?分?).+(现金|银行存款|付现).+(冲|抵|还|借款|其他应收款)',
         "desc_fn": lambda m: "报销差旅费，部分付现部分冲借款", "parser": _parse_expense_reimbursement, "confidence": 0.93},
        {"pattern": r'(购入|购买|采购|购)(材料|原材料|设备|商品|货物).+(增值税|进项税|税率)',
         "desc_fn": lambda m: "购入货物含增值税进项", "parser": _parse_purchase_with_vat, "confidence": 0.93},
        {"pattern": r'(计提|分配).+(工资|薪酬|职工薪酬).+(生产|管理|销售|研发)',
         "desc_fn": lambda m: "计提工资分配到多科目", "parser": _parse_salary_allocation, "confidence": 0.92},
        {"pattern": r'(归还|偿还|还)(借款|贷款).+(利息|手续费)',
         "desc_fn": lambda m: "归还借款并支付利息", "parser": _parse_loan_repayment_with_interest, "confidence": 0.93},
        {"pattern": r'(投资|注资|出资).+(借款|贷款|银行)',
         "desc_fn": lambda m: "收到投资款及银行借款", "parser": _parse_investment_and_loan, "confidence": 0.90},
        {"pattern": r'(折旧|计提折旧).+(摊销|无形资产)',
         "desc_fn": lambda m: "计提折旧及无形资产摊销", "parser": _parse_depr_and_amort, "confidence": 0.92},
        # ── Phase 7 新增复合规则 ──
        {"pattern": r'(采购|购买|购入|购)(材料|原材料|商品|货物).+(运费|运输费|物流费|装卸费)',
         "desc_fn": lambda m: "采购货物并支付运费", "parser": _parse_purchase_with_freight, "confidence": 0.94},
        {"pattern": r'(销售|卖出|出售|销)(商品|货物|产品).+(折扣|折让|优惠|返利)',
         "desc_fn": lambda m: "销售商品并给予折扣", "parser": _parse_sale_with_discount, "confidence": 0.94},
        {"pattern": r'(收到|收)(投资|注资|出资|股东).+(设备|固定资产|资产).+(股权|资本|股份)',
         "desc_fn": lambda m: "收到固定资产投资（实物出资）", "parser": _parse_equity_investment_fixed, "confidence": 0.91},
        {"pattern": r'(计提|分配|结转).+(所得税|企业所得税|所得)',
         "desc_fn": lambda m: "计提所得税费用", "parser": _parse_income_tax, "confidence": 0.92},
        {"pattern": r'(利润|净利润|本年利润).+(分配|分红|股利|派息)',
         "desc_fn": lambda m: "利润分配（宣告股利）", "parser": _parse_profit_distribution, "confidence": 0.93},
        {"pattern": r'(购入|购买|采购).+(材料|原材料).+(预付|预付款|先付)',
         "desc_fn": lambda m: "预付采购货款", "parser": _parse_prepayment_purchase, "confidence": 0.93},
        {"pattern": r'(支付|付|交).+(社保|社会保险|养老保险|医疗保险)',
         "desc_fn": lambda m: "支付社会保险费", "parser": _parse_social_insurance, "confidence": 0.92},
        {"pattern": r'(支付|付|交).+(公积金|住房公积金)',
         "desc_fn": lambda m: "支付住房公积金", "parser": _parse_housing_fund, "confidence": 0.92},
        {"pattern": r'(处置|出售|卖出).+(固定资产|设备|机器).+(清理|报废|转让)',
         "desc_fn": lambda m: "处置固定资产", "parser": _parse_fixed_asset_disposal, "confidence": 0.91},
        {"pattern": r'(收到|收)(客户|买方|购货方).+(预付|预付款|定金)',
         "desc_fn": lambda m: "收到客户预付货款", "parser": _parse_prepayment_received, "confidence": 0.93},
        {"pattern": r'(结转|转销|核销).+(坏账|坏账准备|减值)',
         "desc_fn": lambda m: "核销坏账准备", "parser": _parse_bad_debt_writeoff, "confidence": 0.92},
        {"pattern": r'(出口|外销|外贸).+(销售|卖出|出售).+(退税|出口退税)',
         "desc_fn": lambda m: "出口销售并确认退税", "parser": _parse_export_with_rebate, "confidence": 0.90},
        {"pattern": r'(建造|建设|施工|在建工程).+(完工|竣工|验收).+(转固|结转)',
         "desc_fn": lambda m: "在建工程完工转固", "parser": _parse_cip_to_fixed, "confidence": 0.93},
        {"pattern": r'(发放|发).+(工资|薪酬).+(代扣|扣除).+(个税|个人所得税)',
         "desc_fn": lambda m: "发放工资并代扣个税", "parser": _parse_salary_with_tax, "confidence": 0.93},
    ]

    # 尝试复合规则匹配
    composite_matched = False
    for cr in composite_rules:
        m = re.search(cr["pattern"], text)
        if m:
            try:
                parsed = cr["parser"](text)
                if parsed and len(parsed) >= 2:
                    entries = parsed
                    description = cr["desc_fn"](m)
                    confidence = cr["confidence"]
                    is_composite = True
                    composite_matched = True
                    break
            except Exception:
                continue

    if not composite_matched:
        # ===== 简单规则（原有逻辑）=====
        amount = _extract_amount(text)
        if amount is None:
            amount = 0

        currency = _extract_currency(text)
        if currency != 'CNY':
            exchange_rate = get_exchange_rate(currency, 'CNY', datetime.now().strftime('%Y-%m-%d')) or 1.0
        else:
            exchange_rate = 1.0

        # 简单规则回退
        if not entries:
            amount = amount or _extract_amount(text) or 0
            # 基本关键词匹配
            if any(kw in text for kw in ["收入", "销售", "卖出"]):
                entries = [
                    {"account_code": "1002", "account_name": "银行存款", "debit": amount, "credit": 0},
                    {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": amount},
                ]
                description = "确认收入"
                confidence = 0.70
            elif any(kw in text for kw in ["采购", "购入", "购买"]):
                entries = [
                    {"account_code": "1403", "account_name": "原材料", "debit": amount, "credit": 0},
                    {"account_code": "1002", "account_name": "银行存款", "debit": 0, "credit": amount},
                ]
                description = "采购原材料"
                confidence = 0.70
            elif any(kw in text for kw in ["报销", "费用"]):
                entries = [
                    {"account_code": "6602", "account_name": "管理费用", "debit": amount, "credit": 0},
                    {"account_code": "1001", "account_name": "库存现金", "debit": 0, "credit": amount},
                ]
                description = "报销费用"
                confidence = 0.70
            else:
                entries = [
                    {"account_code": "1002", "account_name": "银行存款", "debit": amount, "credit": 0},
                    {"account_code": "6001", "account_name": "主营业务收入", "debit": 0, "credit": amount},
                ]
                description = text[:30]
                confidence = 0.50

    return {"description": description, "entries": entries, "confidence": confidence,
            "composite": is_composite, "currency": currency, "exchange_rate": exchange_rate}


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


# ── 损益结转 ──

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
                remark=f"{year}-{month}月结转 净利润:{net_profit/100:.2f}元",
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


# ── 审计日志 ──

def add_audit_log(ledger_id, action, detail, voucher_id=None, user_id=None,
                  operator_name=None, module=None, target_table=None, target_id=None,
                  old_value=None, new_value=None, ip_address=None, remark=None):
    """写入审计日志（支持完整字段）
    
    Args:
        ledger_id: 账套ID
        action: 操作类型 (create_voucher/delete_voucher/post_voucher/restore/...)
        detail: 操作描述
        voucher_id: 关联凭证ID
        user_id: 操作人ID
        operator_name: 操作人姓名
        module: 模块 (voucher/account/period/system/settings/...)
        target_table: 目标表名
        target_id: 目标记录ID
        old_value: 变更前值 (JSON字符串)
        new_value: 变更后值 (JSON字符串)
        ip_address: IP地址
        remark: 备注
    """
    import json as _json
    conn = get_conn()
    conn.execute(
        """INSERT INTO audit_logs 
           (ledger_id, action, detail, voucher_id, user_id, operator_name, module,
            target_table, target_id, old_value, new_value, ip_address, remark)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ledger_id, action, detail, voucher_id, user_id, operator_name, module,
         target_table, target_id,
         _json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
         _json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
         ip_address, remark)
    )
    conn.commit()
    conn.close()
    clear_query_cache()


# ── 凭证模板 ──

def get_voucher_templates(ledger_id, include_inactive=False):
    """获取凭证模板列表"""
    import json
    conn = get_conn()
    if include_inactive:
        rows = conn.execute(
            "SELECT * FROM voucher_templates WHERE ledger_id = ? ORDER BY is_system DESC, category, name",
            (ledger_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM voucher_templates WHERE ledger_id = ? AND is_active = 1 ORDER BY is_system DESC, category, name",
            (ledger_id,)
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["entries"] = json.loads(d["entries"]) if d["entries"] else []
        result.append(d)
    return result


def create_voucher_template(ledger_id, name, description, entries, category='general', is_system=0):
    """创建凭证模板"""
    import json
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO voucher_templates (ledger_id, name, description, category, entries, is_system) VALUES (?,?,?,?,?,?)",
            (ledger_id, name, description, category, json.dumps(entries, ensure_ascii=False), is_system)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"模板名称 '{name}' 已存在")
    finally:
        conn.close()


def update_voucher_template(template_id, ledger_id, name=None, description=None, entries=None, category=None, is_active=None):
    """更新凭证模板"""
    import json
    conn = get_conn()
    updates = {}
    if name is not None:
        updates["name"] = name
    if description is not None:
        updates["description"] = description
    if entries is not None:
        updates["entries"] = json.dumps(entries, ensure_ascii=False)
    if category is not None:
        updates["category"] = category
    if is_active is not None:
        updates["is_active"] = 1 if is_active else 0
    if not updates:
        conn.close()
        return
    updates["updated_at"] = "datetime('now','localtime')"
    # 手动构建 SET 子句，因为 updated_at 是 SQL 表达式
    set_parts = []
    params = []
    for k, v in updates.items():
        if k == "updated_at":
            set_parts.append(f"{k} = {v}")
        else:
            set_parts.append(f"{k} = ?")
            params.append(v)
    params.extend([template_id, ledger_id])
    conn.execute(
        f"UPDATE voucher_templates SET {', '.join(set_parts)} WHERE id = ? AND ledger_id = ? AND is_system = 0",
        params
    )
    conn.commit()
    conn.close()
    clear_query_cache()


def delete_voucher_template(template_id, ledger_id):
    """删除凭证模板（不能删除系统模板）"""
    conn = get_conn()
    conn.execute(
        "DELETE FROM voucher_templates WHERE id = ? AND ledger_id = ? AND is_system = 0",
        (template_id, ledger_id)
    )
    conn.commit()
    conn.close()
    clear_query_cache()


def init_system_templates(ledger_id):
    """初始化系统内置凭证模板"""
    import json
    templates = [
        {
            "name": "收款-客户回款",
            "description": "收到客户货款",
            "entries": [
                {"account_code": "1002", "account_name": "银行存款", "direction": "debit", "summary": "收到货款"},
                {"account_code": "1122", "account_name": "应收账款", "direction": "credit", "summary": "收到货款"}
            ]
        },
        {
            "name": "付款-供应商结算",
            "description": "支付供应商货款",
            "entries": [
                {"account_code": "2202", "account_name": "应付账款", "direction": "debit", "summary": "支付货款"},
                {"account_code": "1002", "account_name": "银行存款", "direction": "credit", "summary": "支付货款"}
            ]
        },
        {
            "name": "费用报销-差旅",
            "description": "员工差旅费报销",
            "entries": [
                {"account_code": "6602", "account_name": "管理费用-差旅费", "direction": "debit", "summary": "差旅费报销"},
                {"account_code": "1001", "account_name": "库存现金", "direction": "credit", "summary": "差旅费报销"}
            ]
        },
        {
            "name": "工资发放",
            "description": "发放员工工资",
            "entries": [
                {"account_code": "2211", "account_name": "应付职工薪酬", "direction": "debit", "summary": "发放工资"},
                {"account_code": "1002", "account_name": "银行存款", "direction": "credit", "summary": "发放工资"}
            ]
        },
        {
            "name": "采购入库",
            "description": "采购商品入库",
            "entries": [
                {"account_code": "1405", "account_name": "库存商品", "direction": "debit", "summary": "采购入库"},
                {"account_code": "2202", "account_name": "应付账款", "direction": "credit", "summary": "采购入库"}
            ]
        },
        {
            "name": "销售确认收入",
            "description": "确认销售收入",
            "entries": [
                {"account_code": "1122", "account_name": "应收账款", "direction": "debit", "summary": "确认收入"},
                {"account_code": "6001", "account_name": "主营业务收入", "direction": "credit", "summary": "确认收入"}
            ]
        },
        {
            "name": "折旧计提",
            "description": "月末计提折旧",
            "entries": [
                {"account_code": "6602", "account_name": "管理费用-折旧费", "direction": "debit", "summary": "计提折旧"},
                {"account_code": "1602", "account_name": "累计折旧", "direction": "credit", "summary": "计提折旧"}
            ]
        },
        {
            "name": "月末结转损益",
            "description": "期末损益结转",
            "entries": [
                {"account_code": "6001", "account_name": "主营业务收入", "direction": "debit", "summary": "结转收入"},
                {"account_code": "3131", "account_name": "本年利润", "direction": "credit", "summary": "结转收入"},
                {"account_code": "3131", "account_name": "本年利润", "direction": "debit", "summary": "结转费用"},
                {"account_code": "6401", "account_name": "主营业务成本", "direction": "credit", "summary": "结转费用"}
            ]
        }
    ]
    conn = get_conn()
    for t in templates:
        conn.execute(
            "INSERT INTO voucher_templates (ledger_id, name, description, entries, is_system) VALUES (?,?,?,?,1)",
            (ledger_id, t["name"], t["description"], json.dumps(t["entries"], ensure_ascii=False))
        )
    conn.commit()
    conn.close()
    clear_query_cache()


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



def get_audit_logs(ledger_id, limit=50, module=None, action=None, start_date=None, end_date=None):
    """查询审计日志（支持多维度筛选）"""
    conn = get_conn()
    conditions = ["ledger_id = ?"]
    params = [ledger_id]
    if module:
        conditions.append("module = ?")
        params.append(module)
    if action:
        conditions.append("action = ?")
        params.append(action)
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date)
    params.append(limit)
    # SECURITY: conditions are all hardcoded strings, user input goes through parameterized query
    # No SQL injection risk. Do not modify conditions to include user input directly.
    where = " AND ".join(conditions)
    rows = conn.execute(
        f"SELECT * FROM audit_logs WHERE {where} ORDER BY created_at DESC LIMIT ?",
        params
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── 科目管理 ──

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


# ── 用户认证 ──

def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(password: str, password_hash: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_user(username: str, password: str, role: str = "user", ledger_id: int = None):
    """创建用户"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, ledger_id) VALUES (?,?,?,?)",
            (username, hash_password(password), role, ledger_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"用户名 {username} 已存在")
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict:
    """验证用户登录，返回用户信息（bcrypt 验证）"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1",
        (username,)
    ).fetchone()
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        return dict(row)
    return None


def get_users(ledger_id: int = None) -> list:
    """获取用户列表"""
    conn = get_conn()
    if ledger_id:
        rows = conn.execute("SELECT id, username, role, ledger_id, is_active, created_at FROM users WHERE ledger_id = ? ORDER BY created_at", (ledger_id,)).fetchall()
    else:
        rows = conn.execute("SELECT id, username, role, ledger_id, is_active, created_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user(user_id: int, **kwargs):
    """更新用户信息"""
    allowed = {"role", "is_active", "ledger_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn = get_conn()
    conn.execute(f"UPDATE users SET {set_clause}, updated_at = datetime('now','localtime') WHERE id = ?",
                 list(updates.values()) + [user_id])
    conn.commit()
    conn.close()
    clear_query_cache()


def delete_user(user_id: int):
    """删除用户"""
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    clear_query_cache()


def change_password(user_id: int, new_password: str):
    """修改密码"""
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                 (hash_password(new_password), user_id))
    conn.commit()
    conn.close()
    clear_query_cache()


# ── P2-1: 审核流程 & 权限 ──

# 角色定义
ROLE_ADMIN      = "admin"       # 管理员：所有权限
ROLE_ACCOUNTANT = "accountant"  # 制单人：新增/编辑/提交/删除草稿
ROLE_REVIEWER   = "reviewer"    # 审核人：审核/驳回
ROLE_POSTER     = "poster"      # 过账人：过账/反过账
ROLE_VIEWER     = "viewer"      # 查看者：只读

ALL_ROLES = [ROLE_ADMIN, ROLE_ACCOUNTANT, ROLE_REVIEWER, ROLE_POSTER, ROLE_VIEWER]

# 权限矩阵
PERMISSIONS = {
    "voucher_create":  {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "voucher_edit":    {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "voucher_delete":  {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "voucher_submit":  {ROLE_ADMIN, ROLE_ACCOUNTANT},
    "voucher_approve": {ROLE_ADMIN, ROLE_REVIEWER},
    "voucher_reject":  {ROLE_ADMIN, ROLE_REVIEWER},
    "voucher_post":    {ROLE_ADMIN, ROLE_POSTER},
    "voucher_reverse": {ROLE_ADMIN, ROLE_POSTER},
    "voucher_view":    {ROLE_ADMIN, ROLE_ACCOUNTANT, ROLE_REVIEWER, ROLE_POSTER, ROLE_VIEWER},
}


def check_permission(user: dict, permission: str) -> bool:
    """检查用户是否有指定权限"""
    if not user:
        return False
    role = user.get("role", ROLE_VIEWER)
    if role == ROLE_ADMIN:
        return True
    return role in PERMISSIONS.get(permission, set())


def add_workflow_log(ledger_id, voucher_id, action, from_status, to_status, user_id=None, comment=None):
    """记录审核工作流日志"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO voucher_workflow (voucher_id, ledger_id, action, from_status, to_status, user_id, comment) "
        "VALUES (?,?,?,?,?,?,?)",
        (voucher_id, ledger_id, action, from_status, to_status, user_id, comment)
    )
    conn.commit()
    conn.close()
    clear_query_cache()


def get_voucher_workflow(voucher_id: int) -> list:
    """获取凭证的审核流程历史"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT w.*, u.username "
        "FROM voucher_workflow w "
        "LEFT JOIN users u ON w.user_id = u.id "
        "WHERE w.voucher_id = ? ORDER BY w.created_at ASC",
        (voucher_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── P2-2: 增值税管理 ──

def get_tax_config(ledger_id: int) -> dict:
    """获取账套增值税配置"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM tax_config WHERE ledger_id = ?", (ledger_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_tax_config(ledger_id: int, taxpayer_type: str = "general", default_tax_rate: float = 0.13):
    """设置账套增值税配置"""
    conn = get_conn()
    existing = conn.execute("SELECT id FROM tax_config WHERE ledger_id = ?", (ledger_id,)).fetchone()
    if existing:
        conn.execute("UPDATE tax_config SET taxpayer_type=?, default_tax_rate=?, updated_at=datetime('now','localtime') WHERE ledger_id=?",
                     (taxpayer_type, default_tax_rate, ledger_id))
    else:
        conn.execute("INSERT INTO tax_config (ledger_id, taxpayer_type, default_tax_rate) VALUES (?,?,?)",
                     (ledger_id, taxpayer_type, default_tax_rate))
    conn.commit()
    conn.close()
    clear_query_cache()


def get_tax_rates(ledger_id: int) -> list:
    """获取账套税率列表"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tax_rates WHERE ledger_id = ? AND is_active = 1 ORDER BY rate ASC", (ledger_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_tax_rate(ledger_id: int, rate: float, name: str, description: str = "", is_default: int = 0):
    """添加税率"""
    conn = get_conn()
    if is_default:
        conn.execute("UPDATE tax_rates SET is_default = 0 WHERE ledger_id = ?", (ledger_id,))
    conn.execute("INSERT INTO tax_rates (ledger_id, rate, name, description, is_default) VALUES (?,?,?,?,?)",
                 (ledger_id, rate, name, description, is_default))
    conn.commit()
    conn.close()
    clear_query_cache()


def get_tax_summary(ledger_id: int, year: int, month: int) -> dict:
    """获取增值税汇总数据（进项/销项税额统计）"""
    conn = get_conn()
    # 进项税额（借方分录中的税额）
    input_tax = conn.execute(
        "SELECT COALESCE(SUM(je.tax_amount), 0) as total_input_tax "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' AND je.tax_type = 'input' "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ?",
        (ledger_id, str(year), f"{month:02d}")
    ).fetchone()["total_input_tax"]

    # 销项税额（贷方分录中的税额）
    output_tax = conn.execute(
        "SELECT COALESCE(SUM(je.tax_amount), 0) as total_output_tax "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' AND je.tax_type = 'output' "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ?",
        (ledger_id, str(year), f"{month:02d}")
    ).fetchone()["total_output_tax"]

    config = get_tax_config(ledger_id)
    conn.close()

    return {
        "input_tax": input_tax,
        "output_tax": output_tax,
        "tax_payable": output_tax - input_tax,
        "taxpayer_type": config.get("taxpayer_type", "general") if config else "general",
        "default_rate": config.get("default_tax_rate", 0.13) if config else 0.13,
    }


def get_tax_detail(ledger_id: int, year: int, month: int, tax_type: str = "input") -> list:
    """获取进项/销项税额明细"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT je.account_code, je.account_name, je.tax_rate, je.tax_amount, "
        "v.voucher_no, v.date, v.description "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' AND je.tax_type = ? "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ? "
        "ORDER BY v.date ASC",
        (ledger_id, tax_type, str(year), f"{month:02d}")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── P2-5: 现金流量表 ──

def get_cash_flow_categories(ledger_id: int) -> list:
    """获取现金流分类列表"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM cash_flow_categories WHERE ledger_id = ? AND is_active = 1 ORDER BY category, code",
        (ledger_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_cash_flow_category(ledger_id: int, code: str, name: str, category: str, parent_code: str = None):
    """添加现金流分类"""
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO cash_flow_categories (ledger_id, code, name, category, parent_code) VALUES (?,?,?,?,?)",
        (ledger_id, code, name, category, parent_code)
    )
    conn.commit()
    conn.close()
    clear_query_cache()


def get_cash_flow_statement(ledger_id: int, year: int, month: int, method: str = "direct") -> dict:
    """
    生成现金流量表
    method: 'direct' 直接法, 'indirect' 间接法
    """
    conn = get_conn()

    # 按现金流分类汇总
    rows = conn.execute(
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

    # 现金流分类映射
    cf_categories = {
        "operating_inflow":  {"name": "经营活动现金流入",  "section": "operating"},
        "operating_outflow": {"name": "经营活动现金流出",  "section": "operating"},
        "investing_inflow":  {"name": "投资活动现金流入",  "section": "investing"},
        "investing_outflow": {"name": "投资活动现金流出",  "section": "investing"},
        "financing_inflow":  {"name": "筹资活动现金流入",  "section": "financing"},
        "financing_outflow": {"name": "筹资活动现金流出",  "section": "financing"},
    }

    operating_inflow = 0
    operating_outflow = 0
    investing_inflow = 0
    investing_outflow = 0
    financing_inflow = 0
    financing_outflow = 0

    detail_rows = []
    for row in rows:
        cf_type = row["cash_flow_type"]
        net = row["total_debit"] - row["total_credit"]
        cat = cf_categories.get(cf_type, {"name": cf_type, "section": "other"})
        detail_rows.append({"type": cf_type, "name": cat["name"], "section": cat["section"],
                            "debit": row["total_debit"], "credit": row["total_credit"], "net": net})

        if cf_type == "operating_inflow":   operating_inflow += row["total_debit"]
        elif cf_type == "operating_outflow": operating_outflow += row["total_credit"]
        elif cf_type == "investing_inflow":  investing_inflow += row["total_debit"]
        elif cf_type == "investing_outflow": investing_outflow += row["total_credit"]
        elif cf_type == "financing_inflow":  financing_inflow += row["total_debit"]
        elif cf_type == "financing_outflow": financing_outflow += row["total_credit"]

    # 如果没有现金流分类数据，基于科目自动推断
    if not detail_rows:
        detail_rows = _infer_cash_flow(conn, ledger_id, year, month)
        for d in detail_rows:
            if d["type"] == "operating_inflow":   operating_inflow += max(d["net"], 0)
            elif d["type"] == "operating_outflow": operating_outflow += abs(min(d["net"], 0))
            elif d["type"] == "investing_inflow":  investing_inflow += max(d["net"], 0)
            elif d["type"] == "investing_outflow": investing_outflow += abs(min(d["net"], 0))
            elif d["type"] == "financing_inflow":  financing_inflow += max(d["net"], 0)
            elif d["type"] == "financing_outflow": financing_outflow += abs(min(d["net"], 0))

    net_operating = operating_inflow - operating_outflow
    net_investing = investing_inflow - investing_outflow
    net_financing = financing_inflow - financing_outflow
    net_cash_change = net_operating + net_investing + net_financing

    conn.close()

    return {
        "method": method,
        "year": year,
        "month": month,
        "operating": {
            "inflow": operating_inflow,
            "outflow": operating_outflow,
            "net": net_operating,
        },
        "investing": {
            "inflow": investing_inflow,
            "outflow": investing_outflow,
            "net": net_investing,
        },
        "financing": {
            "inflow": financing_inflow,
            "outflow": financing_outflow,
            "net": net_financing,
        },
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


# ── P2-4: 预算管理 ──

def get_budgets(ledger_id: int, year: int, month: int = None) -> list:
    """获取预算列表"""
    conn = get_conn()
    if month:
        rows = conn.execute(
            "SELECT * FROM budgets WHERE ledger_id = ? AND budget_year = ? AND budget_month = ? ORDER BY account_code",
            (ledger_id, year, month)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM budgets WHERE ledger_id = ? AND budget_year = ? ORDER BY account_code, budget_month",
            (ledger_id, year)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_budget(ledger_id: int, account_code: str, account_name: str, year: int, month: int, amount: float, description: str = ""):
    """设置/更新预算"""
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM budgets WHERE ledger_id = ? AND account_code = ? AND budget_year = ? AND budget_month = ?",
        (ledger_id, account_code, year, month)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE budgets SET budget_amount=?, account_name=?, description=?, updated_at=datetime('now','localtime') WHERE id=?",
            (amount, account_name, description, existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO budgets (ledger_id, account_code, account_name, budget_year, budget_month, budget_amount, description) VALUES (?,?,?,?,?,?,?)",
            (ledger_id, account_code, account_name, year, month, amount, description)
        )
    conn.commit()
    conn.close()
    clear_query_cache()


def get_budget_execution(ledger_id: int, year: int, month: int) -> list:
    """获取预算执行情况（预算 vs 实际）"""
    conn = get_conn()
    # 获取该月所有预算
    budgets = conn.execute(
        "SELECT * FROM budgets WHERE ledger_id = ? AND budget_year = ? AND budget_month = ?",
        (ledger_id, year, month)
    ).fetchall()

    results = []
    for b in budgets:
        # 计算实际发生额（借方合计）
        actual = conn.execute(
            "SELECT COALESCE(SUM(je.debit), 0) as total_debit "
            "FROM journal_entries je "
            "JOIN vouchers v ON je.voucher_id = v.id "
            "WHERE v.ledger_id = ? AND v.status = 'posted' "
            "AND je.account_code = ? "
            "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ?",
            (ledger_id, b["account_code"], str(year), f"{month:02d}")
        ).fetchone()["total_debit"]

        budget_amount = b["budget_amount"]
        variance = actual - budget_amount
        variance_pct = (variance / budget_amount * 100) if budget_amount > 0 else 0

        results.append({
            "id": b["id"],
            "account_code": b["account_code"],
            "account_name": b["account_name"],
            "budget_amount": budget_amount,
            "actual_amount": actual,
            "variance": variance,
            "variance_pct": variance_pct,
            "is_over_budget": actual > budget_amount if budget_amount > 0 else False,
        })

    conn.close()
    return results


def get_budget_summary(ledger_id: int, year: int, month: int) -> dict:
    """获取预算汇总"""
    execution = get_budget_execution(ledger_id, year, month)
    total_budget = sum(e["budget_amount"] for e in execution)
    total_actual = sum(e["actual_amount"] for e in execution)
    over_budget_count = sum(1 for e in execution if e["is_over_budget"])
    return {
        "total_budget": total_budget,
        "total_actual": total_actual,
        "total_variance": total_actual - total_budget,
        "over_budget_count": over_budget_count,
        "item_count": len(execution),
    }


def check_budget_exceeded(ledger_id: int, account_code: str, year: int, month: int, additional_amount: float = 0) -> dict:
    """检查是否超预算（凭证录入时调用）"""
    conn = get_conn()
    budget = conn.execute(
        "SELECT budget_amount FROM budgets WHERE ledger_id = ? AND account_code = ? AND budget_year = ? AND budget_month = ?",
        (ledger_id, account_code, year, month)
    ).fetchone()

    if not budget or budget["budget_amount"] <= 0:
        conn.close()
        return {"has_budget": False, "exceeded": False}

    actual = conn.execute(
        "SELECT COALESCE(SUM(je.debit), 0) as total_debit "
        "FROM journal_entries je "
        "JOIN vouchers v ON je.voucher_id = v.id "
        "WHERE v.ledger_id = ? AND v.status = 'posted' "
        "AND je.account_code = ? "
        "AND strftime('%Y', v.date) = ? AND strftime('%m', v.date) = ?",
        (ledger_id, account_code, str(year), f"{month:02d}")
    ).fetchone()["total_debit"]

    conn.close()

    projected = actual + additional_amount
    return {
        "has_budget": True,
        "budget_amount": budget["budget_amount"],
        "actual_amount": actual,
        "projected": projected,
        "exceeded": projected > budget["budget_amount"],
        "remaining": budget["budget_amount"] - projected,
    }


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


# ── P2-7: 定时自动凭证 ──

import json as _json_mod


def get_voucher_templates(ledger_id: int) -> list:
    """获取凭证模板列表"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM voucher_templates WHERE ledger_id = ? AND is_active = 1 ORDER BY name",
        (ledger_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_voucher_template(ledger_id: int, name: str, entries: list, description: str = "", voucher_type: str = "记") -> int:
    """保存凭证模板"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO voucher_templates (ledger_id, name, description, voucher_type, entries) VALUES (?,?,?,?,?)",
        (ledger_id, name, description, voucher_type, _json_mod.dumps(entries, ensure_ascii=False))
    )
    conn.commit()
    tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return tid


def get_scheduled_vouchers(ledger_id: int) -> list:
    """获取定时凭证任务列表"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT sv.*, vt.name as template_name "
        "FROM scheduled_vouchers sv "
        "LEFT JOIN voucher_templates vt ON sv.template_id = vt.id "
        "WHERE sv.ledger_id = ? AND sv.is_active = 1 "
        "ORDER BY sv.next_run_at",
        (ledger_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_scheduled_voucher(ledger_id: int, name: str, cron_expression: str, template_id: int = None, next_run_at: str = None):
    """添加定时凭证任务"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO scheduled_vouchers (ledger_id, template_id, name, cron_expression, next_run_at) VALUES (?,?,?,?,?)",
        (ledger_id, template_id, name, cron_expression, next_run_at)
    )
    conn.commit()
    conn.close()
    clear_query_cache()


def run_scheduled_voucher(scheduled_id: int) -> str:
    """执行定时凭证任务，生成实际凭证"""
    from datetime import datetime
    conn = get_conn()
    sv = conn.execute("SELECT * FROM scheduled_vouchers WHERE id = ?", (scheduled_id,)).fetchone()
    if not sv:
        conn.close()
        raise ValueError("定时任务不存在")

    entries = []
    if sv["template_id"]:
        tpl = conn.execute("SELECT entries FROM voucher_templates WHERE id = ?", (sv["template_id"],)).fetchone()
        if tpl:
            entries = _json_mod.loads(tpl["entries"])
    else:
        conn.close()
        raise ValueError("定时任务未关联凭证模板")

    if not entries:
        conn.close()
        raise ValueError("凭证模板分录为空")

    today = datetime.now().strftime("%Y-%m-%d")
    vn = create_voucher(sv["ledger_id"], today, f"[自动]{sv['name']}", entries, status="draft")

    # 更新最后执行时间
    conn.execute(
        "UPDATE scheduled_vouchers SET last_run_at = datetime('now','localtime'), updated_at = datetime('now','localtime') WHERE id = ?",
        (scheduled_id,)
    )
    conn.commit()
    conn.close()
    clear_query_cache()
    return vn


# ── Phase 4.1: AI 智能分类 ──

# 分类规则表（关键词 → 科目映射）
CLASSIFICATION_RULES = [
    {"keywords": ["工资", "薪资", "薪酬", "奖金", "津贴"], "account_code": "2211", "account_name": "应付职工薪酬", "direction": "credit", "category": "薪酬"},
    {"keywords": ["电费", "水费", "水电"], "account_code": "6602", "account_name": "管理费用-水电费", "direction": "debit", "category": "水电"},
    {"keywords": ["租金", "房租", "租赁费"], "account_code": "6602", "account_name": "管理费用-租金", "direction": "debit", "category": "租金"},
    {"keywords": ["货款", "采购", "购货", "进货"], "account_code": "1403", "account_name": "原材料", "direction": "debit", "category": "采购"},
    {"keywords": ["退款", "退回", "退票"], "account_code": "adjust", "account_name": "冲销原科目", "direction": "adjust", "category": "退款"},
    {"keywords": ["投资", "注资", "出资"], "account_code": "4001", "account_name": "实收资本", "direction": "credit", "category": "投资"},
    {"keywords": ["借款", "贷款", "融资"], "account_code": "2001", "account_name": "短期借款", "direction": "credit", "category": "借款"},
    {"keywords": ["销售收入", "营业收入", "销售", "卖出"], "account_code": "6001", "account_name": "主营业务收入", "direction": "credit", "category": "收入"},
    {"keywords": ["广告", "推广", "营销"], "account_code": "6601", "account_name": "销售费用-广告费", "direction": "debit", "category": "营销"},
    {"keywords": ["差旅", "出差", "交通费", "机票", "火车票"], "account_code": "6602", "account_name": "管理费用-差旅费", "direction": "debit", "category": "差旅"},
    {"keywords": ["办公", "文具", "打印", "耗材"], "account_code": "6602", "account_name": "管理费用-办公费", "direction": "debit", "category": "办公"},
    {"keywords": ["通讯", "电话", "网络", "宽带"], "account_code": "6602", "account_name": "管理费用-通讯费", "direction": "debit", "category": "通讯"},
    {"keywords": ["餐饮", "招待", "餐费"], "account_code": "6602", "account_name": "管理费用-业务招待费", "direction": "debit", "category": "招待"},
    {"keywords": ["维修", "修理", "维护"], "account_code": "6602", "account_name": "管理费用-维修费", "direction": "debit", "category": "维修"},
    {"keywords": ["保险", "社保", "公积金"], "account_code": "6602", "account_name": "管理费用-保险费", "direction": "debit", "category": "保险"},
    {"keywords": ["利息", "手续费", "银行费用"], "account_code": "6603", "account_name": "财务费用-利息", "direction": "debit", "category": "财务"},
    {"keywords": ["税款", "税金", "增值税", "所得税"], "account_code": "2221", "account_name": "应交税费", "direction": "credit", "category": "税费"},
    {"keywords": ["运费", "物流", "快递", "运输"], "account_code": "6601", "account_name": "销售费用-运费", "direction": "debit", "category": "运费"},
    {"keywords": ["折旧"], "account_code": "6602", "account_name": "管理费用-折旧费", "direction": "debit", "category": "折旧"},
    {"keywords": ["无形资产", "摊销"], "account_code": "6602", "account_name": "管理费用-摊销费", "direction": "debit", "category": "摊销"},
    {"keywords": ["政府补助", "补贴", "退税"], "account_code": "6301", "account_name": "营业外收入", "direction": "credit", "category": "补助"},
    {"keywords": ["捐赠", "捐款"], "account_code": "6711", "account_name": "营业外支出", "direction": "debit", "category": "捐赠"},
    {"keywords": ["罚款", "违约金", "赔偿"], "account_code": "6711", "account_name": "营业外支出-罚款", "direction": "debit", "category": "罚款"},
    {"keywords": ["应收账款", "欠款", "赊销"], "account_code": "1122", "account_name": "应收账款", "direction": "debit", "category": "应收"},
    {"keywords": ["应付账款", "欠款", "赊购"], "account_code": "2202", "account_name": "应付账款", "direction": "credit", "category": "应付"},
]


def classify_transaction(ledger_id, summary, amount, direction, counterparty=""):
    """智能分类单笔交易"""
    text = f"{summary} {counterparty}"

    best_match = None
    best_score = 0
    for rule in CLASSIFICATION_RULES:
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
        hist_result = _match_history(ledger_id, summary, amount)
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

    is_anomaly, anomaly_reason = _detect_anomaly(ledger_id, amount)

    return {
        "account_code": account_code, "account_name": account_name,
        "confidence": confidence, "category": category,
        "is_anomaly": is_anomaly, "anomaly_reason": anomaly_reason,
    }


def _match_history(ledger_id, summary, amount):
    """根据摘要关键词匹配历史凭证科目"""
    conn = get_conn()
    keywords = summary[:10] if len(summary) >= 3 else summary
    rows = conn.execute("""
        SELECT je.account_code, je.account_name, COUNT(*) as freq
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND v.status = 'posted'
          AND je.summary LIKE ?
        GROUP BY je.account_code
        ORDER BY freq DESC LIMIT 1
    """, (ledger_id, f"%{keywords}%")).fetchall()
    conn.close()
    if rows:
        return {"account_code": rows[0]["account_code"], "account_name": rows[0]["account_name"]}
    return None


def _detect_anomaly(ledger_id, amount):
    """异常交易检测"""
    conn = get_conn()
    stats = conn.execute("""
        SELECT COALESCE(AVG(ABS(debit) + ABS(credit)), 0) as avg_amt,
               COUNT(*) as cnt
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND v.status = 'posted'
    """, (ledger_id,)).fetchone()
    avg = stats["avg_amt"] if stats else 0
    cnt = stats["cnt"] if stats else 0
    conn.close()
    if cnt >= 10 and abs(amount) > avg * 3 and avg > 0:
        return True, f"金额 ¥{abs(amount):,.2f} 超过平均值 ¥{avg:,.2f} 的3倍"
    return False, ""


def batch_classify(ledger_id, transactions):
    """批量分类银行流水"""
    results = []
    for txn in transactions:
        classification = classify_transaction(
            ledger_id,
            txn.get("summary", ""),
            txn.get("amount", 0),
            txn.get("direction", "debit"),
            txn.get("counterparty", "")
        )
        results.append({**txn, **classification})
    return results


def get_classification_rules(ledger_id):
    """获取用户历史分类规则"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT je.account_code, je.account_name, je.summary, COUNT(*) as freq
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND v.status = 'posted'
        GROUP BY je.account_code, je.summary
        HAVING freq >= 2
        ORDER BY freq DESC LIMIT 50
    """, (ledger_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def parse_bank_csv(file_content, encoding="utf-8"):
    """解析银行流水 CSV 文件，支持常见银行格式"""
    import csv, io
    text = file_content.decode(encoding) if isinstance(file_content, bytes) else file_content
    lines = text.strip().split("\n")
    if not lines:
        return []
    delimiter = "\t" if "\t" in lines[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
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


def save_classified_transactions(ledger_id, transactions):
    """将分类后的交易保存为草稿凭证，返回凭证号列表"""
    from datetime import date
    voucher_nos = []
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
            vn = create_voucher(ledger_id, date_str, f"银行流水导入-{summary}", entries, status="draft")
            voucher_nos.append(vn)
        except Exception:
            pass
    return voucher_nos


# ── P2-3: 发票管理 ──

def get_invoices(ledger_id: int, invoice_type: str = None, status: str = None) -> list:
    """获取发票列表"""
    conn = get_conn()
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
    conn.close()
    return [dict(r) for r in rows]


def add_invoice(ledger_id: int, invoice_type: str, invoice_no: str, **kwargs) -> int:
    """添加发票"""
    conn = get_conn()
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
    conn.close()
    return iid


def link_invoice_voucher(invoice_id: int, voucher_id: int, ledger_id: int):
    """关联发票与凭证"""
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO invoice_voucher (invoice_id, voucher_id, ledger_id) VALUES (?,?,?)",
        (invoice_id, voucher_id, ledger_id)
    )
    conn.commit()
    conn.close()
    clear_query_cache()


def get_invoice_vouchers(invoice_id: int) -> list:
    """获取发票关联的凭证"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT v.* FROM vouchers v "
        "JOIN invoice_voucher iv ON v.id = iv.voucher_id "
        "WHERE iv.invoice_id = ? ORDER BY v.date DESC",
        (invoice_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_invoice_summary(ledger_id: int) -> dict:
    """获取发票汇总统计"""
    conn = get_conn()
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
    conn.close()
    return {
        "input_count": input_count["cnt"],
        "input_total": input_count["total"],
        "output_count": output_count["cnt"],
        "output_total": output_count["total"],
        "unverified_count": unverified,
    }


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


# ── 数据库初始化 ──

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # 账套表
    c.execute("""
        CREATE TABLE IF NOT EXISTS ledgers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT DEFAULT '默认公司',
            currency TEXT DEFAULT 'CNY',
            fiscal_year_start DATE,
            fiscal_year_end DATE,
            status TEXT DEFAULT 'active',
            settings TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 科目表
    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            sub_category TEXT,
            parent_code TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 凭证表
    c.execute("""
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            voucher_no TEXT UNIQUE NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            total_debit REAL DEFAULT 0,
            total_credit REAL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            attachment TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 凭证明细
    c.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            voucher_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            account_name TEXT NOT NULL,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            summary TEXT,
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE CASCADE,
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 期初余额
    c.execute("""
        CREATE TABLE IF NOT EXISTS opening_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            balance REAL DEFAULT 0,
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(ledger_id, account_code, year, month)
        )
    """)

    # 文档表
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT,
            file_size INTEGER,
            file_path TEXT,
            processing_status TEXT DEFAULT 'pending',
            ocr_text TEXT,
            extracted_data TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 审计日志
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            voucher_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 用户表
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            ledger_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE SET NULL
        )
    """)

    # 汇率表（Phase 10 升级：添加 source 字段）
    c.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            date TEXT NOT NULL,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(from_currency, to_currency, date)
        )
    """)

    # 汇率表添加 source 字段（兼容旧表）
    try:
        c.execute("ALTER TABLE exchange_rates ADD COLUMN source TEXT DEFAULT 'manual'")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE exchange_rates ADD COLUMN created_at TEXT DEFAULT (datetime('now','localtime'))")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE exchange_rates ADD COLUMN updated_at TEXT DEFAULT (datetime('now','localtime'))")
    except Exception:
        pass

    # 币种表（Phase 10 新增）
    c.execute("""
        CREATE TABLE IF NOT EXISTS currencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            symbol TEXT DEFAULT '',
            is_base INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 凭证表添加币种字段（兼容旧表）
    try:
        c.execute("ALTER TABLE vouchers ADD COLUMN currency TEXT DEFAULT 'CNY'")
    except Exception:
        pass

    # 凭证明细添加外币字段（兼容旧表）
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN foreign_currency TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN foreign_amount REAL DEFAULT 0")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN exchange_rate REAL DEFAULT 1")
    except Exception:
        pass

    # AI 复合业务规则表 (Phase 7)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_rules_complex (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pattern TEXT NOT NULL,
            description TEXT,
            entries_json TEXT NOT NULL,
            priority INTEGER DEFAULT 50,
            is_active INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # 索引
    c.execute("CREATE INDEX IF NOT EXISTS idx_er_from_to ON exchange_rates(from_currency, to_currency)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_rules_complex_pattern ON ai_rules_complex(pattern)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_rules_complex_priority ON ai_rules_complex(priority)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_currency_code ON currencies(code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_currency_active ON currencies(is_active)")

    # 初始化默认币种数据
    _init_default_currencies(c)

    # 初始化默认汇率数据
    _init_default_exchange_rates(c)

    # 创建默认管理员账户
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                  ("admin", "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9", "admin"))

    # 索引
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_ledger ON vouchers(ledger_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_date ON vouchers(date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_status ON vouchers(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_ledger ON journal_entries(ledger_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_voucher ON journal_entries(voucher_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_account ON journal_entries(account_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ob_ledger ON opening_balances(ledger_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_ledger ON audit_logs(ledger_id)")

    # 复合索引（Week 1 优化）
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_ledger_account ON journal_entries(ledger_id, account_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_je_ledger_voucher ON journal_entries(ledger_id, voucher_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_ledger_date ON vouchers(ledger_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_voucher_ledger_status ON vouchers(ledger_id, status)")

    # 初始化标准科目
    _init_chart_of_accounts(c)

    # 初始化复合业务规则 (Phase 7)
    _init_complex_rules(c)

    # 创建默认账套
    c.execute("SELECT COUNT(*) FROM ledgers")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO ledgers (name, company, currency, fiscal_year_start, fiscal_year_end) VALUES (?,?,?,?,?)",
            ("默认账套", "我的公司", "CNY", f"{datetime.now().year}-01-01", f"{datetime.now().year}-12-31")
        )
        default_lid = c.lastrowid
        # 初始化默认现金流分类
        _init_default_cash_flow_categories(c, default_lid)

    # ── P2-1: 审核流程数据库迁移 ──

    # audit_logs 添加 user_id 字段（记录谁操作的）
    try:
        c.execute("ALTER TABLE audit_logs ADD COLUMN user_id INTEGER")
    except Exception:
        pass

    # audit_logs 补齐会计组方案缺失字段 (2026-04-29)
    for _col in ["operator_name TEXT", "module TEXT", "target_table TEXT",
                 "target_id INTEGER", "old_value TEXT", "new_value TEXT",
                 "ip_address TEXT", "remark TEXT"]:
        try:
            c.execute(f"ALTER TABLE audit_logs ADD COLUMN {_col}")
        except Exception:
            pass

    # 凭证审核工作流表
    c.execute("""
        CREATE TABLE IF NOT EXISTS voucher_workflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id INTEGER NOT NULL,
            ledger_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            user_id INTEGER,
            comment TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE CASCADE,
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # ── P2-3: 发票管理数据库迁移 ──

    # 发票信息表
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            invoice_type TEXT NOT NULL DEFAULT 'input',
            invoice_code TEXT,
            invoice_no TEXT NOT NULL,
            invoice_date TEXT,
            seller_name TEXT,
            seller_tax_no TEXT,
            buyer_name TEXT,
            buyer_tax_no TEXT,
            total_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            total_with_tax REAL DEFAULT 0,
            status TEXT DEFAULT 'unverified',
            ocr_data TEXT,
            file_path TEXT,
            remark TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 发票-凭证关联表
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoice_voucher (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            voucher_id INTEGER NOT NULL,
            ledger_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE CASCADE,
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(invoice_id, voucher_id)
        )
    """)

    # ── P2-7: 定时自动凭证数据库迁移 ──

    # 凭证模板表
    c.execute("""
        CREATE TABLE IF NOT EXISTS voucher_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            voucher_type TEXT DEFAULT '记',
            entries TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 定时凭证任务表
    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            template_id INTEGER,
            name TEXT NOT NULL,
            cron_expression TEXT NOT NULL,
            next_run_at TEXT,
            last_run_at TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            FOREIGN KEY (template_id) REFERENCES voucher_templates(id) ON DELETE SET NULL
        )
    """)

    # ── P2-4: 预算管理数据库迁移 ──

    # 预算表
    c.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            account_name TEXT NOT NULL,
            budget_year INTEGER NOT NULL,
            budget_month INTEGER,
            budget_amount REAL NOT NULL DEFAULT 0,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    # 预算执行记录表
    c.execute("""
        CREATE TABLE IF NOT EXISTS budget_execution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            budget_id INTEGER,
            account_code TEXT NOT NULL,
            budget_year INTEGER NOT NULL,
            budget_month INTEGER NOT NULL,
            actual_amount REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE SET NULL
        )
    """)

    # ── P2-5: 现金流量表数据库迁移 ──

    # journal_entries 添加现金流分类字段
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN cash_flow_type TEXT DEFAULT ''")
    except Exception:
        pass

    # 现金流分类表
    c.execute("""
        CREATE TABLE IF NOT EXISTS cash_flow_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            parent_code TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(ledger_id, code)
        )
    """)

    # ── P2-2: 增值税管理数据库迁移 ──

    # journal_entries 添加税务字段
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN tax_type TEXT DEFAULT ''")  # input/output/none
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN tax_rate REAL DEFAULT 0")   # 税率 0.13/0.09/0.06等
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN tax_amount REAL DEFAULT 0")  # 税额
    except Exception:
        pass

    # 增值税配置表
    c.execute("""
        CREATE TABLE IF NOT EXISTS tax_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            taxpayer_type TEXT DEFAULT 'general',
            default_tax_rate REAL DEFAULT 0.13,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(ledger_id)
        )
    """)

    # 税率表（预设常用税率）
    c.execute("""
        CREATE TABLE IF NOT EXISTS tax_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            rate REAL NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()
    clear_query_cache()


def _init_chart_of_accounts(c):
    c.execute("SELECT COUNT(*) FROM accounts")
    if c.fetchone()[0] > 0:
        return
    accounts = [
        ("1001","库存现金","资产","流动资产"),("1002","银行存款","资产","流动资产"),
        ("100201","银行存款-基本户","资产","流动资产","1002"),("100202","银行存款-一般户","资产","流动资产","1002"),
        ("1012","其他货币资金","资产","流动资产"),("1101","交易性金融资产","资产","流动资产"),
        ("1121","应收票据","资产","流动资产"),("1122","应收账款","资产","流动资产"),
        ("1123","预付账款","资产","流动资产"),("1221","其他应收款","资产","流动资产"),
        ("1401","材料采购","资产","流动资产"),("1403","原材料","资产","流动资产"),
        ("1405","库存商品","资产","流动资产"),("1601","固定资产","资产","非流动资产"),
        ("1602","累计折旧","资产","非流动资产"),("1604","在建工程","资产","非流动资产"),
        ("1701","无形资产","资产","非流动资产"),("1702","累计摊销","资产","非流动资产"),
        ("1801","长期待摊费用","资产","非流动资产"),("1901","待处理财产损溢","资产","流动资产"),
        ("2001","短期借款","负债","流动负债"),("2201","应付票据","负债","流动负债"),
        ("2202","应付账款","负债","流动负债"),("2203","预收账款","负债","流动负债"),
        ("2211","应付职工薪酬","负债","流动负债"),("2221","应交税费","负债","流动负债"),
        ("222101","应交增值税","负债","流动负债","2221"),("222102","应交所得税","负债","流动负债","2221"),
        ("222103","应交城建税","负债","流动负债","2221"),("2231","应付利息","负债","流动负债"),
        ("2232","应付股利","负债","流动负债"),("2241","其他应付款","负债","流动负债"),
        ("2501","长期借款","负债","非流动负债"),("2701","长期应付款","负债","非流动负债"),
        ("4001","实收资本","权益","所有者权益"),("4002","资本公积","权益","所有者权益"),
        ("4101","盈余公积","权益","所有者权益"),("4103","本年利润","权益","所有者权益"),
        ("4104","利润分配","权益","所有者权益"),
        ("6001","主营业务收入","收入","营业收入"),("6051","其他业务收入","收入","营业收入"),
        ("6111","投资收益","收入","营业外收入"),("6301","营业外收入","收入","营业外收入"),
        ("6401","主营业务成本","费用","营业成本"),("6402","其他业务成本","费用","营业成本"),
        ("6403","税金及附加","费用","营业成本"),("6601","销售费用","费用","期间费用"),
        ("6602","管理费用","费用","期间费用"),("6603","财务费用","费用","期间费用"),
        ("6701","资产减值损失","费用","期间费用"),("6711","营业外支出","费用","营业外支出"),
        ("6801","所得税费用","费用","期间费用"),
        ("5101","生产成本","费用","营业成本"),
    ]
    for acc in accounts:
        code, name, cat, sub = acc[0], acc[1], acc[2], acc[3]
        parent = acc[4] if len(acc) > 4 else None
        c.execute("INSERT OR IGNORE INTO accounts (code,name,category,sub_category,parent_code) VALUES (?,?,?,?,?)",
                  (code, name, cat, sub, parent))


def _init_default_currencies(c):
    """Phase 10: 初始化默认币种数据"""
    c.execute("SELECT COUNT(*) FROM currencies")
    if c.fetchone()[0] > 0:
        return
    default_currencies = [
        ("CNY", "人民币", "¥", 1),
        ("USD", "美元", "$", 0),
        ("EUR", "欧元", "€", 0),
        ("JPY", "日元", "¥", 0),
        ("GBP", "英镑", "£", 0),
        ("HKD", "港币", "HK$", 0),
        ("AUD", "澳元", "A$", 0),
        ("CAD", "加元", "C$", 0),
        ("SGD", "新加坡元", "S$", 0),
        ("KRW", "韩元", "₩", 0),
        ("CHF", "瑞士法郎", "Fr", 0),
        ("TWD", "新台币", "NT$", 0),
    ]
    for code, name, symbol, is_base in default_currencies:
        c.execute("INSERT OR IGNORE INTO currencies (code, name, symbol, is_base) VALUES (?, ?, ?, ?)",
                  (code, name, symbol, is_base))


def _init_default_exchange_rates(c):
    """Phase 10: 初始化默认汇率数据（以CNY为基准）"""
    c.execute("SELECT COUNT(*) FROM exchange_rates")
    if c.fetchone()[0] > 0:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    default_rates = [
        ("USD", "CNY", 7.2456),
        ("EUR", "CNY", 7.8456),
        ("JPY", "CNY", 0.0485),
        ("GBP", "CNY", 9.1823),
        ("HKD", "CNY", 0.9275),
        ("AUD", "CNY", 4.7234),
        ("CAD", "CNY", 5.3123),
        ("SGD", "CNY", 5.3567),
        ("KRW", "CNY", 0.0054),
        ("CHF", "CNY", 8.1234),
        ("TWD", "CNY", 0.2234),
    ]
    for from_c, to_c, rate in default_rates:
        c.execute("INSERT OR IGNORE INTO exchange_rates (from_currency, to_currency, rate, date, source) VALUES (?, ?, ?, ?, 'system')",
                  (from_c, to_c, rate, today))


# ===== 多期间对比分析 =====
def get_period_compare_income(ledger_id: int, periods: list) -> dict:
    """多期间利润对比
    periods: [(year, month), ...]
    返回: {periods: [...], items: [{name, code, values: [amount, ...], changes: [%...]}]}
    """
    results = []
    for year, month in periods:
        inc = get_income_statement(ledger_id, year, month)
        # 从 rows 中提取收入/费用项（level > 0 的明细项）
        rev_dict = {}
        exp_dict = {}
        for r in inc["rows"]:
            if r["type"] in ("revenue_item",):
                rev_dict[r["code"]] = r["month"]
            elif r["type"] in ("expense_item",):
                exp_dict[r["code"]] = r["month"]
        results.append({
            "year": year, "month": month,
            "label": f"{year}-{month:02d}",
            "revenues": rev_dict,
            "expenses": exp_dict,
            "total_revenue": inc["total_revenue"],
            "total_expense": inc.get("total_expense", inc.get("total_revenue", 0) - inc.get("net_profit", 0)),
            "net_profit": inc["net_profit"],
        })

    all_rev_codes = set()
    all_exp_codes = set()
    for r in results:
        all_rev_codes.update(r["revenues"].keys())
        all_exp_codes.update(r["expenses"].keys())

    conn = get_conn()
    code_names = {}
    for code in all_rev_codes | all_exp_codes:
        row = conn.execute("SELECT name FROM accounts WHERE code=?", (code,)).fetchone()
        code_names[code] = row["name"] if row else code
    conn.close()

    items = []
    for code in sorted(all_rev_codes):
        values = [r["revenues"].get(code, 0) for r in results]
        changes = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                changes.append((values[i] - values[i-1]) / values[i-1] * 100)
            else:
                changes.append(None)
        items.append({"code": code, "name": code_names[code], "type": "revenue",
                       "values": values, "changes": changes})
    for code in sorted(all_exp_codes):
        values = [r["expenses"].get(code, 0) for r in results]
        changes = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                changes.append((values[i] - values[i-1]) / values[i-1] * 100)
            else:
                changes.append(None)
        items.append({"code": code, "name": code_names[code], "type": "expense",
                       "values": values, "changes": changes})

    return {
        "periods": [r["label"] for r in results],
        "items": items,
        "summary": {
            "total_revenue": [r["total_revenue"] for r in results],
            "total_expense": [r["total_expense"] for r in results],
            "net_profit": [r["net_profit"] for r in results],
        }
    }

def get_period_compare_balance(ledger_id: int, periods: list) -> dict:
    """多期间资产负债对比 — 适配新资产负债表格式"""
    results = []
    for year, month in periods:
        bs = get_balance_sheet(ledger_id, year, month)
        asset_items = {r["code"]: r["end"] for r in bs["assets"] if r["code"] and r["code"] not in ("1003", "1601N")}
        liab_items = {r["code"]: r["end"] for r in bs["liabilities"] if r["code"]}
        eq_items = {r["code"]: r["end"] for r in bs["equity"] if r["code"]}
        results.append({
            "year": year, "month": month,
            "label": f"{year}-{month:02d}",
            "assets": bs["total_assets"],
            "liabilities": bs["total_liab"],
            "equity": bs["total_equity"],
            "asset_items": asset_items,
            "liab_items": liab_items,
            "equity_items": eq_items,
        })

    all_codes = set()
    for r in results:
        all_codes.update(r["asset_items"].keys())
        all_codes.update(r["liab_items"].keys())
        all_codes.update(r["equity_items"].keys())

    conn = get_conn()
    code_names = {}
    for code in all_codes:
        row = conn.execute("SELECT name, category FROM accounts WHERE code=?", (code,)).fetchone()
        if row:
            code_names[code] = {"name": row["name"], "category": row["category"]}
        else:
            code_names[code] = {"name": code, "category": "unknown"}
    conn.close()

    items = []
    for code in sorted(all_codes):
        values = []
        for r in results:
            v = r["asset_items"].get(code, 0) + r["liab_items"].get(code, 0) + r["equity_items"].get(code, 0)
            values.append(v)
        changes = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                changes.append((values[i] - values[i-1]) / values[i-1] * 100)
            else:
                changes.append(None)
        items.append({"code": code, "name": code_names[code]["name"],
                       "category": code_names[code]["category"],
                       "values": values, "changes": changes})

    return {
        "periods": [r["label"] for r in results],
        "items": items,
        "summary": {
            "assets": [r["assets"] for r in results],
            "liabilities": [r["liabilities"] for r in results],
            "equity": [r["equity"] for r in results],
        }
    }


def _flatten_bs(section):
    """将资产负债结构扁平化为条目列表"""
    result = []
    for sub_cat, items in section.items():
        if sub_cat == "total" or not items:
            continue
        result.extend(items)
    return result


# ===== Excel 批量导入 =====
def import_vouchers_from_excel(ledger_id: int, file_path: str) -> dict:
    """从 Excel 文件批量导入凭证
    期望列：日期 | 摘要 | 科目代码 | 科目名称 | 借方金额 | 贷方金额
    返回: {"total": N, "imported": N, "errors": [str], "voucher_nos": [str]}
    """
    import openpyxl
    from datetime import datetime

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    result = {"total": 0, "imported": 0, "errors": [], "voucher_nos": []}
    current_voucher = None  # {"date": ..., "desc": ..., "entries": [...]}

    rows = list(ws.iter_rows(min_row=2, values_only=True))  # 跳过表头

    def _flush_voucher():
        nonlocal current_voucher, result
        if not current_voucher:
            return
        entries = current_voucher["entries"]
        if not entries:
            result["errors"].append(f"凭证 {current_voucher['date']} {current_voucher['desc']} 无分录")
            return
        total_dr = sum(e["debit"] for e in entries)
        total_cr = sum(e["credit"] for e in entries)
        if abs(total_dr - total_cr) > 0.01:
            result["errors"].append(
                f"凭证 {current_voucher['date']} {current_voucher['desc']} 借贷不平(借{total_dr:.2f} 贷{total_cr:.2f})")
            return
        try:
            vn = create_voucher(ledger_id, current_voucher["date"],
                                current_voucher["desc"], entries, status="draft")
            result["imported"] += 1
            result["voucher_nos"].append(vn)
        except ValueError as e:
            result["errors"].append(f"凭证 {current_voucher['date']} {current_voucher['desc']}: {e}")

    for row in rows:
        if all(v is None for v in row):
            continue
        result["total"] += 1

        date_val = row[0]
        desc = str(row[1]).strip() if row[1] else ""
        code = str(row[2]).strip() if row[2] else ""
        name = str(row[3]).strip() if row[3] else ""
        debit = float(row[4]) if row[4] else 0
        credit = float(row[5]) if row[5] else 0

        # 日期解析
        if isinstance(date_val, datetime):
            date_str = date_val.strftime("%Y-%m-%d")
        elif isinstance(date_val, str):
            date_str = date_val.strip()
        else:
            date_str = str(date_val)

        # 新凭证：以日期+摘要变化为分界
        if current_voucher is None or date_str != current_voucher["date"] or desc != current_voucher["desc"]:
            _flush_voucher()
            current_voucher = {"date": date_str, "desc": desc, "entries": []}

        if code:
            current_voucher["entries"].append({
                "account_code": code,
                "account_name": name,
                "debit": debit,
                "credit": credit,
                "summary": "",
            })

    _flush_voucher()  # 最后一张
    return result



# ===== 汇率管理 =====

def generate_composite_voucher(ledger_id: int, text: str) -> dict:
    """
    复合业务AI凭证生成 — 支持多借多贷、一句话描述复杂业务
    返回 {"description": str, "entries": [...], "confidence": float, "composite": bool}
    """
    import re
    text = str(text).strip()

    def _extract_all_amounts(t):
        amounts = []
        for m in re.finditer(r'(\d+\.?\d*)\s*[万wW]', t):
            amounts.append(float(m.group(1)) * 10000)
        if not amounts:
            for m in re.finditer(r'(\d[\d,]*(?:\.\d+)?)', t.replace(',', '')):
                amounts.append(float(m.group(1)))
        return amounts

    def _get_account(code):
        conn = get_conn()
        row = conn.execute("SELECT name FROM accounts WHERE code = ?", (code,)).fetchone()
        conn.close()
        return row["name"] if row else code

    def _make_entry(code, debit=0, credit=0, summary=""):
        return {"account_code": code, "account_name": _get_account(code),
                "debit": round(debit, 2), "credit": round(credit, 2), "summary": summary}

    def _parse_mixed_purchase(t, amounts):
        if len(amounts) >= 2:
            total, cash = amounts[0], amounts[1]
            credit_amt = round(total - cash, 2)
            return ("购入固定资产（部分赊购）", [
                _make_entry("1601", debit=total, summary="购入固定资产"),
                _make_entry("1002", credit=cash, summary="银行存款支付"),
                _make_entry("2202", credit=credit_amt, summary="余款赊购（应付账款）"),
            ])
        return None

    def _parse_mixed_sale(t, amounts):
        if len(amounts) >= 2:
            total, cash = amounts[0], amounts[1]
            credit_amt = round(total - cash, 2)
            return ("销售商品（部分赊销）", [
                _make_entry("1002", debit=cash, summary="银行存款收现"),
                _make_entry("1122", debit=credit_amt, summary="余款赊销（应收账款）"),
                _make_entry("6001", credit=total, summary="主营业务收入"),
            ])
        return None

    def _parse_reimbursement(t, amounts):
        if len(amounts) >= 2:
            total, cash = amounts[0], amounts[1]
            other = round(total - cash, 2)
            return ("报销差旅费（部分冲借款）", [
                _make_entry("6602", debit=total, summary="差旅费报销"),
                _make_entry("1001", credit=cash, summary="现金支付"),
                _make_entry("1221", credit=other, summary="冲抵其他应收款"),
            ])
        return None

    def _parse_purchase_with_tax(t, amounts):
        if len(amounts) >= 2:
            material, tax = amounts[0], amounts[1]
            total = round(material + tax, 2)
            return ("采购原材料（含增值税）", [
                _make_entry("1403", debit=material, summary="原材料采购"),
                _make_entry("222101", debit=tax, summary="进项增值税"),
                _make_entry("1002", credit=total, summary="银行存款支付"),
            ])
        return None

    def _parse_multi_dept_salary(t, amounts):
        if len(amounts) >= 3:
            a, b, c = amounts[0], amounts[1], amounts[2]
            total = round(a + b + c, 2)
            return ("计提职工薪酬（多部门）", [
                _make_entry("5101", debit=a, summary="生产工人工资"),
                _make_entry("6602", debit=b, summary="管理人员工资"),
                _make_entry("6601", debit=c, summary="销售人员工资"),
                _make_entry("2211", credit=total, summary="应付职工薪酬"),
            ])
        return None

    composite_rules = [
        (r'(?:购入|购买|采购|购)(?:设备|固定资产|机器).*(?:其中|部分).*(?:余款|剩余|赊购|欠款|应付)', _parse_mixed_purchase),
        (r'(?:销售|卖出|出售).*(?:商品|货物|产品).*(?:其中|部分).*(?:收现|现金|余款赊销|挂账)', _parse_mixed_sale),
        (r'(?:报销|差旅费).*(?:现金|库存现金).*(?:冲抵|冲借款|其他应收|剩余)', _parse_reimbursement),
        (r'(?:购入|采购|购买).*(?:原材料|材料).*(?:增值税|进项).*(?:全部|银行)', _parse_purchase_with_tax),
        (r'(?:计提|分配).*(?:工资|薪酬).*(?:生产|工人|管理|销售)', _parse_multi_dept_salary),
    ]

    for pattern, handler in composite_rules:
        if re.search(pattern, text):
            amounts = _extract_all_amounts(text)
            if amounts:
                result = handler(text, amounts)
                if result:
                    desc, entries = result
                    total_dr = sum(e["debit"] for e in entries)
                    total_cr = sum(e["credit"] for e in entries)
                    if abs(total_dr - total_cr) < 0.02:
                        return {"description": desc, "entries": entries,
                                "confidence": 0.88, "composite": True}

    return {"description": text, "entries": [], "confidence": 0.0, "composite": False}


def set_exchange_rate(from_currency: str, to_currency: str, rate: float, date: str = None):
    """设置汇率"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO exchange_rates (from_currency, to_currency, rate, date)
        VALUES (?,?,?,?)
    """, (from_currency.upper(), to_currency.upper(), rate, date))
    conn.commit()
    conn.close()
    clear_query_cache()


def get_exchange_rate(from_currency: str, to_currency: str, date: str = None) -> float:
    """获取汇率，如果没有则返回1"""
    if from_currency.upper() == to_currency.upper():
        return 1.0
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    row = conn.execute("""
        SELECT rate FROM exchange_rates
        WHERE from_currency = ? AND to_currency = ?
          AND date <= ?
        ORDER BY date DESC LIMIT 1
    """, (from_currency.upper(), to_currency.upper(), date)).fetchone()
    conn.close()
    return row["rate"] if row else 1.0


def convert_currency(amount: float, from_currency: str, to_currency: str, date: str = None) -> float:
    """货币转换"""
    rate = get_exchange_rate(from_currency, to_currency, date)
    return round(amount * rate, 2)


# ===== 数据备份与恢复 =====

def backup_ledger_to_json(ledger_id: int, backup_dir: str) -> str:
    """将指定账套数据备份为JSON文件，返回文件路径"""
    import json
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"backup_ledger{ledger_id}_{ts}.json"
    fpath = os.path.join(backup_dir, fname)

    conn = get_conn()
    ledger = conn.execute("SELECT * FROM ledgers WHERE id = ?", (ledger_id,)).fetchone()
    if not ledger:
        conn.close()
        raise ValueError("账套不存在")

    vouchers = conn.execute("SELECT * FROM vouchers WHERE ledger_id = ?", (ledger_id,)).fetchall()
    entries = conn.execute("SELECT * FROM journal_entries WHERE ledger_id = ?", (ledger_id,)).fetchall()
    openings = conn.execute("SELECT * FROM opening_balances WHERE ledger_id = ?", (ledger_id,)).fetchall()
    audits = conn.execute("SELECT * FROM audit_logs WHERE ledger_id = ?", (ledger_id,)).fetchall()
    conn.close()

    data = {
        "version": "2.0",
        "type": "ledger_backup",
        "created_at": datetime.now().isoformat(),
        "ledger": dict(ledger),
        "vouchers": [dict(v) for v in vouchers],
        "journal_entries": [dict(e) for e in entries],
        "opening_balances": [dict(o) for o in openings],
        "audit_logs": [dict(a) for a in audits],
    }

    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fpath



def backup_database(ledger_id: int, backup_dir: str) -> str:
    """按账套备份数据为JSON文件，返回文件路径"""
    import json
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ledger = get_ledger(ledger_id)
    if not ledger:
        raise ValueError("账套不存在")

    conn = get_conn()
    vouchers = conn.execute("SELECT * FROM vouchers WHERE ledger_id = ?", (ledger_id,)).fetchall()
    entries = conn.execute("SELECT * FROM journal_entries WHERE ledger_id = ?", (ledger_id,)).fetchall()
    ob = conn.execute("SELECT * FROM opening_balances WHERE ledger_id = ?", (ledger_id,)).fetchall()
    audit = conn.execute("SELECT * FROM audit_logs WHERE ledger_id = ?", (ledger_id,)).fetchall()
    conn.close()

    data = {
        "version": "2.0",
        "backup_time": datetime.now().isoformat(),
        "ledger": dict(ledger),
        "vouchers": [dict(v) for v in vouchers],
        "journal_entries": [dict(e) for e in entries],
        "opening_balances": [dict(o) for o in ob],
        "audit_logs": [dict(a) for a in audit],
    }

    fname = "backup_ledger{}_{}.json".format(ledger_id, ts)
    fpath = os.path.join(backup_dir, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fpath


def restore_database(backup_dir: str, target_ledger_id: int = None) -> dict:
    """从JSON备份恢复账套数据
    如果 target_ledger_id 为 None，创建新账套
    如果指定 target_ledger_id，恢复到已有账套（追加模式，跳过已存在凭证）
    返回: {"ledger_id": int, "vouchers_restored": int, "skipped": int}
    """
    import json
    # Find the backup file
    files = [f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.json')]
    if not files:
        raise ValueError("备份目录中没有找到备份文件")
    files.sort(reverse=True)
    fpath = os.path.join(backup_dir, files[0])

    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    vouchers = data.get("vouchers", [])
    entries = data.get("journal_entries", [])
    ob_records = data.get("opening_balances", [])

    if target_ledger_id is None:
        # Create new ledger
        ledger_info = data.get("ledger", {})
        new_id = create_ledger(
            name=ledger_info.get("name", "恢复账套") + "_恢复",
            company=ledger_info.get("company", "未知公司"),
            currency=ledger_info.get("currency", "CNY"),
        )
        target_ledger_id = new_id

    # Restore opening balances
    for ob in ob_records:
        try:
            set_opening_balance(target_ledger_id, ob["account_code"], ob["year"], ob["month"], ob["balance"])
        except Exception:
            pass

    # Restore vouchers (skip existing voucher_no)
    restored = 0
    skipped = 0
    conn = get_conn()
    for v in vouchers:
        existing = conn.execute("SELECT id FROM vouchers WHERE voucher_no = ?", (v["voucher_no"],)).fetchone()
        if existing:
            skipped += 1
            continue
        v_entries = [e for e in entries if e.get("voucher_id") == v["id"]]
        try:
            create_voucher(
                target_ledger_id,
                v["date"],
                v["description"],
                [{"account_code": e["account_code"], "account_name": e["account_name"],
                  "debit": e["debit"], "credit": e["credit"], "summary": e.get("summary", "")}
                 for e in v_entries],
                status=v.get("status", "posted")
            )
            restored += 1
        except Exception:
            skipped += 1
    conn.close()

    return {"ledger_id": target_ledger_id, "vouchers_restored": restored, "skipped": skipped}


def backup_full_database(backup_dir: str) -> str:
    """完整数据库备份（直接复制SQLite文件），返回文件路径"""
    import shutil
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"full_backup_{ts}.db"
    fpath = os.path.join(backup_dir, fname)
    shutil.copy2(DB_PATH, fpath)
    return fpath


def restore_ledger_from_json(fpath: str, target_ledger_id: int = None, user_id: int = None, operator_name: str = None) -> int:
    """从JSON备份恢复账套，返回账套ID"""
    import json
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = get_conn()
    try:
        # 创建或获取账套
        if target_ledger_id is None:
            # 创建新账套
            ledger_name = data["ledger"]["name"] + " (恢复)"
            cur = conn.execute(
                "INSERT INTO ledgers (name, company, currency, fiscal_year_start, fiscal_year_end, status) VALUES (?,?,?,?,?,'active')",
                (ledger_name, data["ledger"].get("company", "未知"), data["ledger"].get("currency", "CNY"),
                 data["ledger"].get("fiscal_year_start", f"{datetime.now().year}-01-01"),
                 data["ledger"].get("fiscal_year_end", f"{datetime.now().year}-12-31"))
            )
            new_ledger_id = cur.lastrowid
        else:
            new_ledger_id = target_ledger_id

        # 恢复期初余额
        for ob in data.get("opening_balances", []):
            conn.execute("""
                INSERT OR IGNORE INTO opening_balances (ledger_id, account_code, year, month, balance)
                VALUES (?,?,?,?,?)
            """, (new_ledger_id, ob["account_code"], ob["year"], ob["month"], ob["balance"]))

        # 恢复凭证（跳过已存在的凭证号）
        existing_nos = set(r["voucher_no"] for r in conn.execute(
            "SELECT voucher_no FROM vouchers WHERE ledger_id = ?", (new_ledger_id,)).fetchall())

        for v in data.get("vouchers", []):
            if v["voucher_no"] in existing_nos:
                continue
            conn.execute("""
                INSERT INTO vouchers (ledger_id, voucher_no, date, description, total_debit, total_credit, status, currency, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (new_ledger_id, v["voucher_no"], v["date"], v.get("description", ""),
                  v.get("total_debit", 0), v.get("total_credit", 0), v.get("status", "posted"),
                  v.get("currency", "CNY"), v.get("created_at", datetime.now().isoformat()),
                  v.get("updated_at", datetime.now().isoformat())))

            # 获取新插入的凭证ID
            new_vid = conn.execute("SELECT id FROM vouchers WHERE voucher_no = ?", (v["voucher_no"],)).fetchone()["id"]
            old_vid = v["id"]

            # 恢复该凭证的明细
            for je in data.get("journal_entries", []):
                if je.get("voucher_id") == old_vid or je.get("voucher_id") == v["id"]:
                    conn.execute("""
                        INSERT INTO journal_entries (ledger_id, voucher_id, account_code, account_name, debit, credit, summary, foreign_currency, foreign_amount, exchange_rate)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (new_ledger_id, new_vid, je["account_code"], je["account_name"],
                          je.get("debit", 0), je.get("credit", 0), je.get("summary", ""),
                          je.get("foreign_currency", ""), je.get("foreign_amount", 0), je.get("exchange_rate", 1)))

        # 审计日志
        add_audit_log(
            ledger_id=new_ledger_id,
            action="restore",
            detail=f"从备份文件 {os.path.basename(fpath)} 恢复",
            module="system",
            target_table="ledgers",
            user_id=user_id,
            operator_name=operator_name,
            remark=f"备份文件:{os.path.basename(fpath)}",
        )

        conn.commit()
        return new_ledger_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ===== PDF 报表导出 =====

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



# ── Phase 7: 复合业务规则管理 ──

def get_ai_rules_complex(active_only=True) -> list:
    """获取所有复合业务规则"""
    conn = get_conn()
    sql = "SELECT * FROM ai_rules_complex"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY priority DESC, id"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_ai_rules_complex(name, pattern, description, entries_json, priority=50):
    """添加复合业务规则"""
    import json
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO ai_rules_complex (name, pattern, description, entries_json, priority)
            VALUES (?,?,?,?,?)
        """, (name, pattern, description, json.dumps(entries_json, ensure_ascii=False), priority))
        conn.commit()
    finally:
        conn.close()


def delete_ai_rules_complex(rule_id):
    """删除复合业务规则"""
    conn = get_conn()
    conn.execute("DELETE FROM ai_rules_complex WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    clear_query_cache()


def toggle_ai_rules_complex(rule_id):
    """启用/禁用复合业务规则"""
    conn = get_conn()
    conn.execute("UPDATE ai_rules_complex SET is_active = 1 - is_active, updated_at = datetime('now','localtime') WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    clear_query_cache()


def _init_complex_rules(c):
    """初始化内置复合业务规则到 ai_rules_complex 表"""
    import json as _json
    c.execute("SELECT COUNT(*) FROM ai_rules_complex")
    if c.fetchone()[0] > 0:
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
        c.execute("""
            INSERT INTO ai_rules_complex (name, pattern, description, entries_json, priority)
            VALUES (?,?,?,?,?)
        """, (rule["name"], rule["pattern"], rule["description"],
              _json.dumps(entries, ensure_ascii=False), rule["priority"]))
    # print(f"  OK: Initialized {len(builtin_rules)} builtin complex rules")


def parse_complex_voucher(ledger_id: int, text: str) -> dict:
    """
    Phase 7: 高级复合业务解析入口
    结合: 正则匹配 + 关键词 + 上下文分析 + ai_rules_complex 表查询
    返回: {
        "description": str,
        "entries": [{"account_code", "account_name", "debit", "credit", "summary"}],
        "confidence": float,
        "composite": bool,
        "matched_rule": str | None,
        "analysis": dict  # 上下文分析详情
    }
    """
    import json, re as _re
    text = str(text).strip()

    def _extract_all_amounts(t):
        amounts = []
        for m in _re.finditer(r'(\d+\.?\d*)\s*[万wW]', t):
            amounts.append(float(m.group(1)) * 10000)
        if not amounts:
            for m in _re.finditer(r'(\d[\d,]*(?:\.\d+)?)', t.replace(',', '')):
                amounts.append(float(m.group(1)))
        return amounts

    def _get_account(code):
        conn = get_conn()
        row = conn.execute("SELECT name FROM accounts WHERE code = ?", (code,)).fetchone()
        conn.close()
        return row["name"] if row else code

    def _make_entry(code, debit=0, credit=0, summary=""):
        return {"account_code": code, "account_name": _get_account(code),
                "debit": round(debit, 2), "credit": round(credit, 2), "summary": summary}

    # ── 1. 上下文分析 ──
    analysis = {
        "detected_keywords": [],
        "detected_amounts": _extract_all_amounts(text),
        "detected_business_type": None,
        "context_score": 0.0,
    }

    # 关键词上下文映射
    context_keywords = {
        "采购": ["采购", "购入", "购买", "购货", "进货", "买"],
        "销售": ["销售", "卖出", "出售", "销货", "营收"],
        "费用": ["费用", "报销", "支出", "付款", "缴纳"],
        "薪酬": ["工资", "薪酬", "社保", "公积金", "奖金", "津贴"],
        "资产": ["设备", "机器", "固定资产", "在建工程", "无形资产"],
        "税费": ["增值税", "所得税", "城建税", "个税", "退税"],
        "融资": ["投资", "借款", "贷款", "注资", "股东"],
        "利润": ["利润", "分红", "股利", "分配"],
    }
    for biz_type, keywords in context_keywords.items():
        for kw in keywords:
            if kw in text:
                analysis["detected_keywords"].append(kw)
                if not analysis["detected_business_type"]:
                    analysis["detected_business_type"] = biz_type
                break

    amounts = analysis["detected_amounts"]
    amt_count = len(amounts)

    # ── 2. 内置复合规则匹配（高优先级）──
    # 规则: (pattern, handler_fn, confidence)
    def _rule_purchase_freight(t, amts):
        if len(amts) >= 2:
            mat, freight = amts[0], amts[1]
            total = round(mat + freight, 2)
            return ("采购材料含运费", [
                _make_entry("1403", debit=mat, summary="原材料采购"),
                _make_entry("6601", debit=freight, summary="运费"),
                _make_entry("1002", credit=total, summary="银行存款支付"),
            ])
        return None

    def _rule_sale_discount(t, amts):
        disc_match = _re.search(r'(\d+\.?\d*)%?\s*(折扣|折让|优惠)', t)
        if len(amts) >= 3:
            total, cash, disc = amts[0], amts[1], amts[2]
        elif len(amts) == 2:
            total, cash = amts[0], amts[1]
            disc = round(total - cash, 2)
        else:
            total = amts[0] if amts else 0
            rate = float(disc_match.group(1)) / 100 if disc_match and '%' in disc_match.group(0) else 0.05
            disc = round(total * rate, 2)
            cash = round(total - disc, 2)
        return ("销售商品含折扣", [
            _make_entry("1002", debit=cash, summary="实收金额"),
            _make_entry("6601", debit=disc, summary="销售折扣"),
            _make_entry("6001", credit=total, summary="主营业务收入"),
        ])

    def _rule_salary_tax(t, amts):
        if len(amts) >= 3:
            gross, tax, net = amts[0], amts[1], amts[2]
        elif len(amts) == 2:
            gross, tax = amts[0], amts[1]
            net = round(gross - tax, 2)
        else:
            gross = amts[0] if amts else 0
            tax = round(gross * 0.1, 2)
            net = round(gross - tax, 2)
        return ("发放工资代扣个税", [
            _make_entry("2211", debit=gross, summary="应付职工薪酬"),
            _make_entry("1002", credit=net, summary="实际发放"),
            _make_entry("222102", credit=tax, summary="代扣个税"),
        ])

    def _rule_social_insurance(t, amts):
        if len(amts) >= 2:
            co, per = amts[0], amts[1]
        else:
            total = amts[0] if amts else 0
            co = round(total * 0.7, 2)
            per = round(total * 0.3, 2)
        total = round(co + per, 2)
        return ("支付社会保险费", [
            _make_entry("6602", debit=co, summary="社保（公司部分）"),
            _make_entry("1221", debit=per, summary="社保（个人代扣）"),
            _make_entry("1002", credit=total, summary="银行存款支付"),
        ])

    def _rule_fixed_asset_disposal(t, amts):
        if len(amts) >= 3:
            orig, accum, proceeds = amts[0], amts[1], amts[2]
        elif len(amts) == 2:
            orig, accum = amts[0], amts[1]
            proceeds = round(orig - accum, 2)
        else:
            orig = amts[0] if amts else 0
            accum = round(orig * 0.6, 2)
            proceeds = round(orig - accum, 2)
        net = round(orig - accum, 2)
        return ("处置固定资产", [
            _make_entry("1602", debit=accum, summary="累计折旧"),
            _make_entry("1601", debit=net, summary="固定资产清理"),
            _make_entry("1601", credit=orig, summary="固定资产原值"),
            _make_entry("1002", debit=proceeds, summary="处置收入"),
        ])

    def _rule_cip_transfer(t, amts):
        amt = amts[0] if amts else 0
        return ("在建工程完工转固", [
            _make_entry("1601", debit=amt, summary="结转固定资产"),
            _make_entry("1604", credit=amt, summary="在建工程"),
        ])

    def _rule_export_rebate(t, amts):
        if len(amts) >= 2:
            rev, rebate = amts[0], amts[1]
        else:
            rev = amts[0] if amts else 0
            rebate = round(rev * 0.13, 2)
        return ("出口销售含退税", [
            _make_entry("1122", debit=rev, summary="应收账款"),
            _make_entry("6001", credit=rev, summary="主营业务收入"),
            _make_entry("1221", debit=rebate, summary="应收出口退税"),
            _make_entry("222101", credit=rebate, summary="应交增值税(出口退税)"),
        ])

    def _rule_prepay_purchase(t, amts):
        amt = amts[0] if amts else 0
        return ("预付采购货款", [
            _make_entry("1123", debit=amt, summary="预付账款"),
            _make_entry("1002", credit=amt, summary="银行存款支付"),
        ])

    def _rule_prepay_received(t, amts):
        amt = amts[0] if amts else 0
        return ("收到预收货款", [
            _make_entry("1002", debit=amt, summary="银行存款"),
            _make_entry("2203", credit=amt, summary="预收账款"),
        ])

    def _rule_profit_dist(t, amts):
        amt = amts[0] if amts else 0
        return ("利润分配-宣告股利", [
            _make_entry("4104", debit=amt, summary="利润分配"),
            _make_entry("2232", credit=amt, summary="应付股利"),
        ])

    def _rule_income_tax(t, amts):
        if len(amts) >= 2:
            profit, tax = amts[0], amts[1]
        else:
            profit = amts[0] if amts else 0
            tax = round(profit * 0.25, 2)
        return ("计提所得税费用", [
            _make_entry("6801", debit=tax, summary="所得税费用"),
            _make_entry("222102", credit=tax, summary="应交所得税"),
        ])

    def _rule_bad_debt(t, amts):
        amt = amts[0] if amts else 0
        return ("核销坏账准备", [
            _make_entry("1221", debit=amt, summary="坏账准备"),
            _make_entry("1122", credit=amt, summary="应收账款"),
        ])

    def _rule_equity_fixed(t, amts):
        amt = amts[0] if amts else 0
        return ("收到固定资产投资", [
            _make_entry("1601", debit=amt, summary="固定资产"),
            _make_entry("4001", credit=amt, summary="实收资本"),
        ])

    def _rule_housing_fund(t, amts):
        if len(amts) >= 2:
            co, per = amts[0], amts[1]
        else:
            total = amts[0] if amts else 0
            co = round(total * 0.5, 2)
            per = round(total * 0.5, 2)
        total = round(co + per, 2)
        return ("支付住房公积金", [
            _make_entry("6602", debit=co, summary="公积金（公司部分）"),
            _make_entry("1221", debit=per, summary="公积金（个人代扣）"),
            _make_entry("1002", credit=total, summary="银行存款支付"),
        ])

    # 内置规则列表: (pattern, handler, confidence)
    builtin_complex_rules = [
        (_re.compile(r'(采购|购买|购入)(材料|原材料|商品|货物).{0,15}(运费|运输|物流|装卸)'), _rule_purchase_freight, 0.94),
        (_re.compile(r'(销售|卖出|出售|销)(商品|货物|产品).{0,15}(折扣|折让|优惠|返利)'), _rule_sale_discount, 0.94),
        (_re.compile(r'(发放|发).{0,10}(工资|薪酬).{0,15}(代扣|扣除|个税|所得税)'), _rule_salary_tax, 0.93),
        (_re.compile(r'(支付|交|缴).{0,10}(社保|社会保险|养老保险|医疗保险)'), _rule_social_insurance, 0.92),
        (_re.compile(r'(支付|交|缴).{0,10}(公积金|住房公积金)'), _rule_housing_fund, 0.92),
        (_re.compile(r'(处置|出售|卖出|清理|报废).{0,15}(固定资产|设备|机器)'), _rule_fixed_asset_disposal, 0.91),
        (_re.compile(r'(建造|建设|施工|在建).{0,20}(完工|竣工|验收|转固)'), _rule_cip_transfer, 0.93),
        (_re.compile(r'(出口|外销|外贸).{0,20}(退税|出口退税|退税款)'), _rule_export_rebate, 0.90),
        (_re.compile(r'(采购|购买|购入).{0,15}(预付|预付款|先付|定金).{0,10}(货款|采购)'), _rule_prepay_purchase, 0.93),
        (_re.compile(r'(收到|收).{0,15}(预付|预收|定金|预付款)'), _rule_prepay_received, 0.93),
        (_re.compile(r'(利润|净利润).{0,15}(分配|分红|股利|派息)'), _rule_profit_dist, 0.93),
        (_re.compile(r'(计提|计算).{0,10}(所得税|企业所得税|所得)'), _rule_income_tax, 0.92),
        (_re.compile(r'(结转|转销|核销).{0,10}(坏账|坏账准备|减值)'), _rule_bad_debt, 0.92),
        (_re.compile(r'(收到|收).{0,10}(投资|注资|出资).{0,15}(设备|固定资产|资产)'), _rule_equity_fixed, 0.91),
    ]

    # 尝试内置规则匹配
    for pattern, handler, conf in builtin_complex_rules:
        if pattern.search(text):
            try:
                result = handler(text, amounts)
                if result:
                    desc, ents = result
                    total_dr = sum(e["debit"] for e in ents)
                    total_cr = sum(e["credit"] for e in ents)
                    if abs(total_dr - total_cr) < 0.02:
                        analysis["context_score"] = conf
                        return {
                            "description": desc, "entries": ents,
                            "confidence": conf, "composite": True,
                            "matched_rule": f"builtin:{pattern.pattern[:30]}",
                            "analysis": analysis,
                        }
            except Exception:
                continue

    # ── 3. 尝试 ai_rules_complex 表中的自定义规则 ──
    custom_rules = get_ai_rules_complex(active_only=True)
    for rule in custom_rules:
        try:
            if _re.search(rule["pattern"], text):
                ents_template = _json.loads(rule["entries_json"])
                # 简化: 将模板中的 amount_key 替换为 amounts 中的值
                ents = []
                for et in ents_template:
                    dr = 0
                    cr = 0
                    if "debit_key" in et and amounts:
                        key = et["debit_key"]
                        idx_map = {"material": 0, "freight": 1, "vat": 2, "gross": 0, "tax": 1,
                                   "net": 2, "company": 0, "personal": 1, "original": 0,
                                   "accumulated": 1, "proceeds": 2, "amount": 0, "cash": 1,
                                   "discount": 0, "total": 0, "revenue": 0, "rebate": 1}
                        idx = idx_map.get(key, 0)
                        dr = amounts[idx] if idx < len(amounts) else 0
                    elif "debit" in et:
                        dr = et["debit"]
                    if "credit_key" in et and amounts:
                        key = et["credit_key"]
                        idx_map2 = {"total": 0, "net": 2, "tax": 1, "amount": 0, "original": 0}
                        idx = idx_map2.get(key, 0)
                        cr = amounts[idx] if idx < len(amounts) else 0
                    elif "credit" in et:
                        cr = et["credit"]
                    ents.append(_make_entry(et["account_code"], debit=dr, credit=cr))
                if ents:
                    total_dr = sum(e["debit"] for e in ents)
                    total_cr = sum(e["credit"] for e in ents)
                    if abs(total_dr - total_cr) < 0.02:
                        analysis["context_score"] = 0.85
                        return {
                            "description": rule["description"], "entries": ents,
                            "confidence": 0.85, "composite": True,
                            "matched_rule": f"custom:{rule['name']}",
                            "analysis": analysis,
                        }
        except Exception:
            continue

    # ── 4. 回退到简单规则 ──
    simple_result = generate_voucher_from_text(ledger_id, text)
    simple_result["analysis"] = analysis
    simple_result["matched_rule"] = "simple_fallback"
    return simple_result

# ============================================================
# v3 升级：金蝶风格账务模块 - 新增表和函数
# ============================================================
# 注意：database_v3.py 初始为 database_v2.py 的完整副本
# 以下为 v3 新增内容

# ─── v3 新增表（在 init_db 中执行） ───

# 以下 DDL 需要合并到 init_db 的建表语句中
# 为简化操作，这里提供独立的建表函数

def init_v3_tables():
    """初始化 v3 新增的数据表"""
    conn = get_conn()
    
    # 固定资产类别
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fa_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            default_life_months INTEGER,
            default_residual_rate REAL DEFAULT 0.05,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 固定资产卡片
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fixed_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            asset_code TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            category_id INTEGER,
            purchase_date TEXT,
            original_value INTEGER NOT NULL DEFAULT 0,
            residual_rate REAL DEFAULT 0.05,
            residual_value INTEGER DEFAULT 0,
            useful_life_months INTEGER NOT NULL DEFAULT 120,
            depreciation_method TEXT DEFAULT 'straight_line',
            accumulated_depreciation INTEGER DEFAULT 0,
            net_value INTEGER DEFAULT 0,
            department TEXT,
            employee TEXT,
            location TEXT,
            status TEXT DEFAULT 'in_use',
            source_type TEXT DEFAULT 'purchase',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 资产变动记录
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fa_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            change_date TEXT,
            old_value INTEGER,
            new_value INTEGER,
            reason TEXT,
            voucher_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 银行账户
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            account_no TEXT NOT NULL,
            bank_name TEXT,
            account_name TEXT,
            currency_code TEXT DEFAULT 'CNY',
            opening_balance INTEGER DEFAULT 0,
            current_balance INTEGER DEFAULT 0,
            subject_code TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 银行对账单
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            statement_date TEXT,
            transaction_date TEXT,
            summary TEXT,
            debit INTEGER DEFAULT 0,
            credit INTEGER DEFAULT 0,
            reference_no TEXT,
            is_matched INTEGER DEFAULT 0,
            matched_journal_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 辅助核算类别
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auxiliary_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            aux_type TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 凭证分录辅助核算关联
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voucher_entry_auxiliaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            aux_type TEXT NOT NULL,
            aux_id INTEGER NOT NULL,
            aux_name TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 期末结转记录
    conn.execute("""
        CREATE TABLE IF NOT EXISTS closing_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            period TEXT NOT NULL,
            close_type TEXT NOT NULL,
            voucher_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 汇率表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates_v3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            effective_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 现金盘点
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cash_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            check_date TEXT NOT NULL,
            book_balance INTEGER DEFAULT 0,
            actual_balance INTEGER DEFAULT 0,
            difference INTEGER DEFAULT 0,
            handler TEXT,
            remark TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 支票管理
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            check_no TEXT NOT NULL,
            issue_date TEXT,
            payee TEXT,
            amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'issued',
            voucher_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 凭证模板表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voucher_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'general',
            entries TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE CASCADE,
            UNIQUE(ledger_id, name)
        )
    """)

    # 兼容旧表：添加新列
    for _col, _typ, _def in [
        ("category", "TEXT", "'general'"),
        ("is_active", "INTEGER", "1"),
        ("updated_at", "TEXT", "datetime('now','localtime')"),
    ]:
        try:
            conn.execute(f"ALTER TABLE voucher_templates ADD COLUMN {_col} {_typ} DEFAULT {_def}")
        except Exception:
            pass

    conn.commit()
    conn.close()
    clear_query_cache()


# ─── 固定资产管理函数 ───

def create_fixed_asset(ledger_id, asset_code, asset_name, original_value,
                       useful_life_months, category_id=None, purchase_date=None,
                       residual_rate=0.05, department=None, employee=None,
                       location=None, source_type='purchase',
                       depreciation_method='straight_line'):
    """创建固定资产卡片"""
    residual_value = int(original_value * residual_rate)
    net_value = original_value
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO fixed_assets 
        (ledger_id, asset_code, asset_name, category_id, purchase_date,
         original_value, residual_rate, residual_value, useful_life_months,
         depreciation_method, accumulated_depreciation, net_value,
         department, employee, location, source_type, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ledger_id, asset_code, asset_name, category_id, purchase_date,
          original_value, residual_rate, residual_value, useful_life_months,
          depreciation_method, 0, net_value,
          department, employee, location, source_type, 'in_use'))
    asset_id = cur.lastrowid
    conn.commit()
    conn.close()
    clear_query_cache()
    return asset_id


def get_fixed_assets(ledger_id, status=None):
    """获取固定资产列表"""
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM fixed_assets WHERE ledger_id = ? AND status = ? ORDER BY asset_code",
            (ledger_id, status)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM fixed_assets WHERE ledger_id = ? ORDER BY asset_code",
            (ledger_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fixed_asset(asset_id):
    """获取单个资产"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM fixed_assets WHERE id = ?", (asset_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def calculate_depreciation(asset_id, year, month):
    """计算单资产月折旧额（返回分值）"""
    asset = get_fixed_asset(asset_id)
    if not asset:
        return 0
    if asset['status'] != 'in_use':
        return 0
    remaining = asset['original_value'] - asset['accumulated_depreciation']
    residual = asset['residual_value']
    if remaining <= residual:
        return 0
    
    method = asset['depreciation_method']
    original = asset['original_value']
    life_months = asset['useful_life_months']
    
    if method == 'straight_line':
        monthly = (original - residual) / life_months
    elif method == 'double_declining':
        # 双倍余额递减法
        months_used = asset['accumulated_depreciation'] / ((original - residual) / life_months) if (original - residual) > 0 else 0
        remaining_life = life_months - months_used
        if remaining_life <= 24:
            # 最后两年改直线法
            monthly = (remaining - residual) / remaining_life if remaining_life > 0 else 0
        else:
            monthly = remaining * (2.0 / life_months)
    elif method == 'sum_of_years':
        # 年数总和法
        total_years = life_months / 12
        sum_years = total_years * (total_years + 1) / 2
        months_used = asset['accumulated_depreciation'] / ((original - residual) / life_months) if (original - residual) > 0 else 0
        current_year = int(months_used / 12) + 1
        remaining_years = total_years - current_year + 1
        monthly = (original - residual) * (remaining_years / sum_years) / 12
    else:
        monthly = (original - residual) / life_months
    
    # 确保不超过剩余可折旧金额
    depreciable = remaining - residual
    monthly = min(monthly, depreciable)
    return int(round(monthly))


def batch_calculate_depreciation(ledger_id, year, month):
    """批量计提折旧，返回 [(asset_id, amount), ...]"""
    assets = get_fixed_assets(ledger_id, status='in_use')
    results = []
    for asset in assets:
        amount = calculate_depreciation(asset['id'], year, month)
        if amount > 0:
            results.append((asset['id'], amount))
    return results


def dispose_asset(asset_id, dispose_type, proceeds=0):
    """资产处置"""
    asset = get_fixed_asset(asset_id)
    if not asset:
        return None
    
    net_value = asset['original_value'] - asset['accumulated_depreciation']
    gain_loss = proceeds - net_value  # 正数=收益，负数=损失
    
    conn = get_conn()
    conn.execute("""
        UPDATE fixed_assets SET status = 'disposed', net_value = 0, updated_at = datetime('now','localtime')
        WHERE id = ?
    """, (asset_id,))
    conn.execute("""
        INSERT INTO fa_changes (asset_id, change_type, change_date, old_value, new_value, reason)
        VALUES (?, ?, ?, ?, 0, ?)
    """, (asset_id, f'dispose_{dispose_type}', 
          f"{year}-{month:02d}-01" if 'year' in dir() else None,
          net_value, f"处置方式:{dispose_type}, 收入:{proceeds}"))
    conn.commit()
    conn.close()
    clear_query_cache()
    
    return {
        'asset_id': asset_id,
        'original_value': asset['original_value'],
        'accumulated_depreciation': asset['accumulated_depreciation'],
        'net_value': net_value,
        'proceeds': proceeds,
        'gain_loss': gain_loss
    }


# ─── 出纳管理函数 ───

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
              row.get('summary', ''), int(row.get('debit', 0)), int(row.get('credit', 0)),
              row.get('reference_no', '')))
        imported += 1
    conn.commit()
    conn.close()
    clear_query_cache()
    return imported


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
            SELECT ve.* FROM voucher_entries ve
            JOIN vouchers v ON ve.voucher_id = v.id
            WHERE v.ledger_id = (SELECT ledger_id FROM bank_accounts WHERE id = ?)
            AND v.voucher_date = ?
            AND ((ve.debit_amount = ? AND ? > 0) OR (ve.credit_amount = ? AND ? < 0))
            LIMIT 1
        """, (bank_account_id, stmt['transaction_date'], 
              stmt['debit'], stmt['credit'], abs(stmt['credit']), stmt['credit'])).fetchall()
        
        if entries:
            conn.execute("UPDATE bank_statements SET is_matched = 1 WHERE id = ?", (stmt['id'],))
            matched += 1
    
    conn.commit()
    conn.close()
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


# ─── 辅助核算函数 ───

def create_auxiliary(ledger_id, aux_type, code, name, parent_id=None):
    """创建辅助核算项目"""
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO auxiliary_categories (ledger_id, aux_type, code, name, parent_id)
        VALUES (?,?,?,?,?)
    """, (ledger_id, aux_type, code, name, parent_id))
    aux_id = cur.lastrowid
    conn.commit()
    conn.close()
    clear_query_cache()
    return aux_id


def get_auxiliaries(ledger_id, aux_type=None):
    """获取辅助核算列表"""
    conn = get_conn()
    if aux_type:
        rows = conn.execute(
            "SELECT * FROM auxiliary_categories WHERE ledger_id = ? AND aux_type = ? AND is_active = 1 ORDER BY code",
            (ledger_id, aux_type)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM auxiliary_categories WHERE ledger_id = ? AND is_active = 1 ORDER BY aux_type, code",
            (ledger_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_auxiliary(aux_id, code=None, name=None, is_active=None):
    """更新辅助核算项目"""
    conn = get_conn()
    updates = []
    params = []
    if code is not None:
        updates.append("code = ?")
        params.append(code)
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(is_active)
    if not updates:
        conn.close()
        return
    params.append(aux_id)
    conn.execute(f"UPDATE auxiliary_categories SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    clear_query_cache()


def delete_auxiliary(aux_id):
    """删除辅助核算项目（检查是否被引用）"""
    conn = get_conn()
    ref = conn.execute("SELECT COUNT(*) as cnt FROM voucher_entry_auxiliaries WHERE aux_id = ?", (aux_id,)).fetchone()['cnt']
    if ref > 0:
        conn.close()
        return False, f"该辅助核算项目已被 {ref} 条凭证分录引用，无法删除"
    conn.execute("DELETE FROM auxiliary_categories WHERE id = ?", (aux_id,))
    conn.commit()
    conn.close()
    clear_query_cache()
    return True, "删除成功"


def save_aux_mapping(entry_id, aux_type, aux_id, aux_name=None):
    """保存凭证分录与辅助核算的关联"""
    conn = get_conn()
    conn.execute("DELETE FROM voucher_entry_auxiliaries WHERE entry_id = ? AND aux_type = ?",
                 (entry_id, aux_type))
    if aux_id:
        conn.execute(
            "INSERT INTO voucher_entry_auxiliaries (entry_id, aux_type, aux_id, aux_name) VALUES (?,?,?,?)",
            (entry_id, aux_type, aux_id, aux_name))
    conn.commit()
    conn.close()
    clear_query_cache()


def get_aux_mapping(entry_id):
    """获取凭证分录的辅助核算关联"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM voucher_entry_auxiliaries WHERE entry_id = ?", (entry_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_aux_balance(ledger_id, aux_type, year=None, month=None):
    """辅助核算余额表：按辅助核算项汇总借贷方"""
    conn = get_conn()
    date_filter = ""
    params = [ledger_id, aux_type]
    if year:
        date_filter += " AND strftime('%Y', v.date) = ?"
        params.append(str(year))
    if month:
        date_filter += " AND strftime('%m', v.date) = ?"
        params.append(f"{month:02d}")

    rows = conn.execute(
        "SELECT ac.id as aux_id, ac.code as aux_code, ac.name as aux_name, ac.aux_type, "
        "COALESCE(SUM(CASE WHEN je.amount > 0 THEN je.amount ELSE 0 END), 0) as total_debit, "
        "COALESCE(SUM(CASE WHEN je.amount < 0 THEN ABS(je.amount) ELSE 0 END), 0) as total_credit "
        "FROM auxiliary_categories ac "
        "LEFT JOIN voucher_entry_auxiliaries vea ON vea.aux_id = ac.id AND vea.aux_type = ac.aux_type "
        "LEFT JOIN journal_entries je ON je.id = vea.entry_id "
        "LEFT JOIN vouchers v ON v.voucher_no = je.voucher_no AND v.ledger_id = ? "
        "WHERE ac.ledger_id = ? AND ac.aux_type = ? AND ac.is_active = 1 " + date_filter + " "
        "GROUP BY ac.id, ac.code, ac.name, ac.aux_type ORDER BY ac.code",
        params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_aux_ledger(ledger_id, aux_type, aux_id, year=None, month=None):
    """辅助核算明细账：按辅助核算项查看凭证分录"""
    conn = get_conn()
    date_filter = ""
    params = [aux_id, aux_type, ledger_id]
    if year:
        date_filter += " AND strftime('%Y', v.date) = ?"
        params.append(str(year))
    if month:
        date_filter += " AND strftime('%m', v.date) = ?"
        params.append(f"{month:02d}")

    rows = conn.execute(
        "SELECT v.voucher_no, v.date, v.summary as voucher_summary, "
        "je.account_code, je.account_name, je.amount, je.summary as entry_summary, "
        "vea.aux_type, vea.aux_name, v.status "
        "FROM voucher_entry_auxiliaries vea "
        "INNER JOIN journal_entries je ON je.id = vea.entry_id "
        "INNER JOIN vouchers v ON v.voucher_no = je.voucher_no "
        "WHERE vea.aux_id = ? AND vea.aux_type = ? AND v.ledger_id = ? " + date_filter + " "
        "ORDER BY v.date, v.voucher_no",
        params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_vouchers_by_aux(ledger_id, aux_type, aux_id, year=None, month=None):
    """按辅助核算查询凭证"""
    conn = get_conn()
    date_filter = ""
    params = [aux_id, aux_type, ledger_id]
    if year:
        date_filter += " AND strftime('%Y', v.date) = ?"
        params.append(str(year))
    if month:
        date_filter += " AND strftime('%m', v.date) = ?"
        params.append(f"{month:02d}")

    rows = conn.execute(
        "SELECT DISTINCT v.voucher_no, v.date, v.summary, v.total_debit, v.total_credit, v.status "
        "FROM vouchers v "
        "INNER JOIN journal_entries je ON je.voucher_no = v.voucher_no "
        "INNER JOIN voucher_entry_auxiliaries vea ON vea.entry_id = je.id "
        "WHERE vea.aux_id = ? AND vea.aux_type = ? AND v.ledger_id = ? " + date_filter + " "
        "ORDER BY v.date DESC, v.voucher_no DESC",
        params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def multi_aux_search(ledger_id, aux_filters, year=None, month=None):
    """多维交叉查询：aux_filters = [(aux_type, aux_id), ...]"""
    conn = get_conn()
    if not aux_filters:
        return []

    joins = []
    where_parts = ["v.ledger_id = ?"]
    params = [ledger_id]
    date_filter = ""

    for i, (atype, aid) in enumerate(aux_filters):
        alias = f"vea{i}"
        joins.append(f"INNER JOIN voucher_entry_auxiliaries {alias} ON {alias}.entry_id = je.id")
        where_parts.append(f"{alias}.aux_type = ? AND {alias}.aux_id = ?")
        params.extend([atype, aid])

    if year:
        date_filter += " AND strftime('%Y', v.date) = ?"
        params.append(str(year))
    if month:
        date_filter += " AND strftime('%m', v.date) = ?"
        params.append(f"{month:02d}")

    join_str = " ".join(joins)
    where_str = " AND ".join(where_parts)

    sql = (
        "SELECT DISTINCT v.voucher_no, v.date, v.summary, v.total_debit, v.total_credit, v.status "
        "FROM vouchers v "
        "INNER JOIN journal_entries je ON je.voucher_no = v.voucher_no "
        + join_str + " "
        "WHERE " + where_str + " " + date_filter + " "
        "ORDER BY v.date DESC, v.voucher_no DESC"
    )
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]




# ─── 期末处理函数 ───



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
    


# ─── 初始化 v3 表 ───
# 在应用启动时调用
# init_v3_tables()


# ─── 全局搜索 ───

def search_vouchers(keyword, limit=10):
    """全局搜索凭证：按凭证号、摘要、金额模糊匹配"""
    conn = get_conn()
    kw = f"%{keyword}%"
    rows = conn.execute("""
        SELECT v.voucher_no, v.date, v.summary, v.total_debit, v.total_credit, v.status
        FROM vouchers v
        WHERE v.voucher_no LIKE ? OR v.summary LIKE ?
        ORDER BY v.date DESC, v.voucher_no DESC
        LIMIT ?
    """, (kw, kw, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_accounts_by_kw(keyword, limit=10):
    """全局搜索科目：按科目编码、名称模糊匹配"""
    conn = get_conn()
    kw = f"%{keyword}%"
    rows = conn.execute("""
        SELECT code, name, category, subcategory, is_active
        FROM accounts
        WHERE is_active = 1 AND (code LIKE ? OR name LIKE ?)
        ORDER BY code
        LIMIT ?
    """, (kw, kw, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_db(sql, params=()):
    """执行查询并返回字典列表"""
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "finance_v2.db")
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── 缓存管理 ──
def clear_query_cache():
    """清除所有查询缓存 — 在写操作后调用"""
    get_balance_sheet.cache_clear()
    get_income_statement.cache_clear()
    get_vouchers.cache_clear()
    get_ledgers.cache_clear()


# ─── Phase 1 新增函数 ───

def get_account_ledger(ledger_id, account_code, year, month):
    """获取科目明细账：返回指定科目在期间内的所有凭证分录及余额"""
    conn = get_conn()
    acct = conn.execute("SELECT code, name, category FROM accounts WHERE code=? AND is_active=1", (account_code,)).fetchone()
    if not acct:
        conn.close()
        return None
    acct = dict(acct)
    opening = get_opening_balance(ledger_id, account_code, year, month)
    entries = conn.execute("""
        SELECT je.id, je.debit, je.credit, je.summary,
               v.voucher_no, v.date, v.description as voucher_desc, v.status
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND je.account_code = ?
          AND strftime('%Y', v.date) = ? AND CAST(strftime('%m', v.date) AS INTEGER) <= ?
          AND v.status = 'posted'
        ORDER BY v.date, v.voucher_no, je.id
    """, (ledger_id, account_code, str(year), month)).fetchall()
    conn.close()
    bal = opening
    rows = []
    for e in entries:
        d = dict(e)
        bal += d["debit"] - d["credit"]
        d["balance"] = round(bal, 2)
        rows.append(d)
    return {
        "account": acct,
        "opening_balance": round(opening, 2),
        "closing_balance": round(bal, 2),
        "entries": rows,
        "period": f"{year}-{month:02d}",
    }


def get_cash_flow_statement_direct(ledger_id, year, month):
    """现金流量表（直接法）- 简化版，按对方科目类别归类"""
    conn = get_conn()

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


# ── Phase 2.2: Dashboard KPI ──

def get_dashboard_kpi(ledger_id, year, month):
    """获取仪表盘 KPI 数据"""
    conn = get_conn()

    ar = conn.execute("""
        SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) as bal
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND je.account_code LIKE '1122%'
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) <= ?
    """, (ledger_id, str(year), month)).fetchone()
    ar_bal = ar["bal"] if ar else 0

    ap = conn.execute("""
        SELECT COALESCE(SUM(je.credit) - SUM(je.debit), 0) as bal
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND je.account_code LIKE '2202%'
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) <= ?
    """, (ledger_id, str(year), month)).fetchone()
    ap_bal = ap["bal"] if ap else 0

    bank = conn.execute("""
        SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) as bal
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND je.account_code LIKE '1002%'
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) <= ?
    """, (ledger_id, str(year), month)).fetchone()
    bank_bal = bank["bal"] if bank else 0

    rev = conn.execute("""
        SELECT COALESCE(SUM(je.credit) - SUM(je.debit), 0) as total
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN accounts a ON je.account_code = a.code
        WHERE je.ledger_id = ? AND a.category = '收入' AND a.is_active = 1
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) = ?
    """, (ledger_id, str(year), month)).fetchone()
    month_revenue = rev["total"] if rev else 0

    exp = conn.execute("""
        SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) as total
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN accounts a ON je.account_code = a.code
        WHERE je.ledger_id = ? AND a.category = '费用' AND a.is_active = 1
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) = ?
    """, (ledger_id, str(year), month)).fetchone()
    month_expense = exp["total"] if exp else 0

    cash_flow = conn.execute("""
        SELECT COALESCE(SUM(je.debit) - SUM(je.credit), 0) as total
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        WHERE je.ledger_id = ? AND (je.account_code LIKE '1001%' OR je.account_code LIKE '1002%')
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) = ?
    """, (ledger_id, str(year), month)).fetchone()
    net_cash_flow = cash_flow["total"] if cash_flow else 0

    conn.close()
    return {
        "ar_balance": ar_bal,
        "ap_balance": ap_bal,
        "bank_balance": bank_bal,
        "month_revenue": month_revenue,
        "month_expense": month_expense,
        "month_profit": month_revenue - month_expense,
        "net_cash_flow": net_cash_flow,
    }


def get_monthly_trend(ledger_id, months=12):
    """获取最近 N 个月的收支趋势"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT strftime('%Y', v.date) as year,
               CAST(strftime('%m', v.date) AS INTEGER) as month,
               SUM(CASE WHEN a.category = '收入' THEN je.credit - je.debit ELSE 0 END) as revenue,
               SUM(CASE WHEN a.category = '费用' THEN je.debit - je.credit ELSE 0 END) as expense
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN accounts a ON je.account_code = a.code AND a.is_active = 1
        WHERE je.ledger_id = ? AND v.status = 'posted'
          AND a.category IN ('收入', '费用')
        GROUP BY year, month
        ORDER BY year DESC, month DESC
        LIMIT ?
    """, (ledger_id, months)).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    result.reverse()
    return result


def get_expense_breakdown(ledger_id, year, month):
    """获取费用占比数据"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT a.sub_category as category,
               SUM(je.debit - je.credit) as amount
        FROM journal_entries je
        JOIN vouchers v ON je.voucher_id = v.id
        JOIN accounts a ON je.account_code = a.code AND a.is_active = 1
        WHERE je.ledger_id = ? AND a.category = '费用'
          AND v.status = 'posted'
          AND strftime('%Y',v.date) = ? AND CAST(strftime('%m',v.date) AS INTEGER) = ?
        GROUP BY a.sub_category
        HAVING amount > 0
        ORDER BY amount DESC
    """, (ledger_id, str(year), month)).fetchall()
    conn.close()
    return [{"category": r["category"] or "其他", "amount": r["amount"]} for r in rows]


# ── Phase 2.3: 凭证智能联想 ──

def search_voucher_history_v2(ledger_id, keyword, limit=5):
    """搜索历史凭证：按摘要模糊匹配（Phase 2 版本，带 ledger_id 过滤）"""
    conn = get_conn()
    kw = f"%{keyword}%"
    rows = conn.execute("""
        SELECT DISTINCT v.description as summary,
               je.account_code, je.account_name,
               AVG(je.debit + je.credit) as avg_amount
        FROM vouchers v
        JOIN journal_entries je ON v.id = je.voucher_id
        WHERE v.ledger_id = ?
          AND v.description LIKE ?
          AND v.status = 'posted'
          AND je.debit + je.credit > 0
        GROUP BY v.description, je.account_code
        ORDER BY v.date DESC
        LIMIT ?
    """, (ledger_id, kw, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
