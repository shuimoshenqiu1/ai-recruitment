"""用户相关Schema"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """用户注册请求 - 角色由服务端硬编码，不接受客户端输入"""
    email: EmailStr = Field(description="邮箱地址")
    password: str = Field(min_length=8, max_length=128, description="密码，至少8位")
    name: str = Field(min_length=1, max_length=100, description="用户姓名")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """H-2: 密码强度校验 - 至少包含大写、小写、数字、特殊字符"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含至少一个数字")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]", v):
            raise ValueError("密码必须包含至少一个特殊字符")
        return v


class AdminUserCreate(BaseModel):
    """管理员创建用户请求 - 仅 admin 接口使用（后续实现）"""
    email: EmailStr = Field(description="邮箱地址")
    password: str = Field(min_length=8, max_length=128, description="密码，至少8位")
    name: str = Field(min_length=1, max_length=100, description="用户姓名")
    role: str = Field(
        default="recruiter",
        pattern=r"^(admin|hr_manager|recruiter|interviewer)$",
        description="用户角色",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """密码强度校验"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含至少一个数字")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]", v):
            raise ValueError("密码必须包含至少一个特殊字符")
        return v


class UserLogin(BaseModel):
    """用户登录请求"""
    email: EmailStr = Field(description="邮箱地址")
    password: str = Field(min_length=1, description="密码")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: uuid.UUID
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """JWT Token响应"""
    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: UserResponse = Field(description="用户信息")
