"""AI助手"""
from nicegui import ui
from app.components.state import state
from app.components.ui_helpers import show_toast
from database_v3 import generate_voucher_from_text, get_ledgers, query_db

# 外部 API（可选）
try:
    from external_apis import convert_currency
    _EXTERNAL_APIS_OK = True
except ImportError:
    _EXTERNAL_APIS_OK = False
    convert_currency = None

def do_ai_generate(text):
    """AI智能凭证生成 — 基于规则引擎"""
    if not text or not text.strip():
        show_toast("请输入业务描述", "warning")
        return
    lid = state.selected_ledger_id
    if not lid:
        show_toast("请先选择账套", "warning")
        return
    try:
        result = generate_voucher_from_text(lid, text)
        entries = result.get("entries", [])
        confidence = result.get("confidence", 0)
        if not entries:
            show_toast("无法识别该业务描述，请尝试其他描述", "warning")
            return
        # 构建显示文本
        lines = [f"📝 {result.get('description', text)}", f"📊 置信度: {confidence:.0%}", "━" * 30]
        total_dr = total_cr = 0
        for e in entries:
            amt = e.get("debit", 0) or e.get("credit", 0)
            side = "借" if e.get("debit", 0) else "贷"
            lines.append(f"  {side}  {e.get('account_code', '')} {e.get('account_name', '')}  ¥{amt:,.2f}")
            total_dr += e.get("debit", 0)
            total_cr += e.get("credit", 0)
        lines.append("━" * 30)
        lines.append(f"  借方合计: ¥{total_dr:,.2f}  贷方合计: ¥{total_cr:,.2f}")
        if result.get("currency", "CNY") != "CNY":
            lines.append(f"  币种: {result['currency']}  汇率: {result.get('exchange_rate', 1)}")
        show_toast("\n".join(lines), "success" if confidence >= 0.7 else "warning")
    except Exception as e:
        show_toast(f"生成失败: {str(e)}", "error")

def do_ocr_extract(text):
    """发票OCR信息提取 — 正则规则引擎"""
    import re
    if not text or not text.strip():
        show_toast("请粘贴OCR识别文本", "warning")
        return
    text = text.strip()
    results = {}

    # 发票号码
    inv_no_patterns = [
        r'发票号码[：:\s]*([A-Za-z0-9]+)',
        r'发票号[：:\s]*([A-Za-z0-9]+)',
        r'No[.\s:：]*([A-Za-z0-9]{8,20})',
        r'([A-Z]{2}\d{16,20})',
    ]
    for p in inv_no_patterns:
        m = re.search(p, text)
        if m:
            results["发票号码"] = m.group(1)
            break

    # 发票代码
    code_patterns = [
        r'发票代码[：:\s]*(\d{10,12})',
        r'代码[：:\s]*(\d{10,12})',
    ]
    for p in code_patterns:
        m = re.search(p, text)
        if m:
            results["发票代码"] = m.group(1)
            break

    # 开票日期
    date_patterns = [
        r'开票日期[：:\s]*(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}[日]?)',
        r'日期[：:\s]*(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}[日]?)',
        r'(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}[日]?)',
    ]
    for p in date_patterns:
        m = re.search(p, text)
        if m:
            results["开票日期"] = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
            break

    # 金额（价税合计）
    amount_patterns = [
        r'价税合计[（(]小写[)）][：:\s]*[¥￥]?\s*([\d,]+\.?\d*)',
        r'合计[金额]*[：:\s]*[¥￥]?\s*([\d,]+\.?\d*)',
        r'总计[：:\s]*[¥￥]?\s*([\d,]+\.?\d*)',
        r'[¥￥]\s*([\d,]+\.?\d{0,2})',
    ]
    for p in amount_patterns:
        m = re.search(p, text)
        if m:
            results["价税合计"] = f"¥{m.group(1)}"
            break

    # 不含税金额
    net_patterns = [
        r'不含税金额[：:\s]*[¥￥]?\s*([\d,]+\.?\d*)',
        r'金额[：:\s]*[¥￥]?\s*([\d,]+\.?\d*)',
    ]
    for p in net_patterns:
        m = re.search(p, text)
        if m:
            results["不含税金额"] = f"¥{m.group(1)}"
            break

    # 税额
    tax_patterns = [
        r'税额[：:\s]*[¥￥]?\s*([\d,]+\.?\d*)',
        r'税[款额][：:\s]*[¥￥]?\s*([\d,]+\.?\d*)',
    ]
    for p in tax_patterns:
        m = re.search(p, text)
        if m:
            results["税额"] = f"¥{m.group(1)}"
            break

    # 销售方
    seller_patterns = [
        r'销售方[：:\s]*([^\n]{2,40})',
        r'卖方[：:\s]*([^\n]{2,40})',
        r'销售单位[：:\s]*([^\n]{2,40})',
    ]
    for p in seller_patterns:
        m = re.search(p, text)
        if m:
            results["销售方"] = m.group(1).strip()
            break

    # 购买方
    buyer_patterns = [
        r'购买方[：:\s]*([^\n]{2,40})',
        r'买方[：:\s]*([^\n]{2,40})',
        r'采购方[：:\s]*([^\n]{2,40})',
    ]
    for p in buyer_patterns:
        m = re.search(p, text)
        if m:
            results["购买方"] = m.group(1).strip()
            break

    if not results:
        show_toast("未能从OCR文本中识别出有效信息", "warning")
        return

    # 显示结果
    lines = ["📋 发票信息提取结果", "━" * 30]
    for k, v in results.items():
        lines.append(f"  {k}：{v}")
    show_toast("\n".join(lines), "success")

