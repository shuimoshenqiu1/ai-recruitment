"""智能匹配路由"""

import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import Job
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.models.user import User
from app.schemas.common import APIResponse, PageResponse
from app.schemas.matching import (
    MatchDetailResponse,
    MatchExportRequest,
    MatchRequest,
    MatchResultResponse,
)

router = APIRouter()


async def _check_job_access(
    job_id: uuid.UUID, current_user: User, db: AsyncSession
) -> Job:
    """检查岗位存在性和用户访问权限（防止 IDOR）。

    admin 和 hr_manager 角色可操作所有岗位，其他用户只能操作自己创建的岗位。

    Raises:
        HTTPException 404: 岗位不存在
        HTTPException 403: 无权操作此岗位
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")
    if current_user.role not in ("admin", "hr_manager") and job.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作此岗位")
    return job


@router.post("/execute", response_model=APIResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_matching(
    payload: MatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    执行AI匹配任务。
    
    - 校验岗位和简历存在性
    - 简历必须已完成解析
    - 提交后返回202，实际匹配由后台异步完成
    """
    # 校验岗位存在 + 所有权
    job = await _check_job_access(payload.job_id, current_user, db)

    if job.status != "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能对已发布的岗位执行匹配",
        )

    # 校验简历存在且已解析
    resume_result = await db.execute(
        select(Resume).where(
            Resume.id.in_(payload.resume_ids),
            Resume.parse_status == "completed",
        )
    )
    valid_resumes = resume_result.scalars().all()
    valid_ids = {r.id for r in valid_resumes}
    invalid_ids = [str(rid) for rid in payload.resume_ids if rid not in valid_ids]

    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下简历未完成解析或不存在: {', '.join(invalid_ids)}",
        )

    from app.tasks.matching_tasks import execute_match

    task = execute_match.delay(
        job_id=str(payload.job_id),
        resume_ids=[str(r) for r in payload.resume_ids],
        llm_config_id=str(payload.llm_config_id) if payload.llm_config_id else None,
    )

    return APIResponse.success(
        data={
            "job_id": str(payload.job_id),
            "resume_count": len(payload.resume_ids),
            "task_id": task.id,
            "status": "submitted",
        },
        message="匹配任务已提交，请稍后查看结果",
    )


@router.get("/results", response_model=APIResponse)
async def list_match_results(
    job_id: uuid.UUID = Query(description="岗位ID"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    min_score: float | None = Query(default=None, ge=0, le=100, description="最低分数"),
    grade: str | None = Query(default=None, description="筛选等级"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取匹配结果列表（分页+筛选）"""
    # 校验岗位所有权
    await _check_job_access(job_id, current_user, db)

    query = select(MatchResult).where(MatchResult.job_id == job_id)
    count_query = select(func.count()).select_from(MatchResult).where(
        MatchResult.job_id == job_id
    )

    if min_score is not None:
        query = query.where(MatchResult.overall_score >= min_score)
        count_query = count_query.where(MatchResult.overall_score >= min_score)

    if grade:
        query = query.where(MatchResult.grade == grade)
        count_query = count_query.where(MatchResult.grade == grade)

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 按分数降序分页
    offset = (page - 1) * page_size
    query = query.order_by(MatchResult.overall_score.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    matches = result.scalars().all()

    items = [MatchResultResponse.model_validate(m) for m in matches]
    page_data = PageResponse.create(items=items, total=total, page=page, page_size=page_size)

    return APIResponse.success(data=page_data.model_dump())


@router.get("/results/{result_id}", response_model=APIResponse)
async def get_match_detail(
    result_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取匹配结果详情（含完整分析）"""
    result = await db.execute(select(MatchResult).where(MatchResult.id == result_id))
    match = result.scalar_one_or_none()

    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="匹配结果不存在")

    # 校验岗位所有权
    await _check_job_access(match.job_id, current_user, db)

    return APIResponse.success(data=MatchDetailResponse.model_validate(match).model_dump())


@router.post("/export")
async def export_match_results(
    payload: MatchExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    导出匹配结果为增强版Excel（带颜色标识和汇总）。
    
    支持按分数和等级筛选后导出。
    """
    # 校验岗位所有权
    job = await _check_job_access(payload.job_id, current_user, db)

    query = select(MatchResult).where(MatchResult.job_id == payload.job_id)

    if payload.min_score is not None:
        query = query.where(MatchResult.overall_score >= payload.min_score)
    if payload.grades:
        query = query.where(MatchResult.grade.in_(payload.grades))

    query = query.order_by(MatchResult.overall_score.desc())
    result = await db.execute(query)
    matches = result.scalars().all()

    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有符合条件的匹配结果",
        )

    # 使用增强版报告服务生成Excel
    from app.services.report_service import ReportService

    report_service = ReportService()
    output = report_service.generate_match_excel(matches=matches, job_title=job.title)

    filename = f"match_results_{payload.job_id}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
