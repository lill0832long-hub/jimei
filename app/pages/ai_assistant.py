"""AI 助手 — DeepSeek LLM 对话式财务助手"""
from nicegui import ui
from app.components.ui_components import SectionHeader
from app.components.state import state
from app.components.ui_helpers import show_toast
from app.services import LedgerService, ReportService, VoucherService

# ── LLM 服务（延迟加载） ──
_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        try:
            from app.services import llm_service
            _llm = llm_service
        except Exception as e:
            _llm = False
    return _llm if _llm is not False else None


# ── 财务工具定义（Function Calling） ──
FINANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_account_balance",
            "description": "查询指定科目或全部科目的余额",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_code": {
                        "type": "string",
                        "description": "科目编码，如 1001（库存现金）、1002（银行存款）。留空查询全部。"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_income_statement",
            "description": "查询利润表数据（收入、成本、利润）",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_balance_sheet",
            "description": "查询资产负债表数据",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_voucher",
            "description": "根据业务描述生成会计凭证分录",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "业务描述，如：收到客户货款10万元"
                    }
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_financials",
            "description": "分析当前期间的财务数据，检测异常并给出建议",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
]


def _execute_tool(tool_name, arguments):
    """执行 AI 调用的工具"""
    lid = state.selected_ledger_id
    if not lid:
        return {"error": "请先选择账套"}

    try:
        if tool_name == "query_account_balance":
            code = arguments.get("account_code", "")
            balances = ReportService.get_account_balances(
                lid, state.selected_year, state.selected_month
            )
            if code:
                balances = [b for b in balances if b.get("account_code", "").startswith(code)]
            result = []
            for b in balances[:20]:
                result.append({
                    "code": b.get("account_code", ""),
                    "name": b.get("account_name", ""),
                    "closing": round(float(b.get("closing_balance", 0) or 0), 2),
                })
            return {"balances": result, "period": f"{state.selected_year}年{state.selected_month}月"}

        elif tool_name == "query_income_statement":
            report = ReportService.get_income_statement(lid, state.selected_year, state.selected_month)
            if not report:
                return {"error": "暂无利润表数据"}
            rows = report.get("rows", []) if isinstance(report, dict) else []
            return {"rows": rows[:15], "date": report.get("date", "") if isinstance(report, dict) else ""}

        elif tool_name == "query_balance_sheet":
            bs = ReportService.get_balance_sheet(lid, state.selected_year, state.selected_month)
            if not bs:
                return {"error": "暂无资产负债表数据"}
            return {
                "total_assets": bs.get("total_assets", 0),
                "total_liab": bs.get("total_liab", 0),
                "total_equity": bs.get("total_equity", 0),
            }

        elif tool_name == "generate_voucher":
            desc = arguments.get("description", "")
            result = VoucherService.generate_from_text(lid, desc)
            return result

        elif tool_name == "analyze_financials":
            from app.services.analysis_service import analyze_period
            analysis = analyze_period(lid, state.selected_year, state.selected_month)
            return analysis

        else:
            return {"error": f"未知工具: {tool_name}"}
    except Exception as e:
        return {"error": str(e)}


# ── 对话历史（按账套存储） ──
_chat_histories = {}


def _get_history():
    lid = state.selected_ledger_id or "default"
    if lid not in _chat_histories:
        _chat_histories[lid] = []
    return _chat_histories[lid]