def render_ai_assistant():
    if not state.selected_ledger_id:
        ledgers = get_ledgers()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]
    lid = state.selected_ledger_id
    with ui.row().classes("w-full gap-3"):
        with ui.column().classes("w-1/2 gap-2"):
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    ui.label("🤖 智能凭证").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    ai_input = ui.input("业务描述", placeholder="例：收到股东投资款100万").props("outlined dense").classes("w-full")
                    ui.button("🧠 生成分录", color="primary", on_click=lambda: do_ai_generate(ai_input.value)).props("dense").classes("w-full mt-1")

            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    ui.label("📷 发票OCR").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    ocr_input = ui.textarea("OCR文本", placeholder="粘贴发票OCR识别结果...").props("outlined dense").classes("w-full")
                    ui.button("🔍 提取信息", color="orange", on_click=lambda: do_ocr_extract(ocr_input.value)).props("dense").classes("w-full mt-1")

            # ── P1-5: 自然语言查询 ──
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    ui.label("💬 自然语言查询").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    nl_input = ui.input("问财务问题", placeholder="例：上月利润是多少？银行存款余额？").props("outlined dense").classes("w-full")
                    nl_result = ui.label("").classes("text-sm mt-2 p-2 rounded min-h-[60px] whitespace-pre-wrap").style("color:var(--c-bg-hover)")
                    ui.button("🔍 查询", color="teal", on_click=lambda: _do_nl_query(nl_input.value, nl_result)).props("dense").classes("w-full mt-1")

            # ── P1-5: 财务知识问答 ──
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    ui.label("📚 财务知识库").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    kb_input = ui.input("搜索知识", placeholder="例：什么是借贷记账法？").props("outlined dense").classes("w-full")
                    kb_result = ui.label("").classes("text-sm mt-2 p-2 rounded min-h-[80px] whitespace-pre-wrap").style("color:var(--c-bg-hover)").style("color:var(--c-text-secondary)")
                    ui.button("📖 查询", color="purple", on_click=lambda: _do_kb_query(kb_input.value, kb_result)).props("dense").classes("w-full mt-1")

        with ui.column().classes("w-1/2 gap-2"):
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    ui.label("📖 支持场景").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    with ui.column().classes("gap-0.5 text-sm"):
                        scenes = [
                            ("💰 筹资", ["收到投资款","取得借款","归还借款","支付利息"]),
                            ("🏭 采购", ["购买设备","采购材料","赊购","预付货款"]),
                            ("📦 销售", ["销售收入","赊销商品","收到货款","结转成本"]),
                            ("💳 费用", ["办公费","工资薪酬","水电费","房租"]),
                            ("📢 营销", ["广告费","差旅费","计提折旧"]),
                            ("🧾 税费", ["增值税","所得税","城建税"]),
                            ("🔧 其他", ["投资收益","捐赠","罚款","费用报销"]),
                        ]
                        for group, items in scenes:
                            ui.label(group).classes("font-semibold mt-1").style("color:var(--c-text-secondary)")
                            for item in items:
                                ui.label(f"  · {item}").classes("text-xs").style("color:var(--c-text-secondary)")

            # 汇率转换工具
            if _EXTERNAL_APIS_OK:
                with ui.card().classes("w-full"):
                    with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("currency_exchange").style("color:var(--c-primary)")
                            ui.label("汇率转换").classes("text-sm font-semibold")
                    with ui.card_section().classes("py-2 px-3"):
                        with ui.column().classes("gap-1.5"):
                            fx_amount = ui.number("金额", value=100, precision=2).props("outlined dense").classes("w-full")
                            with ui.row().classes("gap-1"):
                                fx_from = ui.select(options={"CNY":"人民币","USD":"美元","EUR":"欧元","GBP":"英镑","JPY":"日元","HKD":"港币"}, value="CNY", label="从").props("outlined dense").classes("flex-1")
                                fx_to = ui.select(options={"CNY":"人民币","USD":"美元","EUR":"欧元","GBP":"英镑","JPY":"日元","HKD":"港币"}, value="USD", label="到").props("outlined dense").classes("flex-1")
                            fx_result_label = ui.label("").classes("text-center font-bold text-lg mt-1 tabular-nums tabular-nums").style("color:var(--c-primary)")
                            def _do_fx_convert():
                                amt = fx_amount.value
                                fc = fx_from.value
                                tc = fx_to.value
                                if not amt or not fc or not tc:
                                    return
                                result = convert_currency(amt, fc, tc)
                                if result is not None:
                                    fx_result_label.text = f"{amt:,.2f} {fc} = {result:,.2f} {tc}"
                                else:
                                    fx_result_label.text = "转换失败，请重试"
                            ui.button("🔄 转换", color="blue", on_click=_do_fx_convert).props("dense").classes("w-full")

            # 自然语言查报表
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("chat").style("color:#7C3AED")
                        ui.label("💬 自然语言查询").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    nl_input = ui.input("问财务问题", placeholder="例：上月利润是多少？银行存款余额？").props("outlined dense").classes("w-full")
                    nl_result = ui.label("").classes("text-sm mt-2 p-2 rounded min-h-[40px]").style("color:var(--c-bg-hover)")
                    ui.button("🔍 查询", color="purple", on_click=lambda: _do_nl_query(nl_input.value, nl_result)).props("dense").classes("w-full mt-1")

            # 财务知识问答
            with ui.card().classes("w-full"):
                with ui.card_section().classes("py-2 px-3 border-b border-grey-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("menu_book").style("color:var(--c-success)")
                        ui.label("📚 财务知识库").classes("text-sm font-semibold")
                with ui.card_section().classes("py-2 px-3"):
                    kb_input = ui.input("搜索知识", placeholder="例：什么是借贷记账法？").props("outlined dense").classes("w-full")
                    kb_result = ui.label("").classes("text-sm mt-2 p-2 rounded min-h-[40px]").style("color:var(--c-bg-hover)")
                    ui.button("📖 搜索", color="green", on_click=lambda: _do_kb_query(kb_input.value, kb_result)).props("dense").classes("w-full mt-1")


# ===== 财务知识库 =====
def _do_nl_query(query_text, result_label):
    """自然语言查询财务数据"""
    if not query_text.strip():
        result_label.text = "请输入查询问题"
        return
    q = query_text.strip().lower()
    lid = state.selected_ledger_id
    try:
        if any(kw in q for kw in ["利润", "净利润", "盈利", "亏损", "收益"]):
            # 查询利润表数据
            year = state.selected_year
            month = state.selected_month
            report = get_income_statement(lid, year, month)
            if report:
                total_revenue = sum(float(r.get("balance", 0)) for r in report if r.get("category") == "revenue")
                total_expense = sum(abs(float(r.get("balance", 0))) for r in report if r.get("category") == "expense")
                net_profit = total_revenue - total_expense
                result_label.text = (f"📊 {year}年{month}月利润表摘要\n"
                                      f"━━━━━━━━━━━━━━━━━━\n"
                                      f"营业收入：¥{total_revenue:,.2f}\n"
                                      f"营业成本：¥{total_expense:,.2f}\n"
                                      f"净利润：  ¥{net_profit:,.2f}\n"
                                      f"利润率：  {(net_profit/total_revenue*100) if total_revenue else 0:.1f}%")
            else:
                result_label.text = "暂无利润表数据，请先录入凭证"

        elif any(kw in q for kw in ["存款", "银行", "余额", "现金", "资金"]):
            # 查询银行存款和现金余额
            accounts = get_account_balances(lid)
            cash_items = [a for a in accounts if a.get("code","").startswith(("1001","1002"))]
            if cash_items:
                lines = ["💰 货币资金余额", "━━━━━━━━━━━━━━━━━━"]
                total = 0
                for a in cash_items:
                    bal = float(a.get("balance", 0))
                    total += bal
                    lines.append(f"{a.get('name','')}：¥{bal:,.2f}")
                lines.append(f"━━━━━━━━━━━━━━━━━━")
                lines.append(f"合计：¥{total:,.2f}")
                result_label.text = "\n".join(lines)
            else:
                result_label.text = "暂无货币资金数据"

        elif any(kw in q for kw in ["应收", "应收账款", "欠款", "应收款"]):
            accounts = get_account_balances(lid)
            ar_items = [a for a in accounts if a.get("code","").startswith("1122")]
            if ar_items:
                lines = ["📋 应收账款余额", "━━━━━━━━━━━━━━━━━━"]
                total = 0
                for a in ar_items:
                    bal = float(a.get("balance", 0))
                    total += bal
                    lines.append(f"{a.get('name','')}：¥{bal:,.2f}")
                lines.append(f"合计：¥{total:,.2f}")
                result_label.text = "\n".join(lines)
            else:
                result_label.text = "暂无应收账款数据"

        elif any(kw in q for kw in ["应付", "应付账款", "欠供应商"]):
            accounts = get_account_balances(lid)
            ap_items = [a for a in accounts if a.get("code","").startswith("2202")]
            if ap_items:
                lines = ["📋 应付账款余额", "━━━━━━━━━━━━━━━━━━"]
                total = 0
                for a in ap_items:
                    bal = float(a.get("balance", 0))
                    total += bal
                    lines.append(f"{a.get('name','')}：¥{bal:,.2f}")
                lines.append(f"合计：¥{total:,.2f}")
                result_label.text = "\n".join(lines)
            else:
                result_label.text = "暂无应付账款数据"

        elif any(kw in q for kw in ["凭证", "单据", "分录"]):
            count = query_db("SELECT COUNT(*) as cnt FROM vouchers WHERE ledger_id=?", (lid,))
            month_count = query_db("SELECT COUNT(*) as cnt FROM vouchers WHERE ledger_id=? AND strftime('%Y-%m',date)=?",
                                  (lid, f"{state.selected_year}-{state.selected_month:02d}"))
            total_v = count[0]["cnt"] if count else 0
            month_v = month_count[0]["cnt"] if month_count else 0
            result_label.text = (f"📋 凭证统计\n"
                                  f"━━━━━━━━━━━━━━━━━━\n"
                                  f"本月凭证：{month_v} 张\n"
                                  f"总凭证数：{total_v} 张\n"
                                  f"会计期间：{state.selected_year}年{state.selected_month}月")

        else:
            result_label.text = ("暂不支持该查询，请尝试：\n"
                                  "• 上月利润是多少\n"
                                  "• 银行存款余额\n"
                                  "• 应收账款余额\n"
                                  "• 应付账款余额\n"
                                  "• 本月凭证数量")
    except Exception as e:
        result_label.text = f"查询出错：{str(e)}"


# ===== 财务知识库 =====
FINANCIAL_KNOWLEDGE = {
    "借贷记账法": "借贷记账法是会计的基本记账规则。'借'表示资产增加、负债减少；'贷'表示资产减少、负债增加。每笔业务都要有借有贷，借贷必相等。",
    "资产负债表": "资产负债表反映企业在某一时点的财务状况，遵循'资产=负债+所有者权益'的会计恒等式。",
    "利润表": "利润表反映企业在一定期间的经营成果。核心公式：收入-费用=利润。",
    "期初余额": "期初余额是会计科目在会计期间开始时的余额。资产类科目期初余额在借方，负债和权益类科目期初余额在贷方。",
    "期末结转": "期末结转是将损益类科目（收入、费用）的余额转入'本年利润'科目。结转后损益类科目余额为零。",
    "固定资产折旧": "固定资产折旧是将固定资产成本在其使用寿命内分摊。常用方法：直线法、双倍余额递减法、年数总和法。",
    "增值税": "增值税是对商品和服务增值部分征收的税。一般纳税人税率13%、9%、6%；小规模纳税人征收率3%。",
    "企业所得税": "企业所得税是对企业利润征收的税，基本税率25%。小微企业应纳税所得额300万以下实际税率5%。",
    "什么是凭证": "凭证是记录经济业务、明确经济责任的书面证明。分为原始凭证（发票、收据）和记账凭证（会计分录）。",
    "什么是科目": "会计科目是对会计要素的分类。分为资产类、负债类、权益类、成本类、损益类五大类。",
    "现金流量表": "现金流量表反映企业现金流入和流出，分为经营活动、投资活动、筹资活动三类。",
}

def _do_kb_query(query_text, result_label):
    """财务知识库查询"""
    if not query_text.strip():
        result_label.text = "输入关键词查询财务知识，如：借贷记账法、资产负债表、增值税..."
        return
    q = query_text.strip()
    # 精确匹配
    if q in FINANCIAL_KNOWLEDGE:
        result_label.text = FINANCIAL_KNOWLEDGE[q]
        return
    # 模糊匹配
    matches = [(k, v) for k, v in FINANCIAL_KNOWLEDGE.items() if q in k or k in q]
    if matches:
        result_label.text = "\n\n".join(f"📖 {k}\n{v}" for k, v in matches[:3])
        return
    # 关键词匹配
    keyword_map = {
        "借贷": "借贷记账法", "记账": "借贷记账法", "分录": "什么是凭证",
        "资产": "资产负债表", "负债": "资产负债表", "权益": "资产负债表",
        "利润": "利润表", "收入": "利润表", "费用": "利润表",
        "折旧": "固定资产折旧", "固定资产": "固定资产折旧",
        "税": "增值税", "增值税": "增值税", "所得税": "企业所得税",
        "凭证": "什么是凭证", "科目": "什么是科目",
        "期初": "期初余额", "结转": "期末结转",
    }
    for kw, topic in keyword_map.items():
        if kw in q:
            result_label.text = f"📖 {topic}\n{FINANCIAL_KNOWLEDGE.get(topic, '暂无相关信息')}"
            return
    result_label.text = "未找到相关知识，请尝试其他关键词：借贷记账法、资产负债表、利润表、增值税、折旧等"


# ===== 5. 系统设置 =====

