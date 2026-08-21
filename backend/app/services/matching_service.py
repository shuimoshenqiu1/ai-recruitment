"""AI智能匹配服务

使用LLM对候选人简历与岗位需求进行多维度匹配分析。
包含结果验证、分数计算、等级划分和批量处理。
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.base import (
    LLMError,
    LLMRateLimitError,
    LLMResponseParseError,
    LLMTimeoutError,
)
from app.llm.factory import LLMFactory
from app.llm.prompts.matching import build_matching_messages
from app.utils.sanitize import sanitize_error_message

logger = logging.getLogger(__name__)

# 评分权重
WEIGHT_SKILL = 0.40
WEIGHT_EXPERIENCE = 0.30
WEIGHT_EDUCATION = 0.20
WEIGHT_SOFT_SKILL = 0.10

# 等级阈值
GRADE_EXCELLENT_THRESHOLD = 80
GRADE_QUALIFIED_THRESHOLD = 60

# LLM调用最大重试次数
MAX_RETRIES = 2

# 输入文本长度限制
MAX_JOB_TEXT_LENGTH = 10000
MAX_RESUME_TEXT_LENGTH = 30000

VALID_GRADES = {"excellent", "qualified", "unqualified"}


class MatchingError(Exception):
    """匹配服务异常"""

    def __init__(self, message: str, resume_id: str | None = None):
        self.resume_id = resume_id
        super().__init__(message)


class MatchingService:
    """
    使用LLM进行人岗智能匹配。

    负责：
    1. 将岗位需求和简历数据格式化为可读文本
    2. 调用LLM进行多维度匹配分析
    3. 验证和清理返回结果
    4. 计算加权综合得分并划分等级

    Usage:
        service = MatchingService(provider="openai", api_key="sk-...")
        result = await service.match_single(job_data, resume_data)
    """

    def __init__(self, provider: str = "openai", **llm_kwargs: Any):
        """
        初始化匹配服务。

        Args:
            provider: LLM提供商标识
            **llm_kwargs: 传递给 LLMFactory.create 的参数
        """
        self.provider_name = provider
        self.llm = LLMFactory.create(provider, **llm_kwargs)
        logger.info(f"MatchingService 初始化: provider={provider}, model={self.llm.model_name}")

    async def match_single(self, job: dict, resume_parsed: dict) -> dict:
        """
        单个简历匹配单个岗位。

        Args:
            job: 岗位数据，需包含 requirements 字段 (JSONB)
            resume_parsed: 简历已解析数据 (Resume.parsed_data)

        Returns:
            匹配结果字典，包含各维度得分、等级、推荐意见等

        Raises:
            MatchingError: LLM调用失败或多次重试后仍无法获得有效结果
        """
        # 构建文本
        job_text = self._build_job_requirements_text(job)
        resume_text = self._build_resume_text(resume_parsed)

        if not job_text.strip():
            raise MatchingError("岗位需求信息为空，无法匹配")
        if not resume_text.strip():
            raise MatchingError("简历数据为空，无法匹配")

        # 截断过长文本
        job_text = job_text[:MAX_JOB_TEXT_LENGTH]
        resume_text = resume_text[:MAX_RESUME_TEXT_LENGTH]

        messages = build_matching_messages(job_text, resume_text)

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                logger.info(f"LLM匹配尝试 #{attempt}, provider={self.provider_name}")

                result = await self.llm.chat_json(
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2048,
                )

                # 验证和清理
                validated = self._validate_match_result(result)
                logger.info(
                    f"LLM匹配成功: attempt={attempt}, "
                    f"overall_score={validated['overall_score']}, "
                    f"grade={validated['grade']}"
                )
                return validated

            except LLMResponseParseError as e:
                last_error = e
                logger.warning(
                    f"LLM返回无效JSON (attempt {attempt}): "
                    f"{sanitize_error_message(str(e))}"
                )
                if attempt > MAX_RETRIES + 1:
                    break

            except (LLMTimeoutError, LLMRateLimitError):
                # 可重试异常直接透传，让Celery autoretry_for 捕获
                raise

            except LLMError as e:
                last_error = e
                logger.error(
                    f"LLM调用错误 (attempt {attempt}): "
                    f"{sanitize_error_message(str(e))}"
                )
                if attempt > MAX_RETRIES + 1:
                    break

        raise MatchingError(
            f"LLM匹配失败，已重试{MAX_RETRIES}次: "
            f"{sanitize_error_message(str(last_error))}"
        )

    async def match_batch(self, job: dict, resumes: list[dict]) -> list[dict]:
        """
        批量匹配（串行调用LLM，避免速率限制）。

        Args:
            job: 岗位数据
            resumes: 简历列表，每项为 {resume_id, parsed_data}

        Returns:
            匹配结果列表，每项额外包含 resume_id 和 status 字段
        """
        results = []
        for i, resume_item in enumerate(resumes):
            resume_id = resume_item.get("resume_id", f"unknown_{i}")
            parsed_data = resume_item.get("parsed_data", {})

            try:
                match_result = await self.match_single(job, parsed_data)
                match_result["resume_id"] = resume_id
                match_result["status"] = "success"
                results.append(match_result)
                logger.info(
                    f"批量匹配进度: {i + 1}/{len(resumes)}, "
                    f"resume_id={resume_id}, score={match_result['overall_score']}"
                )

            except MatchingError as e:
                logger.error(f"批量匹配失败: resume_id={resume_id}, error={e}")
                results.append({
                    "resume_id": resume_id,
                    "status": "failed",
                    "error": sanitize_error_message(str(e)),
                })

        return results

    def _build_job_requirements_text(self, job: dict) -> str:
        """
        将Job数据转为可读文本。

        处理 Job.requirements JSONB 的结构：
        {hard: [...], soft: [...], preferred: [...]}

        Args:
            job: 岗位数据字典

        Returns:
            格式化后的岗位需求文本
        """
        parts = []

        # 岗位基本信息
        if job.get("title"):
            parts.append(f"**岗位名称**: {job['title']}")
        if job.get("department"):
            parts.append(f"**所属部门**: {job['department']}")
        if job.get("description"):
            parts.append(f"**岗位描述**: {job['description']}")

        # 需求结构化数据
        requirements = job.get("requirements", {})
        if isinstance(requirements, dict):
            hard = requirements.get("hard", [])
            soft = requirements.get("soft", [])
            preferred = requirements.get("preferred", [])

            if hard:
                parts.append("\n**硬性要求（必须满足）**:")
                for item in hard:
                    parts.append(f"  - {item}")

            if soft:
                parts.append("\n**软性要求（加分项）**:")
                for item in soft:
                    parts.append(f"  - {item}")

            if preferred:
                parts.append("\n**优先条件（额外加分）**:")
                for item in preferred:
                    parts.append(f"  - {item}")

        return "\n".join(parts)

    def _build_resume_text(self, parsed_data: dict) -> str:
        """
        将简历parsed_data转为可读文本。

        处理结构：{basic_info, education, work_experience, skills, projects, certifications, languages}

        Args:
            parsed_data: 简历结构化数据

        Returns:
            格式化后的简历文本
        """
        parts = []

        # parsed_data可能有 "structured" 嵌套层（来自parse_resume的存储格式）
        data = parsed_data.get("structured", parsed_data)

        # 基本信息
        basic = data.get("basic_info", {})
        if basic:
            info_items = []
            if basic.get("name"):
                info_items.append(f"姓名: {basic['name']}")
            if basic.get("gender"):
                info_items.append(f"性别: {basic['gender']}")
            if basic.get("age"):
                info_items.append(f"年龄: {basic['age']}")
            if basic.get("location"):
                info_items.append(f"所在地: {basic['location']}")
            if info_items:
                parts.append("**基本信息**: " + " | ".join(info_items))

        # 教育背景
        education = data.get("education", [])
        if education:
            parts.append("\n**教育背景**:")
            for edu in education:
                line = f"  - {edu.get('school', '未知学校')}"
                if edu.get("major"):
                    line += f" / {edu['major']}"
                if edu.get("degree"):
                    line += f" / {edu['degree']}"
                if edu.get("start_date") or edu.get("end_date"):
                    line += f" ({edu.get('start_date', '?')} ~ {edu.get('end_date', '至今')})"
                parts.append(line)

        # 工作经历
        work = data.get("work_experience", [])
        if work:
            parts.append("\n**工作经历**:")
            for exp in work:
                line = f"  - {exp.get('company', '未知公司')} | {exp.get('position', '未知职位')}"
                if exp.get("start_date") or exp.get("end_date"):
                    line += f" ({exp.get('start_date', '?')} ~ {exp.get('end_date', '至今')})"
                parts.append(line)
                if exp.get("description"):
                    parts.append(f"    {exp['description']}")
                achievements = exp.get("achievements", [])
                for ach in achievements[:5]:  # 限制数量
                    parts.append(f"    • {ach}")

        # 技能
        skills = data.get("skills", [])
        if skills:
            parts.append("\n**技术技能**:")
            for skill in skills:
                line = f"  - {skill.get('name', '未知技能')}"
                if skill.get("level"):
                    line += f" ({skill['level']})"
                if skill.get("years"):
                    line += f" {skill['years']}年"
                parts.append(line)

        # 项目经验
        projects = data.get("projects", [])
        if projects:
            parts.append("\n**项目经验**:")
            for proj in projects[:5]:  # 限制数量
                line = f"  - {proj.get('name', '未知项目')}"
                if proj.get("role"):
                    line += f" | {proj['role']}"
                parts.append(line)
                if proj.get("description"):
                    parts.append(f"    {proj['description']}")
                tech = proj.get("tech_stack", [])
                if tech:
                    parts.append(f"    技术栈: {', '.join(tech[:10])}")

        # 证书
        certs = data.get("certifications", [])
        if certs:
            parts.append("\n**证书资质**:")
            for cert in certs:
                parts.append(f"  - {cert.get('name', '未知证书')}")

        # 语言
        languages = data.get("languages", [])
        if languages:
            parts.append("\n**语言能力**:")
            for lang in languages:
                line = f"  - {lang.get('language', '未知')}"
                if lang.get("level"):
                    line += f" ({lang['level']})"
                parts.append(line)

        return "\n".join(parts)

    def _validate_match_result(self, raw: dict) -> dict:
        """
        验证和清理LLM返回的匹配结果。

        处理：
        - 分数范围钳位（0-100）
        - 等级合法性检查
        - 缺失字段补默认值
        - 重新计算加权综合得分（不信任LLM的计算）

        Args:
            raw: LLM返回的原始字典

        Returns:
            验证清理后的匹配结果
        """
        # 提取并钳位各维度分数
        skill_score = _clamp_score(raw.get("skill_score"))
        experience_score = _clamp_score(raw.get("experience_score"))
        education_score = _clamp_score(raw.get("education_score"))
        soft_skill_score = _clamp_score(raw.get("soft_skill_score"))

        # 自行计算加权综合得分（不信任LLM的overall_score）
        overall_score = round(
            skill_score * WEIGHT_SKILL
            + experience_score * WEIGHT_EXPERIENCE
            + education_score * WEIGHT_EDUCATION
            + soft_skill_score * WEIGHT_SOFT_SKILL
        )
        overall_score = _clamp_score(overall_score)

        # 自行确定等级（不信任LLM的grade）
        if overall_score >= GRADE_EXCELLENT_THRESHOLD:
            grade = "excellent"
        elif overall_score >= GRADE_QUALIFIED_THRESHOLD:
            grade = "qualified"
        else:
            grade = "unqualified"

        # 推荐理由
        recommendation = raw.get("recommendation", "")
        if not isinstance(recommendation, str) or not recommendation.strip():
            recommendation = f"综合得分{overall_score}分，等级: {grade}"

        # 优劣势
        strengths = _clean_str_list(raw.get("strengths"))
        weaknesses = _clean_str_list(raw.get("weaknesses"))

        # 详细分析
        raw_details = raw.get("details", {})
        if not isinstance(raw_details, dict):
            raw_details = {}

        details = {
            "skill_analysis": _ensure_str(raw_details.get("skill_analysis")),
            "experience_analysis": _ensure_str(raw_details.get("experience_analysis")),
            "education_analysis": _ensure_str(raw_details.get("education_analysis")),
            "soft_skill_analysis": _ensure_str(raw_details.get("soft_skill_analysis")),
            "strengths": strengths,
            "weaknesses": weaknesses,
        }

        return {
            "overall_score": overall_score,
            "skill_score": skill_score,
            "experience_score": experience_score,
            "education_score": education_score,
            "soft_skill_score": soft_skill_score,
            "grade": grade,
            "recommendation": recommendation.strip(),
            "details": details,
        }


# ============================================================
# 内部辅助函数
# ============================================================


def _clamp_score(value: Any) -> int:
    """将评分值钳位到 0-100 范围"""
    if value is None:
        return 50  # 缺失时给中间分
    try:
        score = int(float(value))
    except (ValueError, TypeError):
        return 50
    return max(0, min(100, score))


def _clean_str_list(value: Any) -> list[str]:
    """清理字符串列表"""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if item and str(item).strip()]


def _ensure_str(value: Any) -> str:
    """确保值为字符串，None时返回空串"""
    if value is None:
        return ""
    return str(value).strip()
