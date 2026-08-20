"""简历相关Schema"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ResumeUpload(BaseModel):
    """简历上传元信息（文件通过Form上传，此处记录业务属性）"""
    candidate_name: str | None = Field(default=None, max_length=100, description="候选人姓名")
    candidate_email: str | None = Field(default=None, max_length=255, description="候选人邮箱")
    candidate_phone: str | None = Field(default=None, max_length=50, description="候选人电话")


class ParsedResumeData(BaseModel):
    """LLM解析后的结构化简历数据"""
    name: str | None = Field(default=None, description="姓名")
    email: str | None = Field(default=None, description="邮箱")
    phone: str | None = Field(default=None, description="电话")
    education: list[dict] = Field(default_factory=list, description="教育经历")
    work_experience: list[dict] = Field(default_factory=list, description="工作经历")
    skills: list[str] = Field(default_factory=list, description="技能列表")
    certifications: list[str] = Field(default_factory=list, description="证书")
    languages: list[str] = Field(default_factory=list, description="语言能力")
    summary: str | None = Field(default=None, description="个人摘要")
    years_of_experience: int | None = Field(default=None, ge=0, description="总工作年限")


class ResumeResponse(BaseModel):
    """简历详情响应"""
    id: uuid.UUID
    uploaded_by: uuid.UUID
    file_name: str
    file_type: str
    file_size: int
    parse_status: str
    parsed_data: ParsedResumeData | None = None
    candidate_name: str | None = None
    candidate_email: str | None = None
    candidate_phone: str | None = None
    parse_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeUploadResult(BaseModel):
    """单个简历上传结果"""
    resume_id: uuid.UUID
    file_name: str
    parse_status: str


class BatchUploadFileResult(BaseModel):
    """批量上传中单个文件的处理结果"""
    file_name: str
    success: bool
    resume_id: uuid.UUID | None = None
    error: str | None = None


class BatchUploadResponse(BaseModel):
    """批量上传响应"""
    total: int = Field(description="提交总数")
    success_count: int = Field(description="成功数量")
    failed_count: int = Field(description="失败数量")
    results: list[BatchUploadFileResult] = Field(description="逐文件结果")
