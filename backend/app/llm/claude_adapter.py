"""LLM适配层 - Anthropic Claude 适配器

Claude API 不兼容 OpenAI 格式，需要独立实现：
- 不同的认证方式 (x-api-key header)
- 不同的消息格式 (system 独立于 messages)
- 不同的响应结构
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

# Claude API 版本
ANTHROPIC_API_VERSION = "2023-06-01"


class ClaudeProvider(LLMProvider):
    """
    Anthropic Claude 适配器。
    
    Claude API 与 OpenAI 不兼容，主要区别：
    - 认证: x-api-key header (非 Bearer token)
    - system 消息作为顶层字段传递，不在 messages 数组中
    - 响应结构不同 (content[0].text)
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "claude-sonnet-4-20250514",
        endpoint: str = "https://api.anthropic.com/v1",
        **kwargs,
    ):
        super().__init__(endpoint=endpoint, api_key=api_key, model_name=model_name, **kwargs)
        self._timeout = kwargs.get("timeout", 90.0)
        self._api_version = kwargs.get("anthropic_version", ANTHROPIC_API_VERSION)
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

    def _build_headers(self) -> dict[str, str]:
        """构建 Claude API 请求头"""
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or "",
            "anthropic-version": self._api_version,
        }

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        """
        转换消息格式为 Claude API 格式。
        
        Claude 要求 system 消息独立于 messages 列表。
        messages 列表中的 role 只能是 'user' 或 'assistant'。
        
        Returns:
            (system_prompt, messages_list)
        """
        system_prompt: str | None = None
        claude_messages: list[dict] = []

        for msg in messages:
            if msg.role == "system":
                # 多个 system 消息合并
                if system_prompt is None:
                    system_prompt = msg.content
                else:
                    system_prompt += f"\n\n{msg.content}"
            elif msg.role in ("user", "assistant"):
                claude_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })
            else:
                # 未知 role 当作 user 处理
                logger.warning(f"Unknown message role '{msg.role}', treating as 'user'")
                claude_messages.append({
                    "role": "user",
                    "content": msg.content,
                })

        # Claude 要求 messages 不能为空，且第一条必须是 user
        if not claude_messages:
            claude_messages.append({"role": "user", "content": "hello"})

        return system_prompt, claude_messages

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
        """调用 Claude Messages API"""
        system_prompt, claude_messages = self._convert_messages(messages)

        payload: dict = {
            "model": self.model_name,
            "messages": claude_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = await self._client.post(
                f"{self.endpoint}/messages",
                headers=self._build_headers(),
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

        # Claude 响应格式: {"content": [{"type": "text", "text": "..."}], "usage": {...}}
        content_blocks = data.get("content", [])
        text_content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")

        usage = data.get("usage", {})

        return LLMResponse(
            content=text_content,
            model=data.get("model", self.model_name),
            provider=self.provider_type,
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
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
        Claude 的 JSON 模式。
        
        Claude 不支持 response_format 参数，通过 system prompt 指令引导。
        """
        from app.llm.base import extract_json_from_text

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

        # Claude 不支持 response_format，直接调用 chat_completion
        response = await self.chat_completion(
            messages=enhanced_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=None,
        )

        return extract_json_from_text(response.content)

    async def health_check(self) -> bool:
        """检查 Claude 服务可用性"""
        try:
            response = await self.chat_completion(
                messages=[Message(role="user", content="hi")],
                max_tokens=5,
            )
            return bool(response.content)
        except Exception:
            return False
