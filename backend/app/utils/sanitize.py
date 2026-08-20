"""错误信息脱敏工具

从错误消息中移除可能泄露的API Key、Bearer Token等敏感信息。
"""

import re

# 匹配常见API Key / Token模式
_SENSITIVE_PATTERNS = [
    (re.compile(r"(sk-)[a-zA-Z0-9_-]{10,}", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"(key-)[a-zA-Z0-9_-]{10,}", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9_.\-]{10,}", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"(api[_\-]?key[=:\s]+)[a-zA-Z0-9_\-]{10,}", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"(token[=:\s]+)[a-zA-Z0-9_.\-]{10,}", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"(secret[=:\s]+)[a-zA-Z0-9_.\-]{10,}", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"(password[=:\s]+)\S{6,}", re.IGNORECASE), r"\1***REDACTED***"),
]


def sanitize_error_message(msg: str) -> str:
    """从错误信息中移除可能的API Key和敏感信息。

    对常见的密钥模式进行正则匹配和替换，保留前缀以便调试定位，
    但隐藏实际密钥值。

    Args:
        msg: 原始错误信息

    Returns:
        脱敏后的错误信息
    """
    if not msg:
        return msg

    result = msg
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result
