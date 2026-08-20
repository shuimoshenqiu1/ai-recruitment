"""认证路由 - 登录/注册"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse

router = APIRouter()


@router.post("/register", response_model=APIResponse)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册。
    
    - 检查邮箱唯一性
    - 密码哈希存储
    - 返回JWT Token
    """
    # 检查邮箱是否已注册
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已被注册",
        )

    # 创建用户
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # 生成Token
    access_token = create_access_token(data={"sub": str(user.id)})
    token_data = Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )

    return APIResponse.success(data=token_data.model_dump(), message="注册成功")


@router.post("/login", response_model=APIResponse)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录。
    
    - 验证邮箱和密码
    - 返回JWT Token
    """
    # 查找用户
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 生成Token
    access_token = create_access_token(data={"sub": str(user.id)})
    token_data = Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )

    return APIResponse.success(data=token_data.model_dump(), message="登录成功")
