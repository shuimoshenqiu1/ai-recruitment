"""岗位管理路由"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import job as job_crud
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
    # 非管理员只能看自己创建的岗位
    user_id = (
        None if current_user.role in ("admin", "hr_manager") else current_user.id
    )

    offset = (page - 1) * page_size
    jobs, total = await job_crud.get_jobs(
        db,
        skip=offset,
        limit=page_size,
        status=status_filter,
        user_id=user_id,
        keyword=keyword,
    )

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
    job = await job_crud.create_job(db, job_in=payload, user_id=current_user.id)

    return APIResponse.success(
        data=JobResponse.model_validate(job).model_dump(),
        message="岗位创建成功",
    )


@router.get("/{job_id}", response_model=APIResponse)
async def get_job_detail(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取岗位详情"""
    job = await job_crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")

    # 权限检查：非管理员只能查看自己创建的岗位
    if (
        current_user.role not in ("admin", "hr_manager")
        and job.created_by != current_user.id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看此岗位")

    return APIResponse.success(data=JobResponse.model_validate(job).model_dump())


@router.put("/{job_id}", response_model=APIResponse)
async def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新岗位信息（全量更新）"""
    job = await job_crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")

    # 权限检查：只有创建者或管理员可以编辑
    if job.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权编辑此岗位")

    # 已关闭的岗位不允许编辑
    if job.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已关闭的岗位不可编辑")

    updated_job = await job_crud.update_job(db, job, payload)

    return APIResponse.success(
        data=JobResponse.model_validate(updated_job).model_dump(),
        message="岗位更新成功",
    )


@router.patch("/{job_id}/status", response_model=APIResponse)
async def change_job_status(
    job_id: uuid.UUID,
    payload: JobStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新岗位状态（发布/关闭）"""
    job = await job_crud.get_job(db, job_id)
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

    updated_job = await job_crud.update_job_status(db, job, payload.status)

    return APIResponse.success(
        data=JobResponse.model_validate(updated_job).model_dump(),
        message=f"岗位状态已更新为: {payload.status}",
    )


@router.delete("/{job_id}", response_model=APIResponse)
async def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除岗位（仅草稿状态且无匹配结果时允许）"""
    job = await job_crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")

    # 权限检查：只有创建者或管理员可以删除
    if job.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此岗位")

    try:
        await job_crud.delete_job(db, job_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    return APIResponse.success(message="岗位删除成功")
