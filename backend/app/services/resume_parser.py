"""简历解析服务 - 文档提取、文本清洗与LLM结构化解析的集成入口"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.document_extractor import ExtractionError, extract_text
from app.services.text_preprocessor import clean_resume_text, estimate_resume_quality

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """简历解析结果"""

    raw_text: str
    cleaned_text: str
    metadata: dict
    quality: dict
    structured_data: dict | None = field(default=None)
    llm_error: str | None = field(default=None)

    @property
    def is_usable(self) -> bool:
        """文本质量是否可用于后续LLM解析"""
        return self.quality.get("quality_level") in ("high", "medium")

    @property
    def is_parsed(self) -> bool:
        """LLM结构化解析是否成功"""
        return self.structured_data is not None


async def parse_resume(
    file_path: str,
    file_extension: str | None = None,
    llm_config: dict | None = None,
) -> ParseResult:
    """
    简历解析主入口：文本提取 + 清洗 + 质量评估 + LLM结构化解析。

    流程：
    1. 确定文件格式
    2. 调用 extract_text() 提取原始文本
    3. 调用 clean_resume_text() 清洗
    4. 调用 estimate_resume_quality() 评估质量
    5. 如果文本质量可用且提供了LLM配置，调用LLM结构化解析
    6. 返回完整解析结果

    Args:
        file_path: 文件路径
        file_extension: 文件扩展名（不含点号）。
                       如果未提供，从文件路径推断。
        llm_config: LLM配置字典（可选）。
                   格式: {provider, api_key, model_name, endpoint, timeout}
                   如果不传，则只做文本提取不做LLM解析。

    Returns:
        ParseResult 包含原始文本、清洗后文本、元数据、质量评估和结构化数据

    Raises:
        ExtractionError: 文件格式不支持或提取失败
        FileNotFoundError: 文件不存在
    """
    # 确定扩展名
    if not file_extension:
        file_extension = Path(file_path).suffix.lstrip(".")

    if not file_extension:
        raise ExtractionError("无法确定文件格式：缺少扩展名", file_type="unknown")

    file_extension = file_extension.lower()
    logger.info(f"开始解析简历: path={file_path}, ext={file_extension}")

    # Step 1: 提取文本
    raw_text, metadata = await extract_text(file_path, file_extension)

    # Step 2: 清洗文本
    cleaned_text = clean_resume_text(raw_text)

    # Step 3: 质量评估
    quality = estimate_resume_quality(cleaned_text)

    # 记录质量信息
    logger.info(
        f"简历文本提取完成: path={file_path}, "
        f"quality_score={quality['quality_score']}, "
        f"quality_level={quality['quality_level']}, "
        f"sections={quality['estimated_sections']}"
    )

    if not quality.get("quality_level") or quality["quality_level"] == "unusable":
        logger.warning(f"简历文本质量过低: path={file_path}, score={quality['quality_score']}")

    # Step 4: LLM结构化解析（如果条件满足）
    structured_data = None
    llm_error = None

    if llm_config and quality.get("quality_level") in ("high", "medium"):
        structured_data, llm_error = await _run_llm_parse(cleaned_text, llm_config)
    elif llm_config and quality.get("quality_level") not in ("high", "medium"):
        llm_error = f"文本质量过低({quality.get('quality_level')})，跳过LLM解析"
        logger.warning(llm_error)

    return ParseResult(
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        metadata=metadata,
        quality=quality,
        structured_data=structured_data,
        llm_error=llm_error,
    )


async def _run_llm_parse(cleaned_text: str, llm_config: dict) -> tuple[dict | None, str | None]:
    """
    执行LLM结构化解析（隔离异常）。

    Returns:
        (structured_data, error_message) — 成功时error为None，失败时data为None
    """
    from app.services.llm_resume_parser import LLMParseError, LLMResumeParser

    try:
        # 构建LLM参数
        llm_kwargs: dict[str, Any] = {}
        if llm_config.get("api_key"):
            llm_kwargs["api_key"] = llm_config["api_key"]
        if llm_config.get("model_name"):
            llm_kwargs["model_name"] = llm_config["model_name"]
        if llm_config.get("endpoint"):
            llm_kwargs["endpoint"] = llm_config["endpoint"]
        if llm_config.get("timeout"):
            llm_kwargs["timeout"] = llm_config["timeout"]

        parser = LLMResumeParser(
            provider=llm_config["provider"],
            **llm_kwargs,
        )
        result = await parser.parse(cleaned_text)
        return result, None

    except LLMParseError as e:
        logger.error(f"LLM解析失败: {e}")
        return None, str(e)

    except Exception as e:
        logger.error(f"LLM解析意外异常: {type(e).__name__}: {e}")
        return None, f"LLM解析意外异常: {type(e).__name__}: {e}"


# ============================================================
# 同步版本（供Celery任务使用）
# ============================================================


def parse_resume_sync(
    file_path: str,
    file_extension: str | None = None,
    llm_config: dict | None = None,
) -> ParseResult:
    """
    parse_resume 的同步包装版本，供Celery worker调用。

    Args:
        file_path: 文件路径
        file_extension: 文件扩展名
        llm_config: LLM配置（可选）

    Returns:
        ParseResult
    """
    import asyncio

    return asyncio.run(parse_resume(file_path, file_extension, llm_config))
