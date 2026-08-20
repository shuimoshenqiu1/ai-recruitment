"""匹配相关Schema"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    """执行匹配请求"""
    job_id: uuid.UUID = Field(description="岗位ID")
    resume_ids: list[uuid.UUID] = Field(
        min_length=1, max_length=50, description="简历ID列表，最多50个"
    )
    llm_config_id: uuid.UUID | None = Field(
        default=None, description="指定LLM配置ID，为空则使用默认配置"
    )


class MatchResultResponse(BaseModel):
    """匹配结果列表项"""
    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID
    overall_score: Decimal
    skill_score: Decimal | None = None
    experience_score: Decimal | None = None
    education_score: Decimal | None = None
    grade: str | None = None
    recommendation: str | None = None
    model_used: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchDetailResponse(BaseModel):
    """匹配结果详情（含完整分析）"""
    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID
    overall_score: Decimal
    skill_score: Decimal | None = None
    experience_score: Decimal | None = None
    education_score: Decimal | None = None
    grade: str | None = None
    recommendation: str | None = None
    details: dict | None = Field(default=None, description="LLM输出的详细分析结果")
    model_used: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchExportRequest(BaseModel):
    """导出匹配结果请求"""
    job_id: uuid.UUID = Field(description="岗位ID")
    min_score: Decimal | None = Field(default=None, ge=0, le=100, description="最低分数筛选")
    grades: list[str] | None = Field(default=None, description="筛选等级列表")
