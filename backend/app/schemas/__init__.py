"""Pydantic数据验证模型"""

from app.schemas.common import APIResponse, PageParams, PageResponse
from app.schemas.user import AdminUserCreate, Token, UserCreate, UserLogin, UserResponse
from app.schemas.resume import (
    BatchUploadFileResult,
    BatchUploadResponse,
    ParsedResumeData,
    ResumeResponse,
    ResumeUpload,
    ResumeUploadResult,
)
from app.schemas.job import JobCreate, JobRequirements, JobResponse, JobUpdate
from app.schemas.matching import MatchDetailResponse, MatchRequest, MatchResultResponse
from app.schemas.llm_config import LLMConfigCreate, LLMConfigResponse, LLMConfigUpdate

__all__ = [
    "APIResponse",
    "PageParams",
    "PageResponse",
    "AdminUserCreate",
    "Token",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "ResumeUpload",
    "ResumeResponse",
    "ResumeUploadResult",
    "ParsedResumeData",
    "BatchUploadFileResult",
    "BatchUploadResponse",
    "JobCreate",
    "JobUpdate",
    "JobResponse",
    "JobRequirements",
    "MatchRequest",
    "MatchResultResponse",
    "MatchDetailResponse",
    "LLMConfigCreate",
    "LLMConfigUpdate",
    "LLMConfigResponse",
]
