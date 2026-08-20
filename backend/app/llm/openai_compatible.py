"""LLM适配层 - OpenAI兼容协议提供商

覆盖：OpenAI (GPT)、DeepSeek、Moonshot (Kimi)、Zhipu (GLM)
这些提供商均兼容OpenAI API协议，只需不同的endpoint和api_key。
"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.llm.base import LLMProvider, LLMResponse, Message


class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI兼容协议的通用提供商。
    
    适用于所有实现了 OpenAI Chat Completions API 的服务：
    - OpenAI: https://api.openai.com/v1
    - DeepSeek: https://api.deepseek.com/v1
    - Moonshot: https://api.moonshot.cn/v1
    - Zhipu: https://open.bigmodel.cn/api/paas/v4
    """

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def chat_completion(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """调用OpenAI兼容的Chat Completion API"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.endpoint}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model_name),
            provider=self.provider_type,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            raw_response=data,
        )

    async def health_check(self) -> bool:
        """通过发送最小请求检查服务可用性"""
        try:
            response = await self.chat_completion(
                messages=[Message(role="user", content="hi")],
                max_tokens=5,
            )
            return bool(response.content)
        except Exception:
            return False


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI GPT 系列"""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", **kwargs):
        super().__init__(
            endpoint="https://api.openai.com/v1",
            api_key=api_key,
            model_name=model_name,
            **kwargs,
        )


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek 系列"""

    def __init__(self, api_key: str, model_name: str = "deepseek-chat", **kwargs):
        super().__init__(
            endpoint="https://api.deepseek.com/v1",
            api_key=api_key,
            model_name=model_name,
            **kwargs,
        )


class MoonshotProvider(OpenAICompatibleProvider):
    """Moonshot Kimi 系列"""

    def __init__(self, api_key: str, model_name: str = "moonshot-v1-8k", **kwargs):
        super().__init__(
            endpoint="https://api.moonshot.cn/v1",
            api_key=api_key,
            model_name=model_name,
            **kwargs,
        )


class ZhipuProvider(OpenAICompatibleProvider):
    """智谱 GLM 系列"""

    def __init__(self, api_key: str, model_name: str = "glm-4", **kwargs):
        super().__init__(
            endpoint="https://open.bigmodel.cn/api/paas/v4",
            api_key=api_key,
            model_name=model_name,
            **kwargs,
        )
