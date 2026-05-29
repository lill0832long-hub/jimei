"""LLM 服务 — 统一封装 DeepSeek / OpenAI 调用"""
import os
import json
import logging
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
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
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
FINANCE_SYSTEM_PROMPT = """你是一个专业的 AI 财务助手，服务于"AI 财务系统 V5.1"。

你的能力：
1. 根据业务描述自动生成会计分录（凭证）
2. 解答财务、会计、税务相关问题
3. 分析财务数据并给出经营建议
4. 解读财务报表（资产负债表、利润表等）

规则：
- 生成凭证时，确保借贷必相等
- 使用中国会计准则（CAS）
- 金额精确到分（两位小数）
- 回复使用中文，简洁专业
- 不确定时说明理由，不要编造数据

你可以通过工具查询系统中的实际财务数据来辅助回答。
"""


def get_finance_prompt():
    """获取财务助手系统提示词"""
    return FINANCE_SYSTEM_PROMPT
