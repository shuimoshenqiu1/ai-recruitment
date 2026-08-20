"""LLM 简历解析服务

使用LLM将简历纯文本解析为结构化JSON数据。
包含结果验证、字段清理、重试逻辑和配置管理。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.llm.base import (
    LLMError,
    LLMRateLimitError,
    LLMResponseParseError,
    LLMTimeoutError,
)
from app.llm.factory import LLMFactory
from app.llm.prompts.resume_parse import build_resume_parse_messages
from app.utils.sanitize import sanitize_error_message

logger = logging.getLogger(__name__)

# 最大重试次数
MAX_RETRIES = 2

# 简历文本长度限制（避免token超限）
MAX_RESUME_TEXT_LENGTH = 30000


class LLMParseError(Exception):
    """LLM解析失败异常"""

    def __init__(self, message: str, retry_count: int = 0, raw_response: str | None = None):
        self.retry_count = retry_count
        self.raw_response = raw_response
        super().__init__(message)


class LLMResumeParser:
    """
    使用LLM解析简历文本为结构化数据。

    负责：
    1. 构建prompt消息
    2. 调用LLM获取JSON响应
    3. 验证和清理输出结果
    4. 错误处理与重试

    Usage:
        parser = LLMResumeParser(provider="openai", api_key="sk-...")
        result = await parser.parse("张三的简历文本...")
    """

    def __init__(self, provider: str = "openai", **llm_kwargs: Any):
        """
        初始化解析器。

        Args:
            provider: LLM提供商标识
            **llm_kwargs: 传递给 LLMFactory.create 的参数
                - api_key: API密钥
                - model_name: 模型名称
                - endpoint: 自定义端点
                - timeout: 超时秒数
        """
        self.provider_name = provider
        self.llm = LLMFactory.create(provider, **llm_kwargs)
        logger.info(f"LLMResumeParser 初始化: provider={provider}, model={self.llm.model_name}")

    async def parse(self, resume_text: str) -> dict:
        """
        解析简历文本，返回结构化JSON。

        包含重试逻辑：LLM返回无效JSON时最多重试 MAX_RETRIES 次。

        Args:
            resume_text: 清洗后的简历纯文本

        Returns:
            结构化简历数据字典

        Raises:
            LLMParseError: LLM调用失败或多次重试后仍无法获得有效结果
        """
        if not resume_text or not resume_text.strip():
            raise LLMParseError("简历文本为空，无法解析")

        # 截断过长文本
        truncated_text = resume_text[:MAX_RESUME_TEXT_LENGTH]
        if len(resume_text) > MAX_RESUME_TEXT_LENGTH:
            logger.warning(
                f"简历文本过长({len(resume_text)}字符)，已截断至{MAX_RESUME_TEXT_LENGTH}字符"
            )

        messages = build_resume_parse_messages(truncated_text)

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 2):  # 1次初始 + MAX_RETRIES次重试
            try:
                logger.info(f"LLM解析尝试 #{attempt}, provider={self.provider_name}")

                result = await self.llm.chat_json(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=4096,
                )

                # 验证和清理
                validated = self._validate_and_clean(result)
                logger.info(f"LLM解析成功: attempt={attempt}")
                return validated

            except LLMResponseParseError as e:
                last_error = e
                logger.warning(f"LLM返回无效JSON (attempt {attempt}): {sanitize_error_message(str(e))}")
                if attempt > MAX_RETRIES + 1:
                    break
                # 继续重试

            except LLMRateLimitError as e:
                # 速率限制不重试，立即抛出
                raise LLMParseError(
                    f"LLM速率限制: {sanitize_error_message(str(e))}",
                    retry_count=attempt - 1,
                ) from e

            except LLMTimeoutError as e:
                last_error = e
                logger.warning(f"LLM请求超时 (attempt {attempt}): {sanitize_error_message(str(e))}")
                if attempt > MAX_RETRIES + 1:
                    break

            except LLMError as e:
                last_error = e
                logger.error(f"LLM调用错误 (attempt {attempt}): {sanitize_error_message(str(e))}")
                if attempt > MAX_RETRIES + 1:
                    break

        # 所有重试用尽
        raise LLMParseError(
            f"LLM解析失败，已重试{MAX_RETRIES}次: {sanitize_error_message(str(last_error))}",
            retry_count=MAX_RETRIES,
        )

    def _validate_and_clean(self, raw_result: dict) -> dict:
        """
        验证和清理LLM输出。

        处理：
        - 缺失的顶级字段（补充空值）
        - 类型不匹配（尝试修正）
        - 去除多余空白

        Args:
            raw_result: LLM返回的原始字典

        Returns:
            清理后的结构化数据
        """
        cleaned: dict[str, Any] = {}

        # --- basic_info ---
        basic_info = raw_result.get("basic_info", {})
        if not isinstance(basic_info, dict):
            basic_info = {}

        cleaned["basic_info"] = {
            "name": _clean_str(basic_info.get("name")),
            "gender": _clean_str(basic_info.get("gender")),
            "age": _clean_int(basic_info.get("age")),
            "phone": _clean_phone(basic_info.get("phone")),
            "email": _clean_str(basic_info.get("email")),
            "location": _clean_str(basic_info.get("location")),
            "expected_salary": _clean_str(basic_info.get("expected_salary")),
        }

        # --- education ---
        cleaned["education"] = _clean_list_of_dicts(
            raw_result.get("education", []),
            required_keys=["school", "degree"],
            schema={
                "school": _clean_str,
                "major": _clean_str,
                "degree": _clean_str,
                "start_date": _clean_date,
                "end_date": _clean_date,
                "gpa": _clean_str,
            },
        )

        # --- work_experience ---
        cleaned["work_experience"] = _clean_list_of_dicts(
            raw_result.get("work_experience", []),
            required_keys=["company", "position"],
            schema={
                "company": _clean_str,
                "position": _clean_str,
                "start_date": _clean_date,
                "end_date": _clean_date,
                "description": _clean_str,
                "achievements": _clean_str_list,
            },
        )

        # --- skills ---
        cleaned["skills"] = _clean_list_of_dicts(
            raw_result.get("skills", []),
            required_keys=["name"],
            schema={
                "name": _clean_str,
                "level": _clean_skill_level,
                "years": _clean_int,
            },
        )

        # --- projects ---
        cleaned["projects"] = _clean_list_of_dicts(
            raw_result.get("projects", []),
            required_keys=["name"],
            schema={
                "name": _clean_str,
                "role": _clean_str,
                "description": _clean_str,
                "tech_stack": _clean_str_list,
                "achievements": _clean_str_list,
            },
        )

        # --- certifications ---
        cleaned["certifications"] = _clean_list_of_dicts(
            raw_result.get("certifications", []),
            required_keys=["name"],
            schema={
                "name": _clean_str,
                "date": _clean_date,
                "issuer": _clean_str,
            },
        )

        # --- languages ---
        cleaned["languages"] = _clean_list_of_dicts(
            raw_result.get("languages", []),
            required_keys=["language"],
            schema={
                "language": _clean_str,
                "level": _clean_str,
            },
        )

        return cleaned


# ============================================================
# LLM配置获取
# ============================================================


async def get_active_llm_config(db_session) -> dict:
    """
    获取当前活跃的LLM配置。

    优先从数据库 llm_configs 表获取 is_active=True 的记录，
    如果没有活跃配置，从 settings 读取默认值。

    Args:
        db_session: SQLAlchemy async session

    Returns:
        dict: {provider, api_key, model_name, endpoint, extra_config}
    """
    from sqlalchemy import select

    from app.core.config import settings
    from app.models.llm_config import LLMConfig

    # 查询活跃配置（优先取 is_default=True 的）
    stmt = (
        select(LLMConfig)
        .where(LLMConfig.is_active == True)  # noqa: E712
        .order_by(LLMConfig.is_default.desc(), LLMConfig.updated_at.desc())
        .limit(1)
    )

    result = await db_session.execute(stmt)
    config_record = result.scalar_one_or_none()

    if config_record:
        logger.info(
            f"使用数据库LLM配置: name={config_record.name}, "
            f"provider={config_record.provider_type}, "
            f"model={config_record.model_name}"
        )
        extra = config_record.config or {}
        return {
            "provider": config_record.provider_type,
            "api_key": config_record.api_key,
            "model_name": config_record.model_name,
            "endpoint": config_record.endpoint,
            "timeout": extra.get("timeout", settings.LLM_REQUEST_TIMEOUT),
        }

    # 没有数据库配置，使用settings默认值
    logger.info(f"使用默认LLM配置: provider={settings.DEFAULT_LLM_PROVIDER}")
    return {
        "provider": settings.DEFAULT_LLM_PROVIDER,
        "api_key": None,  # 需要从环境变量获取
        "model_name": None,  # 使用provider默认模型
        "endpoint": None,  # 使用provider默认endpoint
        "timeout": settings.LLM_REQUEST_TIMEOUT,
    }


def get_active_llm_config_sync(sync_engine) -> dict:
    """
    get_active_llm_config 的同步版本，供Celery worker使用。

    Args:
        sync_engine: 同步SQLAlchemy engine

    Returns:
        dict: {provider, api_key, model_name, endpoint, timeout}
    """
    from sqlalchemy import select, text

    from app.core.config import settings
    from app.models.llm_config import LLMConfig

    with sync_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT provider_type, api_key, model_name, endpoint, config "
                "FROM llm_configs "
                "WHERE is_active = true "
                "ORDER BY is_default DESC, updated_at DESC "
                "LIMIT 1"
            )
        )
        row = result.fetchone()

    if row:
        extra = row[4] or {}  # config JSONB column
        logger.info(
            f"[sync] 使用数据库LLM配置: provider={row[0]}, model={row[2]}"
        )
        return {
            "provider": row[0],
            "api_key": row[1],
            "model_name": row[2],
            "endpoint": row[3],
            "timeout": extra.get("timeout", settings.LLM_REQUEST_TIMEOUT),
        }

    logger.info(f"[sync] 使用默认LLM配置: provider={settings.DEFAULT_LLM_PROVIDER}")
    return {
        "provider": settings.DEFAULT_LLM_PROVIDER,
        "api_key": None,
        "model_name": None,
        "endpoint": None,
        "timeout": settings.LLM_REQUEST_TIMEOUT,
    }


# ============================================================
# 内部辅助函数 - 字段清理
# ============================================================


def _clean_str(value: Any) -> str | None:
    """清理字符串字段：去除前后空白，空字符串转None"""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _clean_int(value: Any) -> int | None:
    """清理整数字段"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        # 尝试从字符串提取数字
        digits = re.findall(r"\d+", value)
        if digits:
            return int(digits[0])
    return None


