"""CRUD操作 - 岗位"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.match_result import MatchResult
from app.schemas.job import JobCreate, JobUpdate


def _escape_like(value: str) -> str:
    """转义LIKE模式中的特殊字符（%, _, \\）"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def create_job(db: AsyncSession, job_in: JobCreate, user_id: uuid.UUID) -> Job:
    """
    创建岗位。

    Args:
        db: 数据库会话
        job_in: 岗位创建Schema
        user_id: 创建者ID

    Returns:
        创建的Job对象
    """
    job = Job(
        created_by=user_id,
        title=job_in.title,
        department=job_in.department,
        level=job_in.level,
        headcount=job_in.headcount,
        description=job_in.description,
        requirements=job_in.requirements.model_dump(),
        status="draft",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    """
    获取单个岗位。

    Args:
        db: 数据库会话
        job_id: 岗位ID

    Returns:
        Job对象或None
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def get_jobs(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    user_id: uuid.UUID | None = None,
    keyword: str | None = None,
) -> tuple[list[Job], int]:
    """
    获取岗位列表（含总数）。

    Args:
        db: 数据库会话
        skip: 偏移量
        limit: 每页数量
        status: 状态筛选
        user_id: 创建者ID筛选（非管理员场景）
        keyword: 关键词搜索（匹配标题/部门）

    Returns:
        (岗位列表, 总数)
    """
    base_filters: list = []

    if user_id is not None:
        base_filters.append(Job.created_by == user_id)

    if status:
        base_filters.append(Job.status == status)

    if keyword:
        like_pattern = f"%{_escape_like(keyword)}%"
        base_filters.append(
            (Job.title.ilike(like_pattern)) | (Job.department.ilike(like_pattern))
        )

    # 总数
    count_query = select(func.count()).select_from(Job)
    if base_filters:
        count_query = count_query.where(*base_filters)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    query = select(Job)
    if base_filters:
        query = query.where(*base_filters)
    query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    return jobs, total


async def update_job(db: AsyncSession, job: Job, job_in: JobUpdate) -> Job:
    """
    更新岗位信息（全量更新）。

    Args:
        db: 数据库会话
        job: 待更新的Job对象
        job_in: 更新数据Schema

    Returns:
        更新后的Job对象
    """
    job.title = job_in.title
    job.department = job_in.department
    job.level = job_in.level
    job.headcount = job_in.headcount
    job.description = job_in.description
    job.requirements = job_in.requirements.model_dump()

    await db.flush()
    await db.refresh(job)
    return job


async def update_job_status(db: AsyncSession, job: Job, new_status: str) -> Job:
    """
    更新岗位状态。

    Args:
        db: 数据库会话
        job: 待更新的Job对象
        new_status: 新状态

    Returns:
        更新后的Job对象
    """
    job.status = new_status
    await db.flush()
    await db.refresh(job)
    return job


async def delete_job(db: AsyncSession, job_id: uuid.UUID) -> bool:
    """
    删除岗位（仅草稿且无匹配结果时允许）。

    Args:
        db: 数据库会话
        job_id: 岗位ID

    Returns:
        是否删除成功

    Raises:
        ValueError: 岗位不存在、状态不允许或存在匹配结果
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise ValueError("岗位不存在")

    if job.status != "draft":
        raise ValueError("仅草稿状态的岗位可以删除")

    # 检查是否有匹配结果
    match_count_result = await db.execute(
        select(func.count()).select_from(MatchResult).where(MatchResult.job_id == job_id)
    )
    match_count = match_count_result.scalar() or 0
    if match_count > 0:
        raise ValueError("该岗位已有匹配结果，不可删除")

    await db.delete(job)
    await db.flush()
    return True
