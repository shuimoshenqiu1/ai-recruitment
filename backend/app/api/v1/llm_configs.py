"""LLM配置管理路由"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.database import get_db
from app.models.llm_config import LLMConfig
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.llm_config import LLMConfigCreate, LLMConfigResponse, LLMConfigUpdate

router = APIRouter()


def _to_response(config: LLMConfig) -> dict:
    """将LLMConfig模型转为响应字典（隐藏api_key明文）"""
    return {
        "id": config.id,
        "name": config.name,
        "provider_type": config.provider_type,
        "endpoint": config.endpoint,
        "api_key_set": config.api_key is not None and len(config.api_key) > 0,
        "model_name": config.model_name,
        "is_default": config.is_default,
        "is_active": config.is_active,
        "config": config.config,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.get("/", response_model=APIResponse)
async def list_llm_configs(
    current_user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """获取所有LLM配置列表（仅管理员/经理可见）"""
    result = await db.execute(
        select(LLMConfig).order_by(LLMConfig.is_default.desc(), LLMConfig.created_at.desc())
    )
    configs = result.scalars().all()
    items = [_to_response(c) for c in configs]

    return APIResponse.success(data=items)


@router.post("/", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    payload: LLMConfigCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """创建LLM配置（仅管理员）"""
    # 如果设为默认，先取消其他默认
    if payload.is_default:
        await _clear_default(db)

    config = LLMConfig(
        name=payload.name,
        provider_type=payload.provider_type,
        endpoint=payload.endpoint,
        api_key=payload.api_key,
        model_name=payload.model_name,
        is_default=payload.is_default,
        config=payload.config,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)

    return APIResponse.success(data=_to_response(config), message="LLM配置创建成功")


@router.put("/{config_id}", response_model=APIResponse)
async def update_llm_config(
    config_id: uuid.UUID,
    payload: LLMConfigUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """更新LLM配置（仅管理员）"""
    result = await db.execute(select(LLMConfig).where(LLMConfig.id == config_id))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM配置不存在")

    # 如果设为默认，先取消其他默认
    if payload.is_default and not config.is_default:
        await _clear_default(db)

    config.name = payload.name
    config.provider_type = payload.provider_type
    config.endpoint = payload.endpoint
    config.model_name = payload.model_name
    config.is_default = payload.is_default
    config.is_active = payload.is_active
    config.config = payload.config

    # api_key只在明确传值时更新（允许不修改密钥）
    if payload.api_key is not None:
        config.api_key = payload.api_key

    await db.flush()
    await db.refresh(config)

    return APIResponse.success(data=_to_response(config), message="LLM配置更新成功")


@router.post("/{config_id}/test", response_model=APIResponse)
async def test_llm_config(
    config_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """
    测试LLM配置连通性。
    
    向目标模型发送简单请求，验证API密钥和端点是否可用。
    """
    result = await db.execute(select(LLMConfig).where(LLMConfig.id == config_id))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM配置不存在")

    if not config.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该配置已禁用")

    # 动态加载对应的Provider进行健康检查
    from app.llm.openai_compatible import OpenAICompatibleProvider

    provider = OpenAICompatibleProvider(
        endpoint=config.endpoint,
        api_key=config.api_key,
        model_name=config.model_name,
    )

    try:
        is_healthy = await provider.health_check()
    except Exception as e:
        return APIResponse.error(message=f"连接测试失败: {str(e)}", code=-1)

    if is_healthy:
        return APIResponse.success(message="连接测试成功，模型服务可用")
    else:
        return APIResponse.error(message="连接测试失败，模型服务不可达", code=-1)


async def _clear_default(db: AsyncSession) -> None:
    """清除所有默认标记"""
    result = await db.execute(select(LLMConfig).where(LLMConfig.is_default.is_(True)))
    for config in result.scalars().all():
        config.is_default = False