# ── 渲染 AI 助手页面 ──
def render_ai_assistant():
    """AI 助手 — 对话式交互"""
    llm = _get_llm()

    if not state.selected_ledger_id:
        ledgers = LedgerService.get_all()
        if ledgers:
            state.selected_ledger_id = ledgers[0]["id"]

    history = _get_history()

    # ── 页面布局 ──
    with ui.row().classes("w-full gap-3 no-wrap"):
        # 左侧：对话区
        with ui.column().classes("flex-1 gap-2 min-w-0"):
            # 状态栏
            with ui.card().classes("w-full"):
                with ui.row().classes("items-center gap-3 px-4 py-2"):
                    ui.icon("smart_toy", size="24px").classes("text-primary")
                    ui.label("AI 财务助手").classes("text-base font-bold")
                    ui.space()
                    if llm:
                        ok, msg = llm.check_connection()
                        if ok:
                            ui.icon("check_circle", size="16px").classes("text-green-5")
                            ui.label("DeepSeek 已连接").classes("text-xs text-green-6")
                        else:
                            ui.icon("error", size="16px").classes("text-red-5")
                            ui.label(msg[:30]).classes("text-xs text-red-6")
                    else:
                        ui.icon("cloud_off", size="16px").classes("text-grey-5")
                        ui.label("LLM 未配置").classes("text-xs text-grey-5")

            # 对话消息区
            chat_container = ui.column().classes("w-full gap-2").style(
                "max-height: calc(100vh - 260px); overflow-y: auto; padding: 8px;"
            )

            def _refresh_chat():
                chat_container.clear()
                with chat_container:
                    if not history:
                        with ui.card().classes("w-full bg-blue-50"):
                            with ui.column().classes("items-center gap-2 p-6"):
                                ui.icon("waving_hand", size="36px").classes("text-blue-4")
                                ui.label("你好！我是 AI 财务助手").classes("text-base font-bold text-blue-7")
                                ui.label("你可以问我财务问题，或让我帮你生成凭证").classes("text-sm text-grey-6")
                                with ui.row().classes("gap-2 mt-2 flex-wrap"):
                                    for hint in [
                                        "本月利润是多少？",
                                        "帮我记一笔办公费500元",
                                        "银行存款余额多少？",
                                        "资产负债表平衡吗？",
                                    ]:
                                        ui.button(hint, on_click=lambda h=hint: _send_message(h)) \
                                            .props("outline dense no-caps size-sm color=blue-7") \
                                            .classes("text-xs")
                    else:
                        for msg in history:
                            role = msg.get("role", "user")
                            content = msg.get("content", "")
                            if role == "user":
                                with ui.row().classes("w-full justify-end"):
                                    with ui.card().classes("bg-blue-600 text-white max-w-[75%]"):
                                        ui.label(content).classes("text-sm p-3 whitespace-pre-wrap")
                            elif role == "assistant":
                                with ui.row().classes("w-full"):
                                    with ui.card().classes("bg-grey-1 max-w-[75%]"):
                                        with ui.row().classes("items-center gap-1 px-3 pt-2"):
                                            ui.icon("smart_toy", size="16px").classes("text-primary")
                                            ui.label("AI").classes("text-xs font-bold text-primary")
                                        ui.label(content).classes("text-sm p-3 whitespace-pre-wrap text-grey-8")
                            elif role == "tool_result":
                                with ui.row().classes("w-full justify-center"):
                                    ui.label(f"📊 {content}").classes("text-xs text-grey-5 bg-grey-2 px-3 py-1 rounded")

                # 滚动到底部
                ui.run_javascript("document.querySelector('.flex-1.gap-2.min-w-0 > .gap-2:last-child')?.scrollIntoView({behavior:'smooth'})")

            _refresh_chat()

            # 输入区
            with ui.card().classes("w-full"):
                with ui.row().classes("items-end gap-2 p-3"):
                    msg_input = ui.textarea(placeholder="输入财务问题或业务描述...").props(
                        "outlined dense autogrow"
                    ).classes("flex-1").style("max-height: 120px;")
                    send_btn = ui.button(icon="send", color="primary") \
                        .props("round dense").classes("mb-1")

                    def _send_message(text=None):
                        user_msg = text or msg_input.value
                        if not user_msg or not user_msg.strip():
                            return
                        msg_input.value = ""
                        _do_chat(user_msg, history, chat_container, llm)

                    send_btn.on_click(lambda: _send_message())
                    msg_input.on("keydown", lambda e: _send_message() if e.args.get("key") == "Enter" and not e.args.get("shiftKey") else None)

        # 右侧：工具面板
        with ui.column().classes("w-72 gap-2"):
            # 快捷工具
            with ui.card().classes("w-full"):
                SectionHeader("快捷工具", icon="build")
                with ui.card_section().classes("gap-1.5"):
                    tools = [
                        ("📝 智能凭证", "描述业务自动生成分录", lambda: _send_message("帮我生成凭证：")),
                        ("🔍 查询余额", "查询科目余额", lambda: _send_message("查询银行存款余额")),
                        ("📊 利润分析", "查看本月利润情况", lambda: _send_message("本月利润是多少？")),
                        ("📋 资产负债", "查看资产负债表", lambda: _send_message("资产负债表平衡吗？")),
                        ("🔬 一键分析", "自动检测异常并给出建议", lambda: _send_message("请分析本月财务状况，检测异常并给出建议")),
                    ]
                    for label, desc, action in tools:
                        with ui.row().classes("items-center gap-2 cursor-pointer hover:bg-grey-2 p-2 rounded"):
                            ui.label(label).classes("text-sm font-semibold")
                            ui.label(desc).classes("text-xs text-grey-5")
                            ui.space()
                            ui.icon("arrow_forward", size="14px").classes("text-grey-4")
                            ui.row().classes("w-full").on("click", action)

            # 发票 OCR 上传
            with ui.card().classes("w-full"):
                SectionHeader("发票识别", icon="document_scanner")
                with ui.card_section().classes("gap-2"):
                    ui.label("上传发票图片，AI 自动识别并生成凭证").classes("text-xs text-grey-5")
                    upload = ui.upload(
                        label="上传发票图片",
                        on_upload=lambda e: _handle_ocr_upload(e, history, chat_container, llm),
                        auto_upload=True,
                    ).props("accept=.jpg,.jpeg,.png,.bmp flat dense no-caps").classes("w-full")
                    upload.props("color=orange")

            # 知识库快捷入口
            with ui.card().classes("w-full"):
                SectionHeader("知识库", icon="menu_book")
                with ui.card_section().classes("gap-1"):
                    try:
                        from app.services.knowledge_service import get_categories, get_by_category
                        cats = get_categories()
                        for cat in cats[:6]:
                            entries = get_by_category(cat)
                            with ui.column().classes("gap-0"):
                                ui.label(f"📂 {cat}").classes("text-xs font-bold text-grey-7 mt-1")
                                for entry in entries[:3]:
                                    ui.button(entry["title"],
                                              on_click=lambda t=entry["title"]: _send_message(f"解释一下{t}")) \
                                        .props("flat dense no-caps size-sm").classes("text-xs justify-start w-full text-left pl-4")
                    except Exception:
                        topics = ["借贷记账法", "资产负债表", "利润表", "增值税", "固定资产折旧", "期末结转"]
                        for topic in topics:
                            ui.button(topic, on_click=lambda t=topic: _send_message(f"解释一下{t}")) \
                                .props("flat dense no-caps size-sm").classes("text-xs justify-start w-full text-left")

            # 清空对话
            with ui.card().classes("w-full"):
                ui.button("清空对话历史", icon="delete_outline", color="red",
                          on_click=lambda: _clear_history(history, chat_container)) \
                    .props("flat dense no-caps").classes("w-full text-xs")


