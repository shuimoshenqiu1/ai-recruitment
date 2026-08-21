"""API路由 - 数据看板"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.dashboard import (
    DailyAvgScore,
    DailyCount,
    JobProgress,
    MatchingStats,
    OverviewStats,
    ResumeStats,
    ScoreRange,
)
from app.services.dashboard_service import dashboard_service

router = APIRouter()

# 具有全局数据访问权限的角色
_GLOBAL_ROLES = {"admin", "hr_manager"}


def _resolve_user_scope(user: User):
    """根据角色决定查询范围：admin/hr_manager看全局，其他看自己的"""
    if user.role in _GLOBAL_ROLES:
        return None
    return user.id


@router.get("/overview", response_model=OverviewStats, summary="看板总览数据")
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OverviewStats:
    """
    获取招聘看板总览统计数据。

    权限：
    - admin/hr_manager: 查看全局数据
    - recruiter/interviewer: 仅查看自己创建/上传的数据
    """
    user_id = _resolve_user_scope(current_user)
    data = await dashboard_service.get_overview(db, user_id=user_id)
    return OverviewStats(**data)


@router.get(
    "/jobs/progress",
    response_model=list[JobProgress],
    summary="各岗位招聘进度",
)
async def get_jobs_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobProgress]:
    """
    获取各活跃岗位的招聘进度。

    - progress = excellent_count / headcount * 100（封顶100）
    - 仅展示 status=published 的岗位

    权限：
    - admin/hr_manager: 所有活跃岗位
    - recruiter/interviewer: 仅自己创建的岗位
    """
    user_id = _resolve_user_scope(current_user)
    data = await dashboard_service.get_job_progress(db, user_id=user_id)
    return [JobProgress(**item) for item in data]


@router.get("/resumes/stats", response_model=ResumeStats, summary="简历统计")
async def get_resume_statistics(
    days: int = Query(default=30, ge=1, le=365, description="统计天数范围"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeStats:
    """
    简历上传与解析统计（最近N天）。

    包含：
    - 每日上传量趋势
    - 解析状态分布
    - 解析成功率

    权限：
    - admin/hr_manager: 全局简历数据
    - recruiter/interviewer: 仅自己上传的简历
    """
    user_id = _resolve_user_scope(current_user)
    data = await dashboard_service.get_resume_stats(db, days=days, user_id=user_id)
    return ResumeStats(**data)


@router.get("/matching/stats", response_model=MatchingStats, summary="匹配统计")
async def get_matching_statistics(
    days: int = Query(default=30, ge=1, le=365, description="统计天数范围"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchingStats:
    """
    匹配结果统计（最近N天）。

    包含：
    - 分数分布（0-20, 20-40, 40-60, 60-80, 80-100）
    - 等级分布（excellent/qualified/unqualified）
    - 每日匹配量趋势
    - 平均分趋势

    权限：
    - admin/hr_manager: 全局匹配数据
    - recruiter/interviewer: 仅自己创建的岗位对应的匹配数据
    """
    user_id = _resolve_user_scope(current_user)
    data = await dashboard_service.get_matching_stats(db, days=days, user_id=user_id)
    return MatchingStats(**data)
