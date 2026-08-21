"""业务服务 - 招聘数据看板"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.match_result import MatchResult
from app.models.resume import Resume


class DashboardService:
    """招聘数据统计服务

    权限说明：
    - user_id=None 时查询全局数据（admin/hr_manager用）
    - user_id 传值时仅查该用户的数据（普通用户用）
    """

    async def get_overview(
        self, db: AsyncSession, user_id: uuid.UUID | None = None
    ) -> dict:
        """获取总览数据"""
        # 简历统计
        resume_base = select(Resume).where(Resume.is_deleted.is_(False))
        if user_id:
            resume_base = resume_base.where(Resume.uploaded_by == user_id)

        resume_stats_q = select(
            func.count(Resume.id).label("total"),
            func.count(
                case((Resume.parse_status == "completed", Resume.id))
            ).label("parsed"),
            func.count(
                case((Resume.parse_status == "pending", Resume.id))
            ).label("pending"),
        ).where(Resume.is_deleted.is_(False))
        if user_id:
            resume_stats_q = resume_stats_q.where(Resume.uploaded_by == user_id)

        resume_result = await db.execute(resume_stats_q)
        resume_row = resume_result.one()

        # 岗位统计
        job_stats_q = select(
            func.count(Job.id).label("total"),
            func.count(case((Job.status == "published", Job.id))).label("active"),
        )
        if user_id:
            job_stats_q = job_stats_q.where(Job.created_by == user_id)

        job_result = await db.execute(job_stats_q)
        job_row = job_result.one()

        # 匹配统计
        match_stats_q = select(
            func.count(MatchResult.id).label("total"),
            func.count(
                case((MatchResult.grade == "excellent", MatchResult.id))
            ).label("excellent"),
            func.count(
                case((MatchResult.grade == "qualified", MatchResult.id))
            ).label("qualified"),
            func.avg(MatchResult.overall_score).label("avg_score"),
        )
        if user_id:
            # 普通用户：只看自己创建的岗位对应的匹配
            match_stats_q = match_stats_q.where(
                MatchResult.job_id.in_(
                    select(Job.id).where(Job.created_by == user_id)
                )
            )

        match_result = await db.execute(match_stats_q)
        match_row = match_result.one()

        avg_score = (
            round(float(match_row.avg_score), 2) if match_row.avg_score else None
        )

        return {
            "resume_total": resume_row.total,
            "resume_parsed": resume_row.parsed,
            "resume_pending": resume_row.pending,
            "job_total": job_row.total,
            "job_active": job_row.active,
            "match_total": match_row.total,
            "match_excellent": match_row.excellent,
            "match_qualified": match_row.qualified,
            "avg_score": avg_score,
        }

    async def get_job_progress(
        self, db: AsyncSession, user_id: uuid.UUID | None = None
    ) -> list[dict]:
        """各岗位招聘进度"""
        # 查询活跃岗位及其匹配统计
        job_q = select(Job).where(Job.status == "published")
        if user_id:
            job_q = job_q.where(Job.created_by == user_id)

        jobs_result = await db.execute(job_q)
        jobs = jobs_result.scalars().all()

        if not jobs:
            return []

        job_ids = [j.id for j in jobs]

        # 按岗位聚合匹配数据
        match_agg_q = (
            select(
                MatchResult.job_id,
                func.count(MatchResult.id).label("match_count"),
                func.count(
                    case((MatchResult.grade == "excellent", MatchResult.id))
                ).label("excellent_count"),
                func.count(
                    case((MatchResult.grade == "qualified", MatchResult.id))
                ).label("qualified_count"),
            )
            .where(MatchResult.job_id.in_(job_ids))
            .group_by(MatchResult.job_id)
        )

        match_agg_result = await db.execute(match_agg_q)
        match_map = {
            row.job_id: {
                "match_count": row.match_count,
                "excellent_count": row.excellent_count,
                "qualified_count": row.qualified_count,
            }
            for row in match_agg_result.all()
        }

        progress_list = []
        for job in jobs:
            stats = match_map.get(
                job.id, {"match_count": 0, "excellent_count": 0, "qualified_count": 0}
            )
            headcount = max(job.headcount, 1)  # 防止除零
            progress = min(
                round((stats["excellent_count"] / headcount) * 100, 1), 100.0
            )
            progress_list.append(
                {
                    "job_id": str(job.id),
                    "title": job.title,
                    "headcount": job.headcount,
                    "match_count": stats["match_count"],
                    "excellent_count": stats["excellent_count"],
                    "qualified_count": stats["qualified_count"],
                    "progress": progress,
                }
            )

        return progress_list

    async def get_resume_stats(
        self, db: AsyncSession, days: int = 30, user_id: uuid.UUID | None = None
    ) -> dict:
        """简历统计（最近N天）"""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # 每日上传量趋势
        daily_q = (
            select(
                cast(Resume.created_at, Date).label("upload_date"),
                func.count(Resume.id).label("count"),
            )
            .where(Resume.is_deleted.is_(False), Resume.created_at >= since)
            .group_by(cast(Resume.created_at, Date))
            .order_by(cast(Resume.created_at, Date))
        )
        if user_id:
            daily_q = daily_q.where(Resume.uploaded_by == user_id)

        daily_result = await db.execute(daily_q)
        daily_uploads = [
            {"date": row.upload_date.isoformat(), "count": row.count}
            for row in daily_result.all()
        ]

        # 状态分布
        status_q = (
            select(
                Resume.parse_status,
                func.count(Resume.id).label("count"),
            )
            .where(Resume.is_deleted.is_(False), Resume.created_at >= since)
            .group_by(Resume.parse_status)
        )
        if user_id:
            status_q = status_q.where(Resume.uploaded_by == user_id)

        status_result = await db.execute(status_q)
        status_distribution = {row.parse_status: row.count for row in status_result.all()}

        # 解析成功率
        total = sum(status_distribution.values())
        completed = status_distribution.get("completed", 0)
        parse_success_rate = round((completed / total) * 100, 1) if total > 0 else 0.0

        return {
            "daily_uploads": daily_uploads,
            "status_distribution": status_distribution,
            "parse_success_rate": parse_success_rate,
        }

    async def get_matching_stats(
        self, db: AsyncSession, days: int = 30, user_id: uuid.UUID | None = None
    ) -> dict:
        """匹配统计（最近N天）"""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        base_filter = [MatchResult.created_at >= since]
        if user_id:
            base_filter.append(
                MatchResult.job_id.in_(
                    select(Job.id).where(Job.created_by == user_id)
                )
            )

        # 分数分布（按20分一档）
        score_ranges = [
            ("0-20", 0, 20),
            ("20-40", 20, 40),
            ("40-60", 40, 60),
            ("60-80", 60, 80),
            ("80-100", 80, 101),  # 包含100
        ]

        score_distribution = []
        for label, low, high in score_ranges:
            count_q = select(func.count(MatchResult.id)).where(
                *base_filter,
                MatchResult.overall_score >= low,
                MatchResult.overall_score < high,
            )
            result = await db.execute(count_q)
            score_distribution.append({"range": label, "count": result.scalar() or 0})

        # 等级分布
        grade_q = (
            select(
                MatchResult.grade,
                func.count(MatchResult.id).label("count"),
            )
            .where(*base_filter)
            .group_by(MatchResult.grade)
        )
        grade_result = await db.execute(grade_q)
        grade_distribution = {
            (row.grade or "unknown"): row.count for row in grade_result.all()
        }

        # 每日匹配量趋势
        daily_match_q = (
            select(
                cast(MatchResult.created_at, Date).label("match_date"),
                func.count(MatchResult.id).label("count"),
            )
            .where(*base_filter)
            .group_by(cast(MatchResult.created_at, Date))
            .order_by(cast(MatchResult.created_at, Date))
        )
        daily_match_result = await db.execute(daily_match_q)
        daily_matches = [
            {"date": row.match_date.isoformat(), "count": row.count}
            for row in daily_match_result.all()
        ]

        # 平均分趋势
        avg_trend_q = (
            select(
                cast(MatchResult.created_at, Date).label("match_date"),
                func.avg(MatchResult.overall_score).label("avg_score"),
            )
            .where(*base_filter)
            .group_by(cast(MatchResult.created_at, Date))
            .order_by(cast(MatchResult.created_at, Date))
        )
        avg_trend_result = await db.execute(avg_trend_q)
        avg_score_trend = [
            {
                "date": row.match_date.isoformat(),
                "avg_score": round(float(row.avg_score), 2),
            }
            for row in avg_trend_result.all()
        ]

        return {
            "score_distribution": score_distribution,
            "grade_distribution": grade_distribution,
            "daily_matches": daily_matches,
            "avg_score_trend": avg_score_trend,
        }


# 单例
dashboard_service = DashboardService()