def _do_chat(user_msg, history, chat_container, llm):
    """处理对话消息"""
    # 添加用户消息
    history.append({"role": "user", "content": user_msg})
    _refresh_chat_ui(history, chat_container)

    if not llm:
        # 无 LLM — 使用旧的规则引擎
        _fallback_reply(user_msg, history, chat_container)
        return

    try:
        from app.services.llm_service import get_finance_prompt, chat

        # 构建消息
        messages = [{"role": "system", "content": get_finance_prompt(user_msg)}]
        for msg in history[-10:]:  # 最近 10 条上下文
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})

        # 调用 LLM（带工具）
        result = chat(messages, tools=FINANCE_TOOLS)

        # 处理工具调用
        if result.get("tool_calls"):
            for tc in result["tool_calls"]:
                fn_name = tc["function"]
                fn_args = tc["arguments"]
                tool_result = _execute_tool(fn_name, fn_args)
                history.append({
                    "role": "tool_result",
                    "content": f"调用 {fn_name} → {json.dumps(tool_result, ensure_ascii=False)[:200]}"
                })
                # 将工具结果发回 LLM
                messages.append({"role": "assistant", "content": None, "tool_calls": [{
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": fn_name, "arguments": json.dumps(fn_args)}
                }]})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })

            # 让 LLM 根据工具结果生成最终回复
            final = chat(messages)
            reply = final["content"]
        else:
            reply = result["content"]

        history.append({"role": "assistant", "content": reply})
        _refresh_chat_ui(history, chat_container)

    except Exception as e:
        history.append({"role": "assistant", "content": f"⚠️ AI 调用出错: {str(e)[:200]}"})
        _refresh_chat_ui(history, chat_container)


