"""AI匹配异步任务

执行人岗匹配的Celery任务：
1. 从数据库读取岗位和简历
2. 调用 MatchingService 进行LLM匹配
3. 将结果写入 match_results 表（upsert）
"""

import asyncio
import concurrent.futures
import json
import logging
import uuid as uuid_mod

from celery import shared_task
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.llm.base import LLMAuthenticationError, LLMRateLimitError, LLMTimeoutError
from app.utils.sanitize import sanitize_error_message

logger = logging.getLogger(__name__)

# ============================================================
# 模块级同步Engine单例（复用 resume_tasks 的模式）
# ============================================================
_sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
_sync_engine = create_engine(
    _sync_url,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(bind=_sync_engine)


# ============================================================
# 安全的异步执行辅助函数
# ============================================================
def _run_async(coro, num_items: int = 1):
    """安全地在同步环境中运行异步协程。

    Args:
        coro: 要执行的异步协程
        num_items: 待处理项目数量，用于计算动态超时
    """
    timeout = max(300, num_items * 120 + 60)  # 每项120s + 60s缓冲，最少300s
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=timeout)


# ============================================================
# 可重试和不可重试异常类型
# ============================================================
RETRYABLE_ERRORS = (LLMTimeoutError, LLMRateLimitError, ConnectionError, TimeoutError)
NON_RETRYABLE_ERRORS = (LLMAuthenticationError, ValueError)


@shared_task(
    bind=True,
    name="app.tasks.matching_tasks.execute_match",
    autoretry_for=RETRYABLE_ERRORS,
    dont_autoretry_for=NON_RETRYABLE_ERRORS,
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
    acks_late=True,
    soft_time_limit=1200,  # 20分钟软超时
    time_limit=1500,       # 25分钟硬超时
)
def execute_match(
    self,
    job_id: str,
    resume_ids: list[str],
    llm_config_id: str | None = None,
) -> dict:
    """
    执行AI匹配任务。

    流程:
    1. 从数据库读取岗位信息和简历解析数据
    2. 获取LLM配置
    3. 对每份简历调用 MatchingService.match_single()
    4. 将结果写入 match_results 表（upsert: 相同job+resume组合更新）
    5. 返回成功/失败数量汇总

    Args:
        job_id: 岗位UUID
        resume_ids: 简历UUID列表
        llm_config_id: 可选的LLM配置ID（指定则使用该配置）

    Returns:
        任务执行摘要
    """
    logger.info(
        f"开始匹配任务: job_id={job_id}, "
        f"resume_count={len(resume_ids)}, "
        f"llm_config_id={llm_config_id}"
    )

    try:
        # Step 1: 获取岗位数据
        job_data = _get_job_data(job_id)
        if job_data is None:
            logger.error(f"岗位不存在: job_id={job_id}")
            return {"status": "failed", "error": "岗位不存在", "job_id": job_id}

        # Step 2: 获取简历解析数据
        resumes_data = _get_resumes_data(resume_ids)
        if not resumes_data:
            logger.error(f"没有可用的简历数据: job_id={job_id}")
            return {"status": "failed", "error": "没有可用的简历数据", "job_id": job_id}

        # Step 3: 获取LLM配置
        llm_config = _get_llm_config(llm_config_id)
        if llm_config is None:
            logger.error("无法获取有效的LLM配置")
            return {"status": "failed", "error": "LLM配置无效", "job_id": job_id}

        # Step 4: 执行匹配
        results = _run_async(
            _do_matching(job_data, resumes_data, llm_config),
            num_items=len(resumes_data),
        )

        # Step 5: 写入数据库
        success_count = 0
        fail_count = 0
        for result in results:
            if result.get("status") == "success":
                _upsert_match_result(
                    job_id=job_id,
                    resume_id=result["resume_id"],
                    match_data=result,
                    model_used=f"{llm_config['provider']}/{llm_config.get('model_name', 'default')}",
                )
                success_count += 1
            else:
                fail_count += 1
                logger.warning(
                    f"匹配失败: resume_id={result.get('resume_id')}, "
                    f"error={result.get('error')}"
                )

        logger.info(
            f"匹配任务完成: job_id={job_id}, "
            f"success={success_count}, failed={fail_count}"
        )

        return {
            "status": "completed",
            "job_id": job_id,
            "total": len(resume_ids),
            "success": success_count,
            "failed": fail_count,
        }

    except LLMAuthenticationError as exc:
        logger.error(f"LLM认证失败(不重试): job_id={job_id}, error={exc}")
        return {
            "status": "auth_failed",
            "job_id": job_id,
            "error": sanitize_error_message(str(exc)),
        }

    except (LLMTimeoutError, LLMRateLimitError, ConnectionError, TimeoutError):
        # 可重试错误由 autoretry_for 自动处理
        logger.warning(
            f"匹配任务遇到可重试错误: job_id={job_id}, "
            f"retry={self.request.retries}/{self.max_retries}"
        )
        raise

    except Exception as exc:
        logger.error(
            f"匹配任务异常: job_id={job_id}, error={exc}", exc_info=True
        )
        return {
            "status": "failed",
            "job_id": job_id,
            "error": sanitize_error_message(str(exc)),
        }


# ============================================================
# 异步匹配核心逻辑
# ============================================================


