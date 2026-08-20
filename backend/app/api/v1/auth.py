"""认证路由 - 注册/登录/获取当前用户"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.crud.user import create_user, get_user_by_email
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse

router = APIRouter()

# H-3: 登录限频 - 基于客户端 IP，5次/分钟
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=APIResponse)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册。

    - 检查邮箱唯一性
    - 密码bcrypt哈希存储
    - 返回JWT Token + 用户信息
    """
    # 检查邮箱是否已注册
    existing_user = await get_user_by_email(db, payload.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已被注册",
        )

    # 创建用户
    user = await create_user(db, payload)

    # 生成Token（包含user_id和role）
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    token_data = Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )

    return APIResponse.success(data=token_data.model_dump(), message="注册成功")


@router.post("/login", response_model=APIResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录。

    - 验证邮箱和密码
    - 返回JWT Token + 用户信息
    - H-3: 限频 5次/分钟/IP，防止暴力破解
    """
    # 查找用户
    user = await get_user_by_email(db, payload.email)

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

    # 生成Token（包含user_id和role）
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    token_data = Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )

    return APIResponse.success(data=token_data.model_dump(), message="登录成功")


@router.get("/me", response_model=APIResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    获取当前登录用户信息。

    - 需要JWT认证（Bearer Token）
    - 返回当前用户的完整信息
    """
    user_data = UserResponse.model_validate(current_user)
    return APIResponse.success(data=user_data.model_dump(), message="获取成功")
