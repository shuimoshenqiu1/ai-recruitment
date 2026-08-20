"""LLM适配层 - 统一抽象接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


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
        """
        ...

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
