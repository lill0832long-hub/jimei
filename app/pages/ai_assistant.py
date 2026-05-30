"""AI 助手 — DeepSeek LLM 对话式财务助手"""
import json
import asyncio
from nicegui import ui
from app.components.ui_components import SectionHeader
from app.components.state import state
from app.components.ui_helpers import show_toast
from app.services import LedgerService, ReportService, VoucherService
from pathlib import Path

# ── LLM 服务（延迟加载） ──
_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        try:
            from app.services import llm_service
            _llm = llm_service
        except Exception:
            _llm = False
    return _llm if _llm is not False else None


# ── 财务工具定义 ──
FINANCE_TOOLS = [
    {"type": "function", "function": {"name": "query_account_balance", "description": "查询科目余额", "parameters": {"type": "object", "properties": {"account_code": {"type": "string", "description": "科目编码，留空查全部"}}}}},
    {"type": "function", "function": {"name": "query_income_statement", "description": "查询利润表", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "query_balance_sheet", "description": "查询资产负债表", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "generate_voucher", "description": "根据业务描述生成凭证", "parameters": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}}},
    {"type": "function", "function": {"name": "analyze_financials", "description": "分析财务数据检测异常。注意：此工具仅包含有期初余额或本期发生额的科目，权益等长期科目可能缺失。验证会计恒等式时必须同时调用 query_balance_sheet", "parameters": {"type": "object", "properties": {}}}},
]


def _execute_tool(tool_name, arguments):
    lid = state.selected_ledger_id
    if not lid:
        return {"error": "请先选择账套"}
    y, m = state.selected_year, state.selected_month
    period_tag = {"query_period": f"{y}-{m:02d}", "ledger_id": lid}
    try:
        if tool_name == "query_account_balance":
            code = arguments.get("account_code", "")
            balances = ReportService.get_account_balances(lid, y, m)
            if code:
                balances = [b for b in balances if b.get("account_code", "").startswith(code)]
            result = {"balances": [{"code": b.get("account_code",""), "name": b.get("account_name",""), "category": b.get("category",""), "closing": round(float(b.get("closing_balance",0) or 0),2)} for b in balances[:30]]}
            result.update(period_tag)
            return result
        elif tool_name == "query_income_statement":
            report = ReportService.get_income_statement(lid, y, m)
            if report:
                report.update(period_tag)
            return report if report else {"error": "暂无数据"}
        elif tool_name == "query_balance_sheet":
            bs = ReportService.get_balance_sheet(lid, y, m)
            if not bs: return {"error": "暂无数据"}
            bs.update(period_tag)
            return bs
        elif tool_name == "generate_voucher":
            return VoucherService.generate_from_text(lid, arguments.get("description",""))
        elif tool_name == "analyze_financials":
            from app.services.analysis_service import analyze_period
            result = analyze_period(lid, y, m)
            if isinstance(result, dict):
                result.update(period_tag)
            return result
        return {"error": f"未知工具: {tool_name}"}
    except Exception as e:
        return {"error": str(e)}


# ── 对话历史持久化 ──
_HISTORY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "chat_history"
_chat_cache = {}

def _get_history():
    lid = state.selected_ledger_id or "default"
    if lid not in _chat_cache:
        _chat_cache[lid] = _load_history(lid)
    return _chat_cache[lid]

def _load_history(lid):
    try:
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return []
    fpath = _HISTORY_DIR / f"chat_{lid}.json"
    if fpath.exists():
        try:
            return json.loads(fpath.read_text(encoding="utf-8"))[-50:]
        except Exception:
            pass
    return []