async def _do_matching(
    job_data: dict, resumes_data: list[dict], llm_config: dict
) -> list[dict]:
    """执行实际的LLM匹配（异步）"""
    from app.services.matching_service import MatchingService

    service = MatchingService(
        provider=llm_config["provider"],
        api_key=llm_config.get("api_key"),
        model_name=llm_config.get("model_name"),
        endpoint=llm_config.get("endpoint"),
        timeout=llm_config.get("timeout", 120),
    )

    return await service.match_batch(job_data, resumes_data)


# ============================================================
# 数据库操作辅助函数
# ============================================================


def _get_job_data(job_id: str) -> dict | None:
    """从数据库获取岗位数据"""
    session = SyncSessionLocal()
    try:
        result = session.execute(
            text(
                "SELECT id, title, department, description, requirements "
                "FROM jobs WHERE id = :job_id::uuid"
            ),
            {"job_id": job_id},
        )
        row = result.fetchone()
        if row is None:
            return None

        return {
            "id": str(row[0]),
            "title": row[1],
            "department": row[2],
            "description": row[3],
            "requirements": row[4] if isinstance(row[4], dict) else {},
        }
    finally:
        session.close()


def _get_resumes_data(resume_ids: list[str]) -> list[dict]:
    """从数据库获取简历解析数据"""
    if not resume_ids:
        return []

    session = SyncSessionLocal()
    try:
        # 使用 ANY 数组操作符批量查询
        result = session.execute(
            text(
                "SELECT id, parsed_data "
                "FROM resumes "
                "WHERE id = ANY(:ids::uuid[]) "
                "AND parse_status = 'completed' "
                "AND parsed_data IS NOT NULL"
            ),
            {"ids": resume_ids},
        )
        rows = result.fetchall()

        resumes = []
        for row in rows:
            parsed_data = row[1] if isinstance(row[1], dict) else {}
            resumes.append({
                "resume_id": str(row[0]),
                "parsed_data": parsed_data,
            })

        return resumes
    finally:
        session.close()


def _get_llm_config(config_id: str | None = None) -> dict | None:
    """
    获取LLM配置。

    如果指定了 config_id，使用该配置；否则使用活跃的默认配置。
    """
    from app.services.llm_resume_parser import get_active_llm_config_sync

    if config_id:
        # 获取指定配置
        session = SyncSessionLocal()
        try:
            result = session.execute(
                text(
                    "SELECT provider_type, api_key, model_name, endpoint, config "
                    "FROM llm_configs "
                    "WHERE id = :config_id::uuid AND is_active = true"
                ),
                {"config_id": config_id},
            )
            row = result.fetchone()
            if row:
                extra = row[4] or {}
                logger.info(
                    f"使用指定LLM配置: config_id={config_id}, "
                    f"provider={row[0]}, model={row[2]}"
                )
                return {
                    "provider": row[0],
                    "api_key": row[1],
                    "model_name": row[2],
                    "endpoint": row[3],
                    "timeout": extra.get("timeout", settings.LLM_REQUEST_TIMEOUT),
                }
            logger.warning(f"指定LLM配置不存在或未激活: config_id={config_id}")
        finally:
            session.close()

    # 使用默认活跃配置
    try:
        config = get_active_llm_config_sync(_sync_engine)
        if config["provider"] == "ollama":
            return config
        if not config.get("api_key"):
            logger.warning(f"LLM配置缺少api_key: provider={config['provider']}")
            return None
        logger.info(
            f"已获取LLM配置: provider={config['provider']}, "
            f"model={config.get('model_name', 'default')}"
        )
        return config
    except Exception as e:
        logger.error(f"获取LLM配置失败: {sanitize_error_message(str(e))}")
        return None


def _upsert_match_result(
    job_id: str,
    resume_id: str,
    match_data: dict,
    model_used: str,
) -> None:
    """
    写入或更新匹配结果（upsert: 相同 job+resume 组合更新）。
    """
    session = SyncSessionLocal()
    try:
        # PostgreSQL upsert (INSERT ... ON CONFLICT UPDATE)
        session.execute(
            text(
                """
                INSERT INTO match_results (
                    id, job_id, resume_id, overall_score, skill_score,
                    experience_score, education_score, soft_skill_score, grade,
                    recommendation, details, model_used, created_at
                ) VALUES (
                    :id, :job_id::uuid, :resume_id::uuid, :overall_score,
                    :skill_score, :experience_score, :education_score,
                    :soft_skill_score, :grade, :recommendation, :details::jsonb,
                    :model_used, NOW()
                )
                ON CONFLICT (job_id, resume_id)
                DO UPDATE SET
                    overall_score = EXCLUDED.overall_score,
                    skill_score = EXCLUDED.skill_score,
                    experience_score = EXCLUDED.experience_score,
                    education_score = EXCLUDED.education_score,
                    soft_skill_score = EXCLUDED.soft_skill_score,
                    grade = EXCLUDED.grade,
                    recommendation = EXCLUDED.recommendation,
                    details = EXCLUDED.details,
                    model_used = EXCLUDED.model_used,
                    created_at = NOW()
                """
            ),
            {
                "id": str(uuid_mod.uuid4()),
                "job_id": job_id,
                "resume_id": resume_id,
                "overall_score": match_data["overall_score"],
                "skill_score": match_data["skill_score"],
                "experience_score": match_data["experience_score"],
                "education_score": match_data["education_score"],
                "soft_skill_score": match_data.get("soft_skill_score"),
                "grade": match_data["grade"],
                "recommendation": match_data.get("recommendation", ""),
                "details": json.dumps(match_data.get("details", {}), ensure_ascii=False),
                "model_used": model_used,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
