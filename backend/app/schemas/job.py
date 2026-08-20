"""岗位相关Schema"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class JobRequirements(BaseModel):
    """岗位要求结构"""
    hard: list[str] = Field(default_factory=list, description="硬性要求（必须满足）")
    soft: list[str] = Field(default_factory=list, description="软性要求（加分项）")
    preferred: list[str] = Field(default_factory=list, description="优先条件")


class JobCreate(BaseModel):
    """创建岗位请求"""
    title: str = Field(min_length=1, max_length=200, description="岗位名称")
    department: str | None = Field(default=None, max_length=100, description="部门")
    level: str | None = Field(default=None, max_length=50, description="职级")
    headcount: int = Field(default=1, ge=1, description="招聘人数")
    description: str | None = Field(default=None, description="岗位描述")
    requirements: JobRequirements = Field(description="岗位要求")


class JobUpdate(BaseModel):
    """更新岗位请求（全量更新）"""
    title: str = Field(min_length=1, max_length=200, description="岗位名称")
    department: str | None = Field(default=None, max_length=100, description="部门")
    level: str | None = Field(default=None, max_length=50, description="职级")
    headcount: int = Field(default=1, ge=1, description="招聘人数")
    description: str | None = Field(default=None, description="岗位描述")
    requirements: JobRequirements = Field(description="岗位要求")


class JobStatusUpdate(BaseModel):
    """更新岗位状态"""
    status: str = Field(
        pattern=r"^(draft|published|closed)$",
        description="岗位状态：draft/published/closed",
    )


class JobResponse(BaseModel):
    """岗位详情响应"""
    id: uuid.UUID
    created_by: uuid.UUID
    title: str
    department: str | None = None
    level: str | None = None
    headcount: int
    status: str
    description: str | None = None
    requirements: JobRequirements
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
