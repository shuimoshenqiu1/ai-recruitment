"""LLM Prompt模板"""

from app.llm.prompts.matching import (
    MATCHING_OUTPUT_SCHEMA,
    MATCHING_SYSTEM_PROMPT,
    MATCHING_USER_TEMPLATE,
    build_matching_messages,
)
from app.llm.prompts.resume_parse import (
    RESUME_PARSE_OUTPUT_SCHEMA,
    RESUME_PARSE_SYSTEM_PROMPT,
    RESUME_PARSE_USER_TEMPLATE,
    build_resume_parse_messages,
)

__all__ = [
    # 简历解析
    "RESUME_PARSE_SYSTEM_PROMPT",
    "RESUME_PARSE_USER_TEMPLATE",
    "RESUME_PARSE_OUTPUT_SCHEMA",
    "build_resume_parse_messages",
    # AI匹配
    "MATCHING_SYSTEM_PROMPT",
    "MATCHING_USER_TEMPLATE",
    "MATCHING_OUTPUT_SCHEMA",
    "build_matching_messages",
]
