"""用户相关Schema"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """用户注册请求"""
    email: EmailStr = Field(description="邮箱地址")
    password: str = Field(min_length=8, max_length=128, description="密码，至少8位")
    name: str = Field(min_length=1, max_length=100, description="用户姓名")
    role: str = Field(
        default="hr_specialist",
        pattern=r"^(admin|hr_specialist|hr_manager|interviewer)$",
        description="用户角色",
    )


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
