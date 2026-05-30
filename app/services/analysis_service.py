"""智能分析服务 — 财务数据异常检测"""
from app.services import ReportService


def analyze_period(lid, year, month):
    """分析指定期间的财务数据，返回异常和建议
    
    Returns:
        dict: {
            "summary": str,      # 摘要
            "anomalies": list,   # 异常列表
            "suggestions": list, # 建议列表
            "kpi": dict,         # 关键指标
        }
    """
    result = {
        "summary": "",
        "anomalies": [],
        "suggestions": [],
        "kpi": {},
    }
    
    # ── 获取数据 ──
    balances = ReportService.get_account_balances(lid, year, month)
    income = ReportService.get_income_statement(lid, year, month)
    bs = ReportService.get_balance_sheet(lid, year, month)
    
    if not balances:
        result["summary"] = "暂无财务数据"
        return result
    
    # ── 计算关键指标 ──
    total_assets = sum(float(b.get("closing_balance", 0) or 0) for b in balances if b.get("category") == "资产")
    total_liab = abs(sum(float(b.get("closing_balance", 0) or 0) for b in balances if b.get("category") == "负债"))
    total_equity = abs(sum(float(b.get("closing_balance", 0) or 0) for b in balances if b.get("category") == "权益"))
    
    # 资产负债率
    debt_ratio = (total_liab / total_assets * 100) if total_assets > 0 else 0
    
    # 利润数据
    revenue = 0
    expense = 0
    net_profit = 0
    if income and isinstance(income, dict):
        rows = income.get("rows", [])
        for r in rows:
            rtype = r.get("type", "")
            val = float(r.get("ytd", 0) or 0)
            if rtype.startswith("rev"):
                revenue += val
            elif rtype.startswith("exp"):
                expense += val
        net_profit = revenue - expense
    
    profit_margin = (net_profit / revenue * 100) if revenue > 0 else 0
    
    result["kpi"] = {
        "total_assets": total_assets,
        "total_liab": total_liab,
        "debt_ratio": round(debt_ratio, 1),
        "revenue": revenue,
        "expense": expense,
        "net_profit": net_profit,
        "profit_margin": round(profit_margin, 1),
    }
    
    # ── 异常检测 ──
    anomalies = []
    
    # 1. 资产负债率过高
    if debt_ratio > 90:
        anomalies.append({
            "level": "danger",
            "title": "资产负债率过高",
            "detail": f"当前资产负债率 {debt_ratio:.1f}%，接近资不抵债",
            "suggestion": "立即评估偿债能力，考虑增资或减债"
        })
    elif debt_ratio > 70:
        anomalies.append({
            "level": "warning",
            "title": "资产负债率偏高",
            "detail": f"当前资产负债率 {debt_ratio:.1f}%，超过 70% 警戒线",
            "suggestion": "关注偿债风险，考虑优化负债结构"
        })
    
    # 2. 净利润为负
    if net_profit < 0:
        anomalies.append({
            "level": "warning",
            "title": "本期净利润为负",
            "detail": f"净亏损 ¥{abs(net_profit):,.2f}",
            "suggestion": "分析亏损原因，控制成本费用"
        })
    
    # 3. 利润率异常低
    if revenue > 0 and profit_margin < 5 and profit_margin > 0:
        anomalies.append({
            "level": "info",
            "title": "利润率偏低",
            "detail": f"净利润率仅 {profit_margin:.1f}%",
            "suggestion": "审查成本结构，寻找降本增效空间"
        })
    
    # 4. 货币资金异常
    cash_balance = sum(float(b.get("closing_balance", 0) or 0) for b in balances 
                       if b.get("account_code", "").startswith(("1001", "1002")))
    if cash_balance < 0:
        anomalies.append({
            "level": "danger",
            "title": "货币资金为负",
            "detail": f"货币资金余额 ¥{cash_balance:,.2f}",
            "suggestion": "检查是否有未入账的收款或银行未达账项"
        })
    
    # 5. 应收账款异常
    ar_balance = sum(float(b.get("closing_balance", 0) or 0) for b in balances 
                     if b.get("account_code", "").startswith("1122"))
    if total_assets > 0 and ar_balance / total_assets > 0.4:
        anomalies.append({
            "level": "warning",
            "title": "应收账款占比过高",
            "detail": f"应收账款占总资产 {ar_balance/total_assets*100:.1f}%",
            "suggestion": "加强催收，评估坏账风险"
        })
    
    # 6. 借贷不平衡
    total_debit = sum(float(b.get("period_debit", 0) or 0) for b in balances)
    total_credit = sum(float(b.get("period_credit", 0) or 0) for b in balances)
    diff = abs(total_debit - total_credit)
    if diff > 0.01:
        anomalies.append({
            "level": "danger",
            "title": "借贷不平衡",
            "detail": f"借方 ¥{total_debit:,.2f} / 贷方 ¥{total_credit:,.2f} / 差额 ¥{diff:,.2f}",
            "suggestion": "检查凭证录入是否有误"
        })
    
    result["anomalies"] = anomalies
    
    # ── 智能建议 ──
    suggestions = []
    if net_profit > 0 and profit_margin > 15:
        suggestions.append("✅ 盈利状况良好，利润率健康")
    if debt_ratio < 40:
        suggestions.append("✅ 负债水平较低，财务风险可控")
    if cash_balance > 0 and total_assets > 0:
        cash_ratio = cash_balance / total_assets * 100
        if cash_ratio > 20:
            suggestions.append(f"💰 货币资金充裕（占总资产 {cash_ratio:.1f}%），可考虑理财增值")
    
    result["suggestions"] = suggestions
    
    # ── 摘要 ──
    status = "正常" if not anomalies else f"发现 {len(anomalies)} 项异常"
    result["summary"] = (f"{year}年{month}月财务分析 — {status}\n"
                         f"总资产: ¥{total_assets:,.2f} | 总负债: ¥{total_liab:,.2f} | "
                         f"负债率: {debt_ratio:.1f}%\n"
                         f"收入: ¥{revenue:,.2f} | 净利润: ¥{net_profit:,.2f} | "
                         f"利润率: {profit_margin:.1f}%")
    
    return result
