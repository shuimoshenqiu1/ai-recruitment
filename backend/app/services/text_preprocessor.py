"""简历文本预处理 - 清洗、标准化、质量评估"""

import re
import unicodedata


# ============================================================
# 文本清洗
# ============================================================

# 常见页眉页脚模式
_HEADER_FOOTER_PATTERNS = [
    r"^第\s*\d+\s*页.*$",  # 中文页码
    r"^Page\s+\d+\s*(of\s+\d+)?\s*$",  # 英文页码
    r"^\d+\s*/\s*\d+\s*$",  # "1/3" 格式页码
    r"^-\s*\d+\s*-\s*$",  # "- 1 -" 格式页码
    r"^(Confidential|CONFIDENTIAL|机密|保密).*$",  # 保密标记
    r"^(Generated|Exported|Downloaded)\s+(by|from|on).*$",  # 导出水印
    r"^\s*www\.\S+\s*$",  # 网站水印
]
_HEADER_FOOTER_RE = re.compile(
    "|".join(f"({p})" for p in _HEADER_FOOTER_PATTERNS),
    re.MULTILINE | re.IGNORECASE,
)


def clean_resume_text(raw_text: str) -> str:
    """
    清理简历文本，去除多余空白、页眉页脚和特殊字符。

    处理步骤：
    1. 标准化空白字符（全角空格→半角）
    2. 去除不可打印字符（保留换行和制表符）
    3. 去除页眉页脚常见模式
    4. 合并多余空行（3+空行→2行）
    5. 去除行首尾多余空白

    Args:
        raw_text: 原始提取文本

    Returns:
        清洗后的文本
    """
    if not raw_text:
        return ""

    text = raw_text

    # 1. 标准化空白字符
    text = _normalize_whitespace(text)

    # 2. 去除不可打印字符
    text = _remove_unprintable(text)

    # 3. 去除页眉页脚模式
    text = _remove_headers_footers(text)

    # 4. 合并多余空行
    text = _collapse_blank_lines(text)

    # 5. 去除行首尾多余空白
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)

    return text.strip()


def _normalize_whitespace(text: str) -> str:
    """标准化空白字符"""
    # 全角空格 → 半角空格
    text = text.replace("\u3000", " ")
    # 不间断空格 → 普通空格
    text = text.replace("\u00a0", " ")
    # 零宽字符去除
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    # 制表符标准化为4空格
    text = text.replace("\t", "    ")
    # 行内多个空格合并（保留换行）
    text = re.sub(r"[^\S\n]+", " ", text)
    return text


def _remove_unprintable(text: str) -> str:
    """去除不可打印字符，保留换行和基本空白"""
    cleaned_chars = []
    for ch in text:
        if ch in ("\n", "\r", " "):
            cleaned_chars.append(ch)
        elif unicodedata.category(ch).startswith("C"):
            # 控制字符，跳过
            continue
        else:
            cleaned_chars.append(ch)
    # 统一换行符
    return "".join(cleaned_chars).replace("\r\n", "\n").replace("\r", "\n")


def _remove_headers_footers(text: str) -> str:
    """去除页眉页脚常见模式"""
    return _HEADER_FOOTER_RE.sub("", text)


def _collapse_blank_lines(text: str) -> str:
    """合并连续空行：3+空行合并为2行"""
    return re.sub(r"\n{3,}", "\n\n", text)


# ============================================================
# 质量评估
# ============================================================

# 常见简历section关键词
_SECTION_KEYWORDS_ZH = [
    "个人信息", "基本信息", "联系方式",
    "教育背景", "教育经历", "学历",
    "工作经历", "工作经验", "实习经历",
    "项目经历", "项目经验",
    "专业技能", "技能特长", "技术栈",
    "自我评价", "个人总结", "求职意向",
    "证书", "获奖", "荣誉", "培训",
]

