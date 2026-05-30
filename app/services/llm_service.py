"""LLM 服务 — 统一封装 DeepSeek / OpenAI 调用"""
import os
import json
import logging
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 加载 .env ──
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        # 手动解析 .env
        for line in _env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# ── 配置 ──
PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

# ── 全局客户端 ──
_client = None


def _get_client():
    global _client
    if _client is None:
        if not API_KEY:
            raise ValueError("LLM_API_KEY 未配置，请在 .env 文件中设置")
        from openai import OpenAI
        _client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    return _client


def chat(messages, tools=None, tool_choice="auto", temperature=None, max_tokens=None):
    """发送对话请求
    
    Args:
        messages: 消息列表 [{"role": "user", "content": "..."}]
        tools: 工具定义列表（function calling）
        tool_choice: 工具选择策略
        temperature: 温度（覆盖默认值）
        max_tokens: 最大 token（覆盖默认值）
    
    Returns:
        dict: {"content": str, "tool_calls": list|None, "usage": dict}
    """
    client = _get_client()
    kwargs = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature or TEMPERATURE,
        "max_tokens": max_tokens or MAX_TOKENS,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    try:
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        result = {
            "content": msg.content or "",
            "tool_calls": None,
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                "total_tokens": resp.usage.total_tokens if resp.usage else 0,
            },
        }
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ]
        return result
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        raise


def chat_simple(user_message, system_prompt=None):
    """简单对话（无工具）
    
    Args:
        user_message: 用户消息
        system_prompt: 系统提示词
    
    Returns:
        str: AI 回复文本
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})
    result = chat(messages)
    return result["content"]


def check_connection():
    """检查 LLM 连接是否正常
    
    Returns:
        tuple: (bool, str) — (是否成功, 信息)
    """
    try:
        if not API_KEY:
            return False, "API Key 未配置"
        result = chat_simple("你好，请用一句话回复。", "你是一个测试助手，简短回复。")
        return True, f"连接成功 — {MODEL} @ {BASE_URL}"
    except Exception as e:
        return False, f"连接失败: {e}"


# ── 财务专用 System Prompt ──
FINANCE_SYSTEM_PROMPT = """你是 AI 财务系统 V5.1 的专业财务助手。

## 能力
1. 根据业务描述自动生成会计分录（凭证）
2. 解答财务、会计、税务问题
3. 分析财务数据并给出经营建议
4. 解读财务报表

## 数据库结构（严格遵守，不得猜测）
- vouchers: 凭证主表 (id, voucher_no, date, description, total_debit, total_credit, status)
- journal_entries: 分录明细 (id, voucher_id, account_code, account_name, debit, credit, summary)
- accounts: 科目表 (id, code, name, category, parent_code)
- opening_balances: 期初余额 (account_code, year, month, balance)
注意：没有 voucher_lines 表，没有 dc 字段。分录使用 debit/credit 两列。

## 铁律（违反任何一条即为失败）
1. 只使用工具返回的数据，绝不编造、猜测、推断任何数字
2. 如果工具未返回数据，明确说"暂无数据"，不要杜撰
3. 引用数据时必须与工具返回值完全一致，不得修改
4. 不得假设数据库中不存在的表名或字段名
5. 报告中的数据必须来自工具查询结果
6. 生成凭证时借贷必须相等
7. 使用中国会计准则（CAS）
8. 回复使用中文
"""


def get_finance_prompt(user_query=None):
    """获取财务助手系统提示词（含知识库上下文和当前日期）
    
    Args:
        user_query: 用户查询，用于检索相关知识
    
    Returns:
        str: 系统提示词
    """
    today = datetime.date.today()
    weekdays = ['周一','周二','周三','周四','周五','周六','周日']
    date_line = f"\n## 当前日期\n今天是 {today.isoformat()}（{weekdays[today.weekday()]}）。报告必须使用此日期。\n"
    prompt = FINANCE_SYSTEM_PROMPT + date_line
    if user_query:
        try:
            from app.services.knowledge_service import get_context_for_llm
            ctx = get_context_for_llm(user_query)
            if ctx:
                prompt += "\n\n" + ctx
        except Exception:
            pass
    return prompt