def _clean_phone(value: Any) -> str | None:
    """清理电话号码：保留数字和常用分隔符"""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # 移除除数字、+、-、空格、()以外的字符
    cleaned = re.sub(r"[^\d+\-\s()]", "", s)
    return cleaned if cleaned else None


def _clean_date(value: Any) -> str | None:
    """
    清理日期字段，统一为 YYYY-MM 格式。
    处理各种常见日期格式。
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("至今", "present", "now", "current", "null"):
        return None

    # 已经是 YYYY-MM 格式
    if re.match(r"^\d{4}-\d{2}$", s):
        return s

    # YYYY-MM-DD 格式
    match = re.match(r"^(\d{4})-(\d{2})-\d{2}$", s)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # YYYY/MM 或 YYYY.MM 格式
    match = re.match(r"^(\d{4})[/.](\d{1,2})", s)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"

    # YYYY年MM月 格式
    match = re.match(r"^(\d{4})年(\d{1,2})月?", s)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"

    # 仅年份
    match = re.match(r"^(\d{4})$", s)
    if match:
        return f"{match.group(1)}-01"

    return s  # 无法识别的格式原样返回


def _clean_skill_level(value: Any) -> str | None:
    """清理技能等级字段，标准化为四级"""
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None

    # 标准化映射
    level_map = {
        "精通": "精通",
        "expert": "精通",
        "advanced": "精通",
        "熟练": "熟练",
        "proficient": "熟练",
        "intermediate": "熟练",
        "熟悉": "熟悉",
        "familiar": "熟悉",
        "了解": "了解",
        "basic": "了解",
        "beginner": "了解",
    }

    for key, level in level_map.items():
        if key in s:
            return level

    return _clean_str(value)  # 无法识别的原样返回


def _clean_str_list(value: Any) -> list[str]:
    """清理字符串列表字段"""
    if value is None:
        return []
    if isinstance(value, str):
        # 可能是逗号分隔的字符串
        return [s.strip() for s in value.split(",") if s.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if item and str(item).strip()]
    return []


def _clean_list_of_dicts(
    items: Any,
    required_keys: list[str],
    schema: dict,
) -> list[dict]:
    """
    清理字典列表字段。

    Args:
        items: 原始列表数据
        required_keys: 必须存在且非空的字段名
        schema: 字段名 -> 清理函数 的映射

    Returns:
        清理后的字典列表（过滤掉缺少必要字段的条目）
    """
    if not isinstance(items, list):
        return []

    cleaned_items = []
    for item in items:
        if not isinstance(item, dict):
            continue

        cleaned_item = {}
        for field_name, cleaner in schema.items():
            raw_value = item.get(field_name)
            cleaned_item[field_name] = cleaner(raw_value)

        # 检查必要字段是否存在
        if all(cleaned_item.get(k) for k in required_keys):
            cleaned_items.append(cleaned_item)

    return cleaned_items