_SECTION_KEYWORDS_EN = [
    "education", "experience", "work experience",
    "skills", "projects", "summary", "objective",
    "certifications", "achievements", "awards",
    "contact", "profile", "qualifications",
]


def estimate_resume_quality(text: str) -> dict:
    """
    评估简历文本的提取质量。

    返回字符数、行数、语言检测、章节估计、质量评分等指标。

    Args:
        text: 已清洗的简历文本

    Returns:
        质量评估字典，包含：
        - char_count: 字符数
        - line_count: 行数
        - has_chinese: 是否包含中文
        - has_english: 是否包含英文
        - estimated_sections: 检测到的章节数
        - detected_sections: 检测到的具体章节关键词
        - quality_score: 0-100的质量评分
        - quality_level: 质量等级（high/medium/low/unusable）
    """
    if not text:
        return {
            "char_count": 0,
            "line_count": 0,
            "has_chinese": False,
            "has_english": False,
            "estimated_sections": 0,
            "detected_sections": [],
            "quality_score": 0,
            "quality_level": "unusable",
        }

    char_count = len(text)
    line_count = text.count("\n") + 1
    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_english = bool(re.search(r"[a-zA-Z]", text))

    # 检测章节
    detected_sections = _detect_sections(text)
    estimated_sections = len(detected_sections)

    # 计算质量评分
    quality_score = _calculate_quality(
        text, char_count, line_count, has_chinese, has_english, estimated_sections
    )

    # 确定质量等级
    if quality_score >= 70:
        quality_level = "high"
    elif quality_score >= 40:
        quality_level = "medium"
    elif quality_score >= 15:
        quality_level = "low"
    else:
        quality_level = "unusable"

    return {
        "char_count": char_count,
        "line_count": line_count,
        "has_chinese": has_chinese,
        "has_english": has_english,
        "estimated_sections": estimated_sections,
        "detected_sections": detected_sections,
        "quality_score": quality_score,
        "quality_level": quality_level,
    }


def _detect_sections(text: str) -> list[str]:
    """检测简历中的章节关键词"""
    text_lower = text.lower()
    found = []

    for kw in _SECTION_KEYWORDS_ZH:
        if kw in text:
            found.append(kw)

    for kw in _SECTION_KEYWORDS_EN:
        if kw in text_lower:
            found.append(kw)

    return found


def _calculate_quality(
    text: str,
    char_count: int,
    line_count: int,
    has_chinese: bool,
    has_english: bool,
    section_count: int,
) -> int:
    """
    计算文本质量评分（0-100）。

    评分维度：
    - 长度充足性（30分）：100-5000字符为最佳
    - 结构性（30分）：检测到的章节数
    - 信息密度（20分）：非空白字符比例
    - 语言丰富度（10分）：中英文混合加分
    - 行结构（10分）：有合理的行数分布
    """
    score = 0

    # 长度充足性（30分）
    if char_count < 50:
        score += 0
    elif char_count < 100:
        score += 5
    elif char_count < 300:
        score += 15
    elif char_count <= 8000:
        score += 30
    elif char_count <= 15000:
        score += 25
    else:
        score += 20  # 过长可能有噪音

    # 结构性（30分）
    section_score = min(section_count * 6, 30)
    score += section_score

    # 信息密度（20分）
    non_space = len(re.sub(r"\s", "", text))
    density = non_space / max(char_count, 1)
    if 0.5 <= density <= 0.9:
        score += 20
    elif 0.3 <= density < 0.5:
        score += 10
    else:
        score += 5

    # 语言丰富度（10分）
    if has_chinese and has_english:
        score += 10
    elif has_chinese or has_english:
        score += 6
    else:
        score += 0

    # 行结构（10分）
    avg_line_len = char_count / max(line_count, 1)
    if 20 <= avg_line_len <= 120:
        score += 10
    elif 10 <= avg_line_len <= 200:
        score += 6
    else:
        score += 2

    return min(score, 100)
