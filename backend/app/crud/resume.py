"""CRUD操作 - 简历"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume


async def create_resume(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    file_name: str,
    file_path: str,
    file_type: str,
    file_size: int,
    candidate_name: str | None = None,
    candidate_email: str | None = None,
    candidate_phone: str | None = None,
) -> Resume:
    """
    创建简历记录。

    Args:
        db: 数据库会话
        user_id: 上传者ID
        file_name: 原始文件名
        file_path: 存储路径
        file_type: 文件扩展名
        file_size: 文件大小（字节）
        candidate_name: 候选人姓名（可选）
        candidate_email: 候选人邮箱（可选）
        candidate_phone: 候选人电话（可选）

    Returns:
        创建的Resume对象
    """
    resume = Resume(
        uploaded_by=user_id,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone,
        parse_status="pending",
        is_deleted=False,
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)
    return resume


async def get_resume(
    db: AsyncSession,
    resume_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> Resume | None:
    """
    获取单个简历记录。

    Args:
        db: 数据库会话
        resume_id: 简历ID
        user_id: 用户ID（如果提供则校验归属权）

    Returns:
        Resume对象或None
    """
    query = select(Resume).where(
        Resume.id == resume_id,
        Resume.is_deleted == False,  # noqa: E712
    )
    if user_id is not None:
        query = query.where(Resume.uploaded_by == user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_resumes(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
) -> tuple[list[Resume], int]:
    """
    获取简历列表（分页）。

    Args:
        db: 数据库会话
        user_id: 用户ID
        skip: 偏移量
        limit: 每页数量
        status: 解析状态筛选

    Returns:
        (简历列表, 总数)
    """
    base_filter = [
        Resume.uploaded_by == user_id,
        Resume.is_deleted == False,  # noqa: E712
    ]

    if status:
        base_filter.append(Resume.parse_status == status)

    # 查总数
    count_query = select(func.count()).select_from(Resume).where(*base_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    query = (
        select(Resume)
        .where(*base_filter)
        .order_by(Resume.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    resumes = list(result.scalars().all())

    return resumes, total


async def update_resume_status(
    db: AsyncSession,
    resume_id: uuid.UUID,
    status: str,
    *,
    parse_error: str | None = None,
    parsed_data: dict | None = None,
) -> Resume | None:
    """
    更新简历解析状态。

    Args:
        db: 数据库会话
        resume_id: 简历ID
        status: 新状态（pending/parsing/completed/failed）
        parse_error: 解析错误信息（仅failed状态）
        parsed_data: 解析结果数据（仅completed状态）

    Returns:
        更新后的Resume对象或None
    """
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        return None

    resume.parse_status = status
    resume.updated_at = datetime.now(timezone.utc)

    if parse_error is not None:
        resume.parse_error = parse_error

    if parsed_data is not None:
        resume.parsed_data = parsed_data
        # 同步候选人信息
        if parsed_data.get("name"):
            resume.candidate_name = parsed_data["name"]
        if parsed_data.get("email"):
            resume.candidate_email = parsed_data["email"]
        if parsed_data.get("phone"):
            resume.candidate_phone = parsed_data["phone"]

    await db.flush()
    await db.refresh(resume)
    return resume


async def soft_delete_resume(
    db: AsyncSession,
    resume_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """
    软删除简历。

    Args:
        db: 数据库会话
        resume_id: 简历ID
        user_id: 用户ID（权限校验）

    Returns:
        是否删除成功
    """
    result = await db.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.uploaded_by == user_id,
            Resume.is_deleted == False,  # noqa: E712
        )
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        return False

    resume.is_deleted = True
    resume.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return True