def _save_history(lid, history):
    try:
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        fpath = _HISTORY_DIR / f"chat_{lid}.json"
        fpath.write_text(json.dumps(history[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── 渲染消息气泡（append 模式） ──
def _append_user_msg(container, content):
    with container:
        with ui.row().classes("w-full justify-end"):
            with ui.card().classes("bg-blue-600 text-white max-w-[75%]"):
                ui.label(content).classes("text-sm p-3 whitespace-pre-wrap")

def _append_ai_msg(container, content):
    with container:
        with ui.row().classes("w-full"):
            with ui.card().classes("bg-grey-1 max-w-[75%]"):
                with ui.row().classes("items-center gap-1 px-3 pt-2"):
                    ui.icon("smart_toy", size="16px").classes("text-primary")
                    ui.label("AI").classes("text-xs font-bold text-primary")
                ui.label(content).classes("text-sm p-3 whitespace-pre-wrap text-grey-8")

def _append_tool_msg(container, content):
    with container:
        with ui.row().classes("w-full justify-center"):
            ui.label(f"📊 {content}").classes("text-xs text-grey-5 bg-grey-2 px-3 py-1 rounded")

def _append_thinking(container):
    """添加"思考中"指示器，返回元素引用"""
    with container:
        row = ui.row().classes("w-full")
        with row:
            with ui.card().classes("bg-grey-1 max-w-[75%]"):
                with ui.row().classes("items-center gap-1 px-3 pt-2"):
                    ui.icon("smart_toy", size="16px").classes("text-primary")
                    ui.label("AI").classes("text-xs font-bold text-primary")
                with ui.row().classes("items-center gap-2 p-3"):
                    spinner = ui.spinner(size="sm", color="primary")
                    label = ui.label("正在思考...").classes("text-sm text-grey-5")
    return row


def _scroll_bottom():
    ui.run_javascript("document.querySelector('.chat-messages')?.scrollTo(0, 999999)")


# ── 主页面 ──
def render_ai_assistant():
    llm = _get_llm()

    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]

    history = _get_history()

    with ui.row().classes("w-full gap-3 no-wrap"):
        # ── 左侧：对话区 ──
        with ui.column().classes("flex-1 gap-2 min-w-0"):
            # 状态栏
            with ui.card().classes("w-full"):
                with ui.row().classes("items-center gap-3 px-4 py-2"):
                    ui.icon("smart_toy", size="24px").classes("text-primary")
                    ui.label("AI 财务助手").classes("text-base font-bold")
                    ui.space()
                    if llm:
                        provider = getattr(llm, "PROVIDER", "LLM")
                        model = getattr(llm, "MODEL", "")
                        ui.icon("check_circle", size="16px").classes("text-green-5")
                        ui.label(f"{provider} ({model})").classes("text-xs text-green-6")
                    else:
                        ui.icon("cloud_off", size="16px").classes("text-grey-5")
                        ui.label("LLM 未配置").classes("text-xs text-grey-5")

            # 消息区
            chat_box = ui.column().classes("w-full gap-2 chat-messages").style("max-height:calc(100vh - 260px);overflow-y:auto;padding:8px;")

            # 渲染历史消息
            with chat_box:
                if not history:
                    with ui.card().classes("w-full bg-blue-50"):
                        with ui.column().classes("items-center gap-2 p-6"):
                            ui.icon("waving_hand", size="36px").classes("text-blue-4")
                            ui.label("你好！我是 AI 财务助手").classes("text-base font-bold text-blue-7")
                            ui.label("你可以问我财务问题，或让我帮你生成凭证").classes("text-sm text-grey-6")
                else:
                    for msg in history:
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        if role == "user":
                            _append_user_msg(chat_box, content)
                        elif role == "assistant":
                            _append_ai_msg(chat_box, content)
                        elif role == "tool_result":
                            _append_tool_msg(chat_box, content)

            # 输入区
            with ui.card().classes("w-full"):
                with ui.row().classes("items-end gap-2 p-3"):
                    msg_input = ui.textarea(placeholder="输入财务问题，按 Enter 发送...").props("outlined dense autogrow").classes("flex-1").style("max-height:120px;")
                    send_btn = ui.button(icon="send", color="primary").props("round dense").classes("mb-1")

                    def _do_send(text=None):
                        raw = (text or "").strip()
                        if not raw:
                            return
                        msg_input.set_value("")
                        history.append({"role": "user", "content": raw})
                        _append_user_msg(chat_box, raw)
                        _scroll_bottom()
                        async def _bg():
                            await _ai_reply(raw, history, chat_box, llm)
                        ui.timer(0.1, lambda: _bg(), once=True)

                    # 统一的 JS 读值+清空+发送函数
                    async def _js_read_and_send():
                        try:
                            val = await ui.run_javascript(
                                "(() => { const el = document.querySelector('textarea'); "
                                "const v = el ? el.value.replace(/\\n/g,'').trim() : ''; "
                                "if(el) el.value=''; return v; })()")
                            if val:
                                _do_send(val)
                        except Exception:
                            pass

                    # Enter 键：阻止换行，用 ui.timer 保持上下文
                    def _on_keydown(e):
                        args = e.args or {}
                        if args.get("key") == "Enter" and not args.get("shiftKey"):
                            ui.timer(0, lambda: _js_read_and_send(), once=True)

                    msg_input.on("keydown", _on_keydown)

                    # 按钮：直接 async 读值（有上下文）
                    send_btn.on_click(_js_read_and_send)

        # ── 右侧：工具面板 ──
        with ui.column().classes("w-72 gap-2"):
            with ui.card().classes("w-full"):
                SectionHeader("快捷工具", icon="build")
                with ui.card_section().classes("gap-1.5"):
                    for label, desc, action in [
                        ("📝 智能凭证", "描述业务自动生成分录", lambda: _do_send("帮我生成凭证：")),
                        ("🔍 查询余额", "查询科目余额", lambda: _do_send("查询银行存款余额")),
                        ("📊 利润分析", "查看本月利润情况", lambda: _do_send("本月利润是多少？")),
                        ("📋 资产负债", "查看资产负债表", lambda: _do_send("资产负债表平衡吗？")),
                        ("🔬 一键分析", "自动检测异常并给出建议", lambda: _do_send("请分析本月财务状况，检测异常并给出建议")),
                    ]:
                        with ui.row().classes("items-center gap-2 cursor-pointer hover:bg-grey-2 p-2 rounded").on("click", action):
                            ui.label(label).classes("text-sm font-semibold")
                            ui.label(desc).classes("text-xs text-grey-5")
                            ui.space()
                            ui.icon("arrow_forward", size="14px").classes("text-grey-4")

            # 发票 OCR
            with ui.card().classes("w-full"):
                SectionHeader("发票识别", icon="document_scanner")
                with ui.card_section().classes("gap-2"):
                    ui.label("上传发票图片，AI 自动识别").classes("text-xs text-grey-5")
                    ui.upload(label="上传发票图片", auto_upload=True,
                              on_upload=lambda e: _do_send(f"[上传了发票: {e.name}]")
                    ).props("accept=.jpg,.jpeg,.png,.bmp flat dense no-caps color=orange").classes("w-full")

            # 知识库
            with ui.card().classes("w-full"):
                SectionHeader("知识库", icon="menu_book")
                with ui.card_section().classes("gap-1"):
                    try:
                        from app.services.knowledge_service import get_categories, get_by_category
                        for cat in get_categories()[:6]:
                            ui.label(f"📂 {cat}").classes("text-xs font-bold text-grey-7 mt-1")
                            for entry in get_by_category(cat)[:3]:
                                ui.button(entry["title"], on_click=lambda t=entry["title"]: _do_send(f"解释一下{t}")).props("flat dense no-caps size-sm").classes("text-xs justify-start w-full text-left pl-4")
                    except Exception:
                        for t in ["借贷记账法", "资产负债表", "增值税", "折旧"]:
                            ui.button(t, on_click=lambda x=t: _do_send(f"解释一下{x}")).props("flat dense no-caps size-sm").classes("text-xs justify-start w-full text-left")

            with ui.card().classes("w-full gap-1"):
                ui.button("压缩上下文", icon="compress", color="amber",
                          on_click=lambda: ui.timer(0.1, lambda: _compress_history(history, chat_box, llm), once=True)).props("flat dense no-caps").classes("w-full text-xs")
                ui.button("清空对话", icon="delete_outline", color="red",
                          on_click=lambda: _clear_all(history, chat_box)).props("flat dense no-caps").classes("w-full text-xs")


async def _ai_reply(user_msg, history, chat_box, llm):
    """后台异步获取 AI 回复"""
    thinking = _append_thinking(chat_box)
    _scroll_bottom()

    try:
        if not llm:
            reply = _fallback(user_msg)
        else:
            from app.services.llm_service import get_finance_prompt, chat
            messages = [{"role": "system", "content": get_finance_prompt(user_msg)}]
            for msg in history[-10:]:
                if msg["role"] in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

            result = chat(messages, tools=FINANCE_TOOLS)

            if result.get("tool_calls"):
                for tc in result["tool_calls"]:
                    fn_name = tc.get("function", "")
                    fn_args = tc.get("arguments", {})
                    tool_result = _execute_tool(fn_name, fn_args)
                    history.append({"role": "tool_result", "content": f"{fn_name} 查询完成"})
                    messages.append({"role": "assistant", "content": None, "tool_calls": [{"id": tc["id"], "type": "function", "function": {"name": fn_name, "arguments": json.dumps(fn_args)}}]})
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(tool_result, ensure_ascii=False)})
                final = chat(messages)
                reply = final["content"]
            else:
                reply = result["content"]
    except Exception as e:
        reply = f"⚠️ 出错: {str(e)[:200]}"

    # 移除思考指示器，显示回复
    thinking.delete()
    history.append({"role": "assistant", "content": reply})
    _save_history(state.selected_ledger_id or "default", history)
    _append_ai_msg(chat_box, reply)
    _scroll_bottom()


