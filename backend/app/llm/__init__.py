"""LLM多模型适配层

提供统一的LLM调用接口，支持多种模型提供商的无缝切换。

支持的提供商：
- OpenAI (GPT-4o, GPT-4, GPT-3.5)
- DeepSeek (deepseek-chat, deepseek-coder)
- Moonshot/Kimi (moonshot-v1-8k/32k/128k)
- 智谱/GLM (glm-4, glm-4-flash)
- Anthropic Claude (claude-sonnet-4-20250514, claude-3-haiku)
- Ollama 本地模型 (llama3, qwen2, mistral)

Usage:
    from app.llm import LLMFactory, Message, LLMResponse

    # 创建适配器
    llm = LLMFactory.create("openai", api_key="sk-...", model_name="gpt-4o")
    
    # 发送请求
    response = await llm.chat_completion([
        Message(role="system", content="你是一个助手"),
        Message(role="user", content="你好"),
    ])
    
    # JSON模式
    result = await llm.chat_json([
        Message(role="user", content="列出3种编程语言，以JSON数组返回"),
    ])
"""

from app.llm.base import (
    LLMAuthenticationError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseParseError,
    LLMTimeoutError,
    Message,
    ProviderType,
    extract_json_from_text,
)
from app.llm.claude_adapter import ClaudeProvider
from app.llm.factory import LLMFactory
from app.llm.ollama_adapter import OllamaProvider
from app.llm.openai_compatible import (
    DeepSeekProvider,
    MoonshotProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    ZhipuProvider,
)

__all__ = [
    # 核心抽象
    "LLMProvider",
    "LLMFactory",
    "LLMResponse",
    "Message",
    "ProviderType",
    # 异常
    "LLMError",
    "LLMAuthenticationError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMResponseParseError",
    # 具体适配器
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "DeepSeekProvider",
    "MoonshotProvider",
    "ZhipuProvider",
    "ClaudeProvider",
    "OllamaProvider",
    # 工具函数
    "extract_json_from_text",
]
