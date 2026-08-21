"""Pydantic模型 - 数据看板"""

from pydantic import BaseModel, Field


class OverviewStats(BaseModel):
    """看板总览统计"""

    resume_total: int = Field(description="简历总量")
    resume_parsed: int = Field(description="已解析简历数")
    resume_pending: int = Field(description="待解析简历数")
    job_total: int = Field(description="岗位总量")
    job_active: int = Field(description="活跃岗位数(published)")
    match_total: int = Field(description="匹配执行总次数")
    match_excellent: int = Field(description="优秀候选人数")
    match_qualified: int = Field(description="合格候选人数")
    avg_score: float | None = Field(default=None, description="平均匹配分数")


class JobProgress(BaseModel):
    """岗位招聘进度"""

    job_id: str = Field(description="岗位ID")
    title: str = Field(description="岗位名称")
    headcount: int = Field(description="招聘人数")
    match_count: int = Field(description="已匹配人数")
    excellent_count: int = Field(description="优秀候选人数")
    qualified_count: int = Field(description="合格候选人数")
    progress: float = Field(description="进度百分比(0-100)")


class DailyCount(BaseModel):
    """每日计数"""

    date: str = Field(description="日期(YYYY-MM-DD)")
    count: int = Field(description="数量")


class ResumeStats(BaseModel):
    """简历统计"""

    daily_uploads: list[DailyCount] = Field(description="每日上传量趋势")
    status_distribution: dict[str, int] = Field(description="状态分布")
    parse_success_rate: float = Field(description="解析成功率(0-100)")


class ScoreRange(BaseModel):
    """分数分布段"""

    range: str = Field(description="分数区间")
    count: int = Field(description="该区间数量")


class DailyAvgScore(BaseModel):
    """每日平均分"""

    date: str = Field(description="日期(YYYY-MM-DD)")
    avg_score: float = Field(description="当日平均分")


class MatchingStats(BaseModel):
    """匹配统计"""

    score_distribution: list[ScoreRange] = Field(description="分数分布")
    grade_distribution: dict[str, int] = Field(description="等级分布")
    daily_matches: list[DailyCount] = Field(description="每日匹配量趋势")
    avg_score_trend: list[DailyAvgScore] = Field(description="平均分趋势")