def _fallback(user_msg):
    """无 LLM 时的降级回复"""
    q = user_msg.lower()
    if any(kw in q for kw in ["利润", "盈利"]):
        return "📊 请在「报表中心 > 利润表」中查看，或配置 LLM 后直接对话查询。"
    elif any(kw in q for kw in ["余额", "存款", "现金"]):
        return "💰 请在「科目余额表」中查看各科目余额。"
    elif "生成" in q or "凭证" in q:
        return "📝 智能凭证功能需要配置 LLM（.env 中设置 LLM_API_KEY）。"
    elif "分析" in q:
        return "🔬 财务分析功能需要配置 LLM。"
    return "🤖 当前为离线模式，请在 .env 中配置 LLM_API_KEY 以获得完整 AI 能力。"


async def _compress_history(history, chat_box, llm):
    """用 LLM 总结旧消息，保留最近 5 条 + 摘要"""
    if len(history) < 8:
        show_toast("消息太少，无需压缩", "info")
        return
    old_msgs = history[:-5]
    recent = history[-5:]
    # 构建总结请求
    summary_text = "\n".join(f"{m['role']}: {m.get('content','')[:200]}" for m in old_msgs if m.get('content'))
    try:
        if llm:
            from app.services.llm_service import chat
            result = chat([
                {"role": "system", "content": "你是一个对话压缩助手。请将以下对话历史压缩为简洁的摘要，保留关键信息（如查询过的科目、生成过的凭证、分析结论等），控制在200字以内。"},
                {"role": "user", "content": summary_text}
            ])
            summary = result.get("content", "对话摘要生成失败")
        else:
            summary = f"（离线模式）已压缩 {len(old_msgs)} 条历史消息"
    except Exception as e:
        summary = f"摘要生成出错: {str(e)[:100]}"
    # 替换历史：摘要 + 最近5条
    history.clear()
    history.append({"role": "system", "content": f"📋 对话摘要：{summary}"})
    history.extend(recent)
    _save_history(state.selected_ledger_id or "default", history)
    # 重建 UI
    chat_box.clear()
    with chat_box:
        with ui.card().classes("w-full bg-amber-50"):
            with ui.row().classes("items-center gap-2 p-3"):
                ui.icon("compress", size="16px").classes("text-amber-7")
                ui.label(f"已压缩 {len(old_msgs)} 条消息").classes("text-sm text-amber-8")
            ui.label(summary).classes("text-xs text-grey-7 px-3 pb-2 whitespace-pre-wrap")
        for msg in recent:
            role, content = msg.get("role"), msg.get("content", "")
            if role == "user":
                _append_user_msg(chat_box, content)
            elif role == "assistant":
                _append_ai_msg(chat_box, content)
    show_toast(f"已压缩 {len(old_msgs)} 条消息", "positive")

def _clear_all(history, chat_box):
    history.clear()
    _save_history(state.selected_ledger_id or "default", history)
    chat_box.clear()
    with chat_box:
        with ui.card().classes("w-full bg-blue-50"):
            with ui.column().classes("items-center gap-2 p-6"):
                ui.icon("waving_hand", size="36px").classes("text-blue-4")
                ui.label("对话已清空，重新开始吧").classes("text-base font-bold text-blue-7")
    show_toast("对话已清空", "info")




