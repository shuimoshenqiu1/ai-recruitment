"""LLM适配层 - Ollama 本地模型适配器

Ollama 运行在本地，使用 /api/chat 端点，不需要 API Key。
适用于 llama3、qwen2、mistral 等本地部署的模型。
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
    LLMError,
    LLMProvider,
    LLMResponse,
    LLMTimeoutError,
    Message,
    extract_json_from_text,
)

logger = logging.getLogger(__name__)

# Ollama 默认地址
DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """
    Ollama 本地模型适配器。
    
    特点：
    - 运行在本地，无需 API Key
    - 使用 /api/chat 端点
    - 支持任意 Ollama 已拉取的模型 (llama3, qwen2, mistral, codellama 等)
    - 响应格式与 OpenAI 不同
    """

    def __init__(
        self,
        model_name: str = "llama3",
        endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
        api_key: str | None = None,  # Ollama 不需要，保留兼容签名
        **kwargs,
    ):
        super().__init__(endpoint=endpoint, api_key=api_key, model_name=model_name, **kwargs)
        self._timeout = kwargs.get("timeout", 120.0)  # 本地模型可能较慢
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def close(self) -> None:
        """关闭共享的httpx连接池"""
        if self._client:
            await self._client.aclose()

    def __del__(self):
        if hasattr(self, "_client") and self._client and not self._client.is_closed:
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                loop.create_task(self._client.aclose())
            except RuntimeError:
                pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((LLMTimeoutError, httpx.TimeoutException)),
        reraise=True,
    )
    async def chat_completion(
        self,
        messages: list[Message],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """调用 Ollama /api/chat 端点"""
        payload: dict = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        # Ollama 支持 format: "json" 来强制 JSON 输出
        if response_format and response_format.get("type") == "json_object":
            payload["format"] = "json"

        try:
            response = await self._client.post(
                f"{self.endpoint}/api/chat",
                json=payload,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"[ollama] 请求超时 (>{self._timeout}s)，模型可能正在加载",
                provider="ollama",
            ) from e
        except httpx.ConnectError as e:
            raise LLMError(
                f"[ollama] 连接失败，请确认 Ollama 正在运行: {e}",
                provider="ollama",
            ) from e

        if response.status_code != 200:
            try:
                body = response.json()
                error_msg = body.get("error", response.text)
            except Exception:
                error_msg = response.text
            raise LLMError(
                f"[ollama] 请求失败 ({response.status_code}): {error_msg}",
                provider="ollama",
                status_code=response.status_code,
            )

        data = response.json()

        # Ollama 响应格式:
        # {
        #   "model": "llama3",
        #   "message": {"role": "assistant", "content": "..."},
        #   "done": true,
        #   "total_duration": ...,
        #   "prompt_eval_count": N,
        #   "eval_count": N,
        # }
        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return LLMResponse(
            content=content,
            model=data.get("model", self.model_name),
            provider="ollama",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            raw_response=data,
        )

    async def chat_json(
        self,
        messages: list[Message],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Ollama JSON 模式。
        
        Ollama 原生支持 format: "json"，比纯 prompt 指令更可靠。
        """
        json_instruction = (
            "你必须以JSON格式输出响应。不要包含任何额外的解释文本，"
            "直接输出纯JSON对象。"
        )

        enhanced_messages = list(messages)
        if enhanced_messages and enhanced_messages[0].role == "system":
            enhanced_messages[0] = Message(
                role="system",
                content=f"{enhanced_messages[0].content}\n\n{json_instruction}",
            )
        else:
            enhanced_messages.insert(0, Message(role="system", content=json_instruction))

        response = await self.chat_completion(
            messages=enhanced_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},  # 触发 Ollama 的 format: "json"
        )

        return extract_json_from_text(response.content)

    async def health_check(self) -> bool:
        """检查 Ollama 服务是否运行且模型可用"""
        try:
            # 先检查服务是否在线
            resp = await self._client.get(f"{self.endpoint}/api/tags")
            if resp.status_code != 200:
                return False

            # 检查目标模型是否已拉取
            data = resp.json()
            available_models = [
                m.get("name", "").split(":")[0]
                for m in data.get("models", [])
            ]
            model_base = self.model_name.split(":")[0]
            if model_base not in available_models:
                logger.warning(
                    f"[ollama] 模型 '{self.model_name}' 未在本地找到。"
                    f"可用模型: {available_models}"
                )
                return False

            return True
        except Exception:
            return False
