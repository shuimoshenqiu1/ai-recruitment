"""用户CRUD操作"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """
    创建新用户。

    - 密码使用bcrypt哈希
    - 角色硬编码为 recruiter（C-2: 禁止客户端自选角色）
    - 返回完整的User ORM对象
    """
    user = User(
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        name=user_in.name,
        role="recruiter",  # 强制固定，不从客户端输入获取
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """根据邮箱查找用户"""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """根据ID查找用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
