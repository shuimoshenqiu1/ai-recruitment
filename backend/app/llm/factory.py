"""LLM适配层 - 适配器工厂

根据 provider 名称创建对应的 LLM 适配器实例。
支持动态注册新的适配器。
"""

from __future__ import annotations

from app.llm.base import LLMProvider, ProviderType
from app.llm.claude_adapter import ClaudeProvider
from app.llm.ollama_adapter import OllamaProvider
from app.llm.openai_compatible import (
    DeepSeekProvider,
    MoonshotProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    ZhipuProvider,
)


class LLMFactory:
    """
    LLM适配器工厂。
    
    通过 provider 名称创建对应的适配器实例。
    所有 OpenAI 兼容的提供商（DeepSeek、Kimi、GLM）使用各自的子类，
    它们预设了 endpoint，只需传入 api_key 和可选的 model_name。
    
    Usage:
        adapter = LLMFactory.create("openai", api_key="sk-...", model_name="gpt-4o")
        adapter = LLMFactory.create("deepseek", api_key="sk-...")
        adapter = LLMFactory.create("ollama", model_name="llama3")
    """

    _adapters: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, provider: str, adapter_class: type[LLMProvider]) -> None:
        """注册一个适配器类"""
        cls._adapters[provider] = adapter_class

    @classmethod
    def create(cls, provider: str, **kwargs) -> LLMProvider:
        """
        根据 provider 名称创建适配器实例。
        
        Args:
            provider: 提供商标识 (openai, deepseek, moonshot, zhipu, claude, ollama)
            **kwargs: 传递给适配器构造函数的参数
                - api_key: API密钥（ollama 可省略）
                - model_name: 模型名称
                - endpoint: 自定义端点（覆盖默认值）
                - timeout: 请求超时秒数
                
        Returns:
            LLMProvider: 适配器实例
            
        Raises:
            ValueError: 未知的 provider
        """
        if provider not in cls._adapters:
            available = list(cls._adapters.keys())
            raise ValueError(
                f"Unknown provider: '{provider}'. "
                f"Available providers: {available}"
            )
        return cls._adapters[provider](**kwargs)

    @classmethod
    def available_providers(cls) -> list[str]:
        """返回所有已注册的 provider 名称"""
        return list(cls._adapters.keys())

    @classmethod
    def is_registered(cls, provider: str) -> bool:
        """检查 provider 是否已注册"""
        return provider in cls._adapters


# === 注册所有内置适配器 ===

# OpenAI 兼容系列
LLMFactory.register(ProviderType.OPENAI, OpenAIProvider)
LLMFactory.register(ProviderType.DEEPSEEK, DeepSeekProvider)
LLMFactory.register(ProviderType.MOONSHOT, MoonshotProvider)
LLMFactory.register(ProviderType.ZHIPU, ZhipuProvider)

# Anthropic Claude
LLMFactory.register(ProviderType.ANTHROPIC, ClaudeProvider)

# 本地 Ollama
LLMFactory.register(ProviderType.OLLAMA, OllamaProvider)
