"""岗位管理路由"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import Job
from app.models.user import User
from app.schemas.common import APIResponse, PageResponse
from app.schemas.job import JobCreate, JobResponse, JobStatusUpdate, JobUpdate

router = APIRouter()


@router.get("/", response_model=APIResponse)
async def list_jobs(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    status_filter: str | None = Query(default=None, alias="status", description="状态筛选"),
    keyword: str | None = Query(default=None, max_length=100, description="关键词搜索"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取岗位列表（分页+筛选）"""
    query = select(Job)
    count_query = select(func.count()).select_from(Job)

    # 非管理员只能看自己创建的岗位
    if current_user.role not in ("admin", "hr_manager"):
        query = query.where(Job.created_by == current_user.id)
        count_query = count_query.where(Job.created_by == current_user.id)

    # 状态筛选
    if status_filter:
        query = query.where(Job.status == status_filter)
        count_query = count_query.where(Job.status == status_filter)

    # 关键词搜索（标题/部门）
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.where(
            (Job.title.ilike(like_pattern)) | (Job.department.ilike(like_pattern))
        )
        count_query = count_query.where(
            (Job.title.ilike(like_pattern)) | (Job.department.ilike(like_pattern))
        )

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    jobs = result.scalars().all()

    items = [JobResponse.model_validate(j) for j in jobs]
    page_data = PageResponse.create(items=items, total=total, page=page, page_size=page_size)

    return APIResponse.success(data=page_data.model_dump())


@router.post("/", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建岗位"""
    job = Job(
        created_by=current_user.id,
        title=payload.title,
        department=payload.department,
        level=payload.level,
        headcount=payload.headcount,
        description=payload.description,
        requirements=payload.requirements.model_dump(),
        status="draft",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    return APIResponse.success(
        data=JobResponse.model_validate(job).model_dump(),
        message="岗位创建成功",
    )


@router.put("/{job_id}", response_model=APIResponse)
async def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新岗位信息（全量更新）"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")

    # 权限检查：只有创建者或管理员可以编辑
    if job.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权编辑此岗位")

    # 已关闭的岗位不允许编辑
    if job.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已关闭的岗位不可编辑")

    job.title = payload.title
    job.department = payload.department
    job.level = payload.level
    job.headcount = payload.headcount
    job.description = payload.description
    job.requirements = payload.requirements.model_dump()

    await db.flush()
    await db.refresh(job)

    return APIResponse.success(
        data=JobResponse.model_validate(job).model_dump(),
        message="岗位更新成功",
    )


@router.patch("/{job_id}/status", response_model=APIResponse)
async def update_job_status(
    job_id: uuid.UUID,
    payload: JobStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新岗位状态（发布/关闭）"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")

    # 权限检查
    if job.created_by != current_user.id and current_user.role not in ("admin", "hr_manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权变更此岗位状态")

    # 状态流转校验
    valid_transitions = {
        "draft": ["published", "closed"],
        "published": ["closed"],
        "closed": [],  # 关闭后不可再变更
    }
    if payload.status not in valid_transitions.get(job.status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的状态变更: {job.status} -> {payload.status}",
        )

    job.status = payload.status
    await db.flush()
    await db.refresh(job)

    return APIResponse.success(
        data=JobResponse.model_validate(job).model_dump(),
        message=f"岗位状态已更新为: {payload.status}",
    )
