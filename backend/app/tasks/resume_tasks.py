"""简历解析异步任务

完整流程：文本提取 -> 清洗 -> 质量评估 -> LLM结构化解析 -> 存入DB
"""

import asyncio
import concurrent.futures
import json
import logging
from pathlib import Path

from celery import shared_task
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.llm.base import LLMAuthenticationError, LLMRateLimitError, LLMTimeoutError
from app.services.document_extractor import ExtractionError
from app.services.resume_parser import parse_resume_sync

logger = logging.getLogger(__name__)

# ============================================================
# H-3: 模块级同步Engine单例（避免反复 create_engine/dispose）
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
# H-2: 安全的异步执行辅助函数
# ============================================================
def _run_async(coro):
    """
    安全地在同步环境中运行异步协程。

    如果当前线程没有运行中的事件循环，直接使用 asyncio.run()。
    如果已有事件循环（gevent/eventlet worker），在新线程中执行以避免嵌套冲突。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的事件循环，直接用 asyncio.run()
        return asyncio.run(coro)
    else:
        # 已有事件循环，在独立线程中运行
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=300)


# ============================================================
# H-4: 定义可重试和不可重试异常类型
# ============================================================
RETRYABLE_ERRORS = (LLMTimeoutError, LLMRateLimitError, ConnectionError, TimeoutError)
NON_RETRYABLE_ERRORS = (LLMAuthenticationError, ValueError, ExtractionError)


@shared_task(
    bind=True,
    name="app.tasks.resume_tasks.parse_resume",
    autoretry_for=RETRYABLE_ERRORS,
    dont_autoretry_for=NON_RETRYABLE_ERRORS,
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
    acks_late=True,
)
def parse_resume(self, resume_id: str, file_path: str) -> dict:
    """
    解析简历文件，提取结构化信息。

    完整流程:
    1. 读取文件（PDF/DOCX/DOC/TXT）- 提取纯文本
    2. 清洗文本 - 去除噪音
    3. 质量评估 - 判断是否可用
    4. 获取LLM配置
    5. 调用LLM解析结构化信息
    6. 更新数据库记录（parsed_data + 状态）
    7. 生成向量嵌入（后续Agent实现）

    Args:
        resume_id: 简历记录UUID
        file_path: 文件存储路径

    Returns:
        解析结果摘要
    """
    logger.info(f"开始解析简历: resume_id={resume_id}, file={file_path}")

    try:
        # 确定文件扩展名
        file_extension = Path(file_path).suffix.lstrip(".")

        # Step 1: 获取LLM配置（从数据库或默认设置）
        llm_config = _get_llm_config()

        # Step 2-5: 提取文本 + 清洗 + 质量评估 + LLM解析（同步调用）
        result = parse_resume_sync(file_path, file_extension, llm_config=llm_config)

        logger.info(
            f"解析流程完成: resume_id={resume_id}, "
            f"quality={result.quality['quality_level']}, "
            f"score={result.quality['quality_score']}, "
            f"llm_parsed={result.is_parsed}"
        )

        # Step 6: 更新数据库
        if result.is_parsed:
            # LLM解析成功 → 完整写入
            _update_resume_completed(
                resume_id=resume_id,
                raw_text=result.raw_text,
                cleaned_text=result.cleaned_text,
                metadata=result.metadata,
                quality=result.quality,
                structured_data=result.structured_data,
            )
            logger.info(f"简历解析完成(completed): resume_id={resume_id}")
            return {
                "status": "completed",
                "resume_id": resume_id,
                "quality_score": result.quality["quality_score"],
                "quality_level": result.quality["quality_level"],
                "char_count": result.quality["char_count"],
                "is_usable": result.is_usable,
                "has_structured_data": True,
                "candidate_name": (result.structured_data or {}).get("basic_info", {}).get("name"),
            }
        else:
            # LLM解析失败但文本提取成功
            _update_resume_parse_failed(
                resume_id=resume_id,
                raw_text=result.raw_text,
                cleaned_text=result.cleaned_text,
                metadata=result.metadata,
                quality=result.quality,
                error_message=result.llm_error or "LLM解析未返回结果",
            )
            logger.warning(
                f"简历LLM解析失败: resume_id={resume_id}, error={result.llm_error}"
            )
            return {
                "status": "parse_failed",
                "resume_id": resume_id,
                "quality_score": result.quality["quality_score"],
                "quality_level": result.quality["quality_level"],
                "char_count": result.quality["char_count"],
                "is_usable": result.is_usable,
                "has_structured_data": False,
                "llm_error": result.llm_error,
            }

    except ExtractionError as exc:
        logger.error(
            f"简历文本提取失败: resume_id={resume_id}, "
            f"type={exc.file_type}, error={exc.message}"
        )
        _update_resume_error(resume_id, f"文本提取失败: {exc.message}")
        return {
            "status": "extraction_failed",
            "resume_id": resume_id,
            "error": exc.message,
        }

    except LLMAuthenticationError as exc:
        # H-4: 认证失败不重试，直接标记失败
        logger.error(
            f"LLM认证失败(不重试): resume_id={resume_id}, error={exc}"
        )
        _update_resume_error(
            resume_id,
            f"LLM认证失败，请检查LLM配置: {exc}",
        )
        return {
            "status": "auth_failed",
            "resume_id": resume_id,
            "error": f"LLM认证失败，请检查LLM配置: {exc}",
        }

    except (LLMTimeoutError, LLMRateLimitError, ConnectionError, TimeoutError) as exc:
        # H-4: 可重试错误由 autoretry_for 自动处理，此处仅日志后re-raise
        logger.warning(
            f"简历解析遇到可重试错误: resume_id={resume_id}, "
            f"retry={self.request.retries}/{self.max_retries}, error={exc}"
        )
        raise

    except Exception as exc:
        logger.error(f"简历解析异常: resume_id={resume_id}, error={exc}")
        # 未知异常：最终失败时标记
        if self.request.retries >= self.max_retries:
            _update_resume_error(resume_id, f"解析异常(重试耗尽): {exc}")
        return {
            "status": "failed",
            "resume_id": resume_id,
            "error": str(exc),
        }


@shared_task(
    bind=True,
    name="app.tasks.resume_tasks.batch_parse_resumes",
    max_retries=1,
)
def batch_parse_resumes(self, resume_ids: list[str]) -> dict:
    """
    批量解析简历（编排任务）

    将批量任务拆分为单个解析任务并行执行

    Args:
        resume_ids: 简历ID列表

    Returns:
        批次摘要
    """
    from celery import group

    logger.info(f"批量解析启动: count={len(resume_ids)}")

    # TODO: 查询每个resume_id对应的file_path
    # tasks = group(
    #     parse_resume.s(rid, path) for rid, path in resume_file_pairs
    # )
    # result = tasks.apply_async()

    return {"status": "dispatched", "count": len(resume_ids)}


@shared_task(
    name="app.tasks.resume_tasks.generate_resume_embedding",
    max_retries=3,
    default_retry_delay=10,
)
def generate_resume_embedding(resume_id: str, text: str) -> dict:
    """
    为简历文本生成向量嵌入并存储

    Args:
        resume_id: 简历记录UUID
        text: 简历文本内容

    Returns:
        嵌入生成结果
    """
    logger.info(f"生成嵌入: resume_id={resume_id}")

    embedding = _generate_embedding(text)
    # TODO: 存储到pgvector字段

    return {"status": "success", "resume_id": resume_id, "dimension": len(embedding)}


# ============================================================
# 内部辅助函数
# ============================================================


def _get_llm_config() -> dict | None:
    """
    获取LLM配置（同步版本，Celery中使用）。

    优先从数据库获取活跃配置，否则使用settings默认值。
    如果无法获取有效配置（例如api_key缺失），返回None。
    """
    from app.services.llm_resume_parser import get_active_llm_config_sync

    try:
        config = get_active_llm_config_sync(_sync_engine)

        # 验证配置有效性（ollama不需要api_key）
        if config["provider"] == "ollama":
            return config
        if not config.get("api_key"):
            logger.warning(
                f"LLM配置缺少api_key: provider={config['provider']}, "
                "将跳过LLM解析"
            )
            return None
        return config

    except Exception as e:
        logger.error(f"获取LLM配置失败: {e}")
        return None


def _update_resume_completed(
    resume_id: str,
    raw_text: str,
    cleaned_text: str,
    metadata: dict,
    quality: dict,
    structured_data: dict,
) -> None:
    """
    LLM解析成功：更新数据库，设置状态为completed，写入parsed_data。
    """
    # parsed_data 存储完整结构化数据
    parsed_data = {
        "structured": structured_data,
        "extraction_metadata": metadata,
        "quality_assessment": quality,
        "raw_text_length": len(raw_text),
        "cleaned_text_length": len(cleaned_text),
    }

    # 从structured_data中提取候选人基本信息用于快速搜索字段
    basic_info = structured_data.get("basic_info", {})
    candidate_name = basic_info.get("name")
    candidate_email = basic_info.get("email")
    candidate_phone = basic_info.get("phone")

    session = SyncSessionLocal()
    try:
        session.execute(
            text(
                "UPDATE resumes SET "
                "parse_status = 'completed', "
                "parsed_data = :parsed_data, "
                "candidate_name = COALESCE(:candidate_name, candidate_name), "
                "candidate_email = COALESCE(:candidate_email, candidate_email), "
                "candidate_phone = COALESCE(:candidate_phone, candidate_phone), "
                "parse_error = NULL, "
                "updated_at = NOW() "
                "WHERE id = :resume_id::uuid"
            ),
            {
                "parsed_data": json.dumps(parsed_data, ensure_ascii=False),
                "candidate_name": candidate_name,
                "candidate_email": candidate_email,
                "candidate_phone": candidate_phone,
                "resume_id": resume_id,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info(f"数据库已更新(completed): resume_id={resume_id}")


def _update_resume_parse_failed(
    resume_id: str,
    raw_text: str,
    cleaned_text: str,
    metadata: dict,
    quality: dict,
    error_message: str,
) -> None:
    """
    LLM解析失败但文本提取成功：更新数据库，设置状态为parse_failed。
    保留提取的文本信息以便后续重试。
    """
    parsed_data = {
        "raw_text": raw_text[:50000],
        "cleaned_text": cleaned_text[:50000],
        "extraction_metadata": metadata,
        "quality_assessment": quality,
    }

    session = SyncSessionLocal()
    try:
        session.execute(
            text(
                "UPDATE resumes SET "
                "parse_status = 'parse_failed', "
                "parsed_data = :parsed_data, "
                "parse_error = :error, "
                "updated_at = NOW() "
                "WHERE id = :resume_id::uuid"
            ),
            {
                "parsed_data": json.dumps(parsed_data, ensure_ascii=False),
                "error": error_message,
                "resume_id": resume_id,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _update_resume_error(resume_id: str, error_message: str) -> None:
    """更新简历记录的错误信息（文本提取阶段就失败了）"""
    session = SyncSessionLocal()
    try:
        session.execute(
            text(
                "UPDATE resumes SET "
                "parse_status = 'failed', "
                "parse_error = :error, "
                "updated_at = NOW() "
                "WHERE id = :resume_id::uuid"
            ),
            {
                "error": error_message,
                "resume_id": resume_id,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _generate_embedding(text: str) -> list[float]:
    """生成文本向量嵌入"""
    # TODO: 由另一个Agent实现 - 调用embedding API
    raise NotImplementedError("待实现: 向量嵌入生成")
