"""LLM Prompt模板"""

from app.llm.prompts.resume_parse import (
    RESUME_PARSE_OUTPUT_SCHEMA,
    RESUME_PARSE_SYSTEM_PROMPT,
    RESUME_PARSE_USER_TEMPLATE,
    build_resume_parse_messages,
)

__all__ = [
    "RESUME_PARSE_SYSTEM_PROMPT",
    "RESUME_PARSE_USER_TEMPLATE",
    "RESUME_PARSE_OUTPUT_SCHEMA",
    "build_resume_parse_messages",
]
