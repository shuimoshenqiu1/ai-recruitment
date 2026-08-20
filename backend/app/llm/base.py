"""LLM适配层 - 统一抽象接口"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProviderType(str, Enum):
    """支持的LLM提供商类型"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    MOONSHOT = "moonshot"
    ANTHROPIC = "anthropic"
    ZHIPU = "zhipu"
    OLLAMA = "ollama"


@dataclass
class Message:
    """聊天消息"""
    role: str  # system, user, assistant
    content: str


@dataclass
class LLMResponse:
    """LLM统一响应"""
    content: str
    model: str
    provider: str
    usage: dict = field(default_factory=dict)  # {prompt_tokens, completion_tokens, total_tokens}
    raw_response: dict | None = None


class LLMError(Exception):
    """LLM调用基础异常"""

    def __init__(self, message: str, provider: str = "", status_code: int | None = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(message)


class LLMAuthenticationError(LLMError):
    """认证失败 (401/403)"""
    pass


class LLMRateLimitError(LLMError):
    """速率限制 (429)"""
    pass


class LLMTimeoutError(LLMError):
    """请求超时"""
    pass


class LLMResponseParseError(LLMError):
    """响应解析失败"""
    pass


def extract_json_from_text(text: str) -> dict:
    """
    从LLM响应文本中提取JSON。
    
    处理以下情况：
    1. 纯JSON字符串
    2. markdown代码块包裹的JSON (```json ... ```)
    3. 带有前后文本的JSON对象/数组
    
    Raises:
        LLMResponseParseError: 无法从文本中提取有效JSON
    """
    # 1. 直接尝试解析
    text_stripped = text.strip()
    try:
        return json.loads(text_stripped)
    except json.JSONDecodeError:
        pass

    # 2. 尝试从 markdown 代码块提取
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    matches = re.findall(code_block_pattern, text_stripped, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # 3. 尝试找到第一个 { 或 [ 开始的JSON
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text_stripped.find(start_char)
        if start_idx == -1:
            continue
        # 从后向前找匹配的结束符
        end_idx = text_stripped.rfind(end_char)
        if end_idx <= start_idx:
            continue
        candidate = text_stripped[start_idx:end_idx + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise LLMResponseParseError(
        f"无法从LLM响应中提取有效JSON。响应前200字符: {text_stripped[:200]}"
    )


class LLMProvider(ABC):
    """
    LLM提供商统一抽象接口。
    
    所有模型适配器必须实现此接口，确保业务层无感切换模型。
    """

    def __init__(self, endpoint: str, api_key: str | None, model_name: str, **kwargs):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_name = model_name
        self.extra_config = kwargs

    async def close(self) -> None:
        """
        关闭提供商持有的资源（如HTTP连接池）。

        子类应覆盖此方法以释放 httpx.AsyncClient 等资源。
        基类默认实现为空操作，方便无需清理的子类。
        """
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """
        发送聊天补全请求。
        
        Args:
            messages: 消息列表
            temperature: 采样温度（0-2），简历解析建议0.1
            max_tokens: 最大输出token数
            response_format: 输出格式（如 {"type": "json_object"} 强制JSON输出）
        
        Returns:
            LLMResponse: 统一响应对象
            
        Raises:
            LLMAuthenticationError: API Key无效
            LLMRateLimitError: 触发速率限制
            LLMTimeoutError: 请求超时
            LLMError: 其他错误
        """
        ...

    async def chat_json(
        self,
        messages: list[Message],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """
        发送聊天请求并解析JSON响应。
        
        在system prompt中注入JSON输出指令，并从响应中提取JSON。
        
        Args:
            messages: 消息列表
            temperature: 采样温度，JSON输出建议较低值
            max_tokens: 最大输出token数
        
        Returns:
            dict: 解析后的JSON对象
            
        Raises:
            LLMResponseParseError: 无法从响应中提取JSON
        """
        # 注入JSON格式指令到系统消息
        json_instruction = (
            "你必须以JSON格式输出响应。不要包含任何额外的解释文本，"
            "不要使用markdown代码块包裹，直接输出纯JSON。"
        )
        
        enhanced_messages = list(messages)
        if enhanced_messages and enhanced_messages[0].role == "system":
            enhanced_messages[0] = Message(
                role="system",
                content=f"{enhanced_messages[0].content}\n\n{json_instruction}",
            )
        else:
            enhanced_messages.insert(0, Message(role="system", content=json_instruction))

        # 尝试使用 response_format（如果提供商支持）
        response = await self.chat_completion(
            messages=enhanced_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        return extract_json_from_text(response.content)

    @abstractmethod
    async def health_check(self) -> bool:
        """
        检查模型服务是否可用。
        
        Returns:
            bool: 服务是否健康
        """
        ...

    @property
    def provider_type(self) -> str:
        """返回提供商类型标识"""
        return self.__class__.__name__.replace("Provider", "").lower()
