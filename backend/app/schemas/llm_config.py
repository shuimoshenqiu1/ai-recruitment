"""LLM配置相关Schema"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LLMConfigCreate(BaseModel):
    """创建LLM配置"""
    name: str = Field(min_length=1, max_length=100, description="配置名称")
    provider_type: str = Field(
        pattern=r"^(openai|deepseek|moonshot|anthropic|zhipu|ollama)$",
        description="提供商类型",
    )
    endpoint: str = Field(min_length=1, max_length=500, description="API端点URL")
    api_key: str | None = Field(default=None, max_length=500, description="API密钥")
    model_name: str = Field(min_length=1, max_length=100, description="模型名称")
    is_default: bool = Field(default=False, description="是否为默认配置")
    config: dict | None = Field(
        default=None,
        description="额外配置：temperature, max_tokens等",
    )


class LLMConfigUpdate(BaseModel):
    """更新LLM配置"""
    name: str = Field(min_length=1, max_length=100, description="配置名称")
    provider_type: str = Field(
        pattern=r"^(openai|deepseek|moonshot|anthropic|zhipu|ollama)$",
        description="提供商类型",
    )
    endpoint: str = Field(min_length=1, max_length=500, description="API端点URL")
    api_key: str | None = Field(default=None, max_length=500, description="API密钥")
    model_name: str = Field(min_length=1, max_length=100, description="模型名称")
    is_default: bool = Field(default=False, description="是否为默认配置")
    is_active: bool = Field(default=True, description="是否启用")
    config: dict | None = Field(default=None, description="额外配置")


class LLMConfigResponse(BaseModel):
    """LLM配置响应（不返回api_key明文）"""
    id: uuid.UUID
    name: str
    provider_type: str
    endpoint: str
    api_key_set: bool = Field(description="是否已设置API密钥")
    model_name: str
    is_default: bool
    is_active: bool
    config: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