def _fallback_reply(user_msg, history, chat_container):
    """无 LLM 时的降级回复"""
    import re
    q = user_msg.strip().lower()
    lid = state.selected_ledger_id

    if any(kw in q for kw in ["利润", "盈利", "收益"]):
        try:
            report = ReportService.get_income_statement(lid, state.selected_year, state.selected_month)
            if report:
                reply = f"📊 {state.selected_year}年{state.selected_month}月利润表数据已获取，请在报表中心查看详细内容。"
            else:
                reply = "暂无利润表数据，请先录入凭证。"
        except:
            reply = "查询失败，请稍后重试。"
    elif any(kw in q for kw in ["余额", "存款", "现金", "资金"]):
        reply = "💰 请在「科目余额表」中查看各科目余额，或接入 LLM 后可直接对话查询。"
    elif "生成" in q or "凭证" in q:
        reply = "📝 智能凭证功能需要接入 LLM。请先配置 .env 中的 LLM_API_KEY。"
    else:
        reply = ("🤖 当前为离线模式，请配置 LLM 以获得完整 AI 能力。\n\n"
                 "配置方法：在 .env 文件中设置 LLM_API_KEY")

    history.append({"role": "assistant", "content": reply})
    _refresh_chat_ui(history, chat_container)


def _refresh_chat_ui(history, chat_container):
    """刷新聊天 UI"""
    chat_container.clear()
    with chat_container:
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                with ui.row().classes("w-full justify-end"):
                    with ui.card().classes("bg-blue-600 text-white max-w-[75%]"):
                        ui.label(content).classes("text-sm p-3 whitespace-pre-wrap")
            elif role == "assistant":
                with ui.row().classes("w-full"):
                    with ui.card().classes("bg-grey-1 max-w-[75%]"):
                        with ui.row().classes("items-center gap-1 px-3 pt-2"):
                            ui.icon("smart_toy", size="16px").classes("text-primary")
                            ui.label("AI").classes("text-xs font-bold text-primary")
                        ui.label(content).classes("text-sm p-3 whitespace-pre-wrap text-grey-8")
            elif role == "tool_result":
                with ui.row().classes("w-full justify-center"):
                    ui.label(f"📊 {content}").classes("text-xs text-grey-5")


def _clear_history(history, chat_container):
    """清空对话历史"""
    history.clear()
    _refresh_chat_ui(history, chat_container)
    show_toast("对话已清空", "info")


def _handle_ocr_upload(event, history, chat_container, llm):
    """处理发票图片上传"""
    import base64
    try:
        # 读取上传的图片
        file_data = event.content.read()
        file_name = event.name
        b64_data = base64.b64encode(file_data).decode("utf-8")
        
        # 获取 MIME 类型
        ext = file_name.lower().split(".")[-1] if "." in file_name else "jpeg"
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "bmp": "image/bmp"}
        mime = mime_map.get(ext, "image/jpeg")
        
        history.append({"role": "user", "content": f"📸 上传了发票图片: {file_name}"})
        _refresh_chat_ui(history, chat_container)
        
        if not llm:
            history.append({"role": "assistant", "content": "⚠️ OCR 功能需要 LLM 支持，请配置 DeepSeek API Key"})
            _refresh_chat_ui(history, chat_container)
            return
        
        from app.services.llm_service import get_finance_prompt, _get_client, MODEL, MAX_TOKENS, TEMPERATURE
        
        client = _get_client()
        
        # 使用 DeepSeek Vision 识别图片
        messages = [
            {"role": "system", "content": "你是一个发票识别助手。请仔细识别图片中的发票信息，包括：发票号码、开票日期、销售方、购买方、商品明细、金额、税额、价税合计。以结构化格式输出。如果是增值税发票，提取所有关键字段。"},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_data}"}},
                {"type": "text", "content": "请识别这张发票的所有信息，以结构化格式输出。然后根据发票内容建议会计分录。"}
            ]}
        ]
        
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=2048,
            temperature=0.1,
        )
        
        reply = resp.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        _refresh_chat_ui(history, chat_container)
        show_toast("发票识别完成", "success")
        
    except Exception as e:
        error_msg = str(e)[:200]
        if "vision" in error_msg.lower() or "image" in error_msg.lower():
            history.append({"role": "assistant", "content": f"⚠️ 当前模型不支持图片识别。请升级 deepseek-chat 或使用 deepseek-vl2 模型。\n错误: {error_msg}"})
        else:
            history.append({"role": "assistant", "content": f"⚠️ 图片识别失败: {error_msg}"})
        _refresh_chat_ui(history, chat_container)


import json
