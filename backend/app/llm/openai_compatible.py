"""LLM适配层 - OpenAI兼容协议提供商

覆盖：OpenAI (GPT)、DeepSeek、Moonshot (Kimi)、Zhipu (GLM)
这些提供商均兼容OpenAI API协议，只需不同的endpoint和api_key。
"""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.llm.base import (
    LLMAuthenticationError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    Message,
)

logger = logging.getLogger(__name__)


def _should_retry(exc: BaseException) -> bool:
    """判断异常是否应该重试"""
    if isinstance(exc, LLMTimeoutError):
        return True
    if isinstance(exc, LLMRateLimitError):
        return True
    if isinstance(exc, httpx.TimeoutException):
        return True
    return False


class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI兼容协议的通用提供商。
    
    适用于所有实现了 OpenAI Chat Completions API 的服务：
    - OpenAI: https://api.openai.com/v1
    - DeepSeek: https://api.deepseek.com/v1
    - Moonshot: https://api.moonshot.cn/v1
    - Zhipu: https://open.bigmodel.cn/api/paas/v4
    """

    def __init__(self, endpoint: str, api_key: str | None, model_name: str, **kwargs):
        super().__init__(endpoint=endpoint, api_key=api_key, model_name=model_name, **kwargs)
        self._timeout = kwargs.get("timeout", 60.0)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def close(self) -> None:
        """关闭共享的httpx连接池"""
        if self._client:
            await self._client.aclose()

    def __del__(self):
        # 安全关闭：如果事件循环仍在运行则忽略
        if hasattr(self, "_client") and self._client and not self._client.is_closed:
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                loop.create_task(self._client.aclose())
            except RuntimeError:
                pass

    def _handle_http_error(self, response: httpx.Response) -> None:
        """根据HTTP状态码抛出对应的异常"""
        status = response.status_code
        try:
            body = response.json()
            error_msg = body.get("error", {}).get("message", response.text)
        except Exception:
            error_msg = response.text

        provider = self.provider_type

        if status in (401, 403):
            raise LLMAuthenticationError(
                f"[{provider}] 认证失败: {error_msg}",
                provider=provider,
                status_code=status,
            )
        elif status == 429:
            raise LLMRateLimitError(
                f"[{provider}] 速率限制: {error_msg}",
                provider=provider,
                status_code=status,
            )
        elif status >= 500:
            raise LLMError(
                f"[{provider}] 服务端错误 ({status}): {error_msg}",
                provider=provider,
                status_code=status,
            )
        else:
            raise LLMError(
                f"[{provider}] 请求失败 ({status}): {error_msg}",
                provider=provider,
                status_code=status,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((LLMTimeoutError, LLMRateLimitError, httpx.TimeoutException)),
        reraise=True,
    )
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

        payload: dict = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            payload["response_format"] = response_format

        try:
            response = await self._client.post(
                f"{self.endpoint}/chat/completions",
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"[{self.provider_type}] 请求超时 (>{self._timeout}s)",
                provider=self.provider_type,
            ) from e
        except httpx.ConnectError as e:
            raise LLMError(
                f"[{self.provider_type}] 连接失败: {e}",
                provider=self.provider_type,
            ) from e

        if response.status_code != 200:
            self._handle_http_error(response)

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


class ModelScopeProvider(OpenAICompatibleProvider):
    """魔搭社区（ModelScope）推理API — OpenAI兼容协议"""

    def __init__(self, api_key: str, model_name: str = "Qwen/Qwen2.5-72B-Instruct", **kwargs):
        super().__init__(
            endpoint="https://api-inference.modelscope.cn/v1",
            api_key=api_key,
            model_name=model_name,
            **kwargs,
        )
