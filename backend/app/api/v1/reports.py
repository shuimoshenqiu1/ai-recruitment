"""报告导出路由"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import Job
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.models.user import User
from app.schemas.matching import MatchExportRequest
from app.services.report_service import ReportService

router = APIRouter()
report_service = ReportService()


async def _check_job_access(
    job_id: uuid.UUID, current_user: User, db: AsyncSession
) -> Job:
    """检查岗位存在性和用户访问权限。"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")
    if current_user.role not in ("admin", "hr_manager") and job.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作此岗位")
    return job


@router.get("/match/{result_id}/report")
async def get_single_match_report(
    result_id: uuid.UUID,
    format: str = Query(default="html", description="报告格式: html"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单份匹配报告（HTML格式，前端可 window.print() 导出PDF）。

    权限：只能查看自己岗位下的匹配报告，admin/hr_manager 可查看所有。
    """
    # 查询匹配结果
    result = await db.execute(select(MatchResult).where(MatchResult.id == result_id))
    match = result.scalar_one_or_none()

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="匹配结果不存在",
        )

    # 校验岗位权限
    job_result = await db.execute(select(Job).where(Job.id == match.job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="岗位不存在")
    if current_user.role not in ("admin", "hr_manager") and job.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看此报告")

    # 查询关联简历
    resume_result = await db.execute(select(Resume).where(Resume.id == match.resume_id))
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关联简历不存在",
        )

    # 构建数据
    match_data = {
        "overall_score": match.overall_score,
        "skill_score": match.skill_score,
        "experience_score": match.experience_score,
        "education_score": match.education_score,
        "soft_skill_score": match.soft_skill_score,
        "grade": match.grade,
        "recommendation": match.recommendation,
        "details": match.details,
    }
    resume_data = resume.parsed_data or {}
    job_data = {
        "title": job.title,
        "department": job.department,
        "level": job.level,
        "requirements": job.requirements,
    }

    if format == "html":
        html_content = report_service.generate_single_report_html(
            match_result=match_data,
            resume_data=resume_data,
            job_data=job_data,
        )
        return HTMLResponse(content=html_content)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"不支持的格式: {format}，当前仅支持 html",
    )


@router.post("/match/export")
async def export_enhanced_excel(
    payload: MatchExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出增强版Excel（带颜色标识、分数条件格式化、汇总行）。

    权限：只能导出自己岗位的匹配结果，admin/hr_manager 可导出所有。
    """
    # 校验岗位权限并获取岗位信息
    job = await _check_job_access(payload.job_id, current_user, db)

    # 构建查询
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

    # 生成增强Excel
    output = report_service.generate_match_excel(
        matches=matches,
        job_title=job.title,
    )

    import re
    from urllib.parse import quote

    safe_title = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', job.title)[:50]
    filename = f"match_report_{safe_title}_{payload.job_id}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
