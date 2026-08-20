"""文件存储服务 - 简历文件的保存与验证"""

import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

import magic
from fastapi import UploadFile

from app.core.config import settings


class FileValidationError(Exception):
    """文件校验失败"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# ============================================================
# Magic-number 内容类型映射
# ============================================================

MAGIC_ALLOWED: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "txt": "text/plain",
    "jpg": "image/jpeg",
    "png": "image/png",
}


def validate_file(file: UploadFile) -> tuple[bool, str | None]:
    """
    校验上传文件的格式（仅扩展名初筛）。

    Args:
        file: FastAPI UploadFile对象

    Returns:
        (is_valid, error_message) - 校验通过时error_message为None
    """
    if not file.filename:
        return False, "文件名不能为空"

    ext = get_file_extension(file.filename)
    if not ext:
        return False, "文件缺少扩展名"

    if ext not in settings.ALLOWED_EXTENSIONS:
        allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
        return False, f"不支持的文件格式: .{ext}，允许格式: {allowed}"

    return True, None


def validate_file_content_type(content: bytes, claimed_ext: str) -> tuple[bool, str | None]:
    """
    使用 libmagic 对文件内容进行二次校验，确保文件真实类型与声明扩展名一致。

    Args:
        content: 文件二进制内容
        claimed_ext: 声明的文件扩展名（小写，不含点号）

    Returns:
        (is_valid, error_message) - 校验通过时error_message为None
    """
    if claimed_ext not in MAGIC_ALLOWED:
        return False, f"不支持的文件格式: .{claimed_ext}"

    expected_mime = MAGIC_ALLOWED[claimed_ext]
    detected_mime = magic.from_buffer(content, mime=True)

    # text/plain 检测可能返回多种 text/* 变体（如 text/x-python），这里放宽匹配
    if claimed_ext == "txt":
        if detected_mime.startswith("text/"):
            return True, None
    # JPEG 可能被检测为 image/jpeg
    elif claimed_ext == "jpg":
        if detected_mime in ("image/jpeg",):
            return True, None
    # docx 也可能被检测为 application/zip（因为docx本质是zip）
    elif claimed_ext == "docx":
        if detected_mime in (expected_mime, "application/zip", "application/x-zip-compressed"):
            return True, None
    # doc 老格式可能被检测为 application/x-ole-storage 或 application/CDFV2
    elif claimed_ext == "doc":
        if detected_mime in (expected_mime, "application/x-ole-storage", "application/CDFV2",
                            "application/vnd.ms-office"):
            return True, None
    else:
        if detected_mime == expected_mime:
            return True, None

    return False, (
        f"文件内容类型不匹配: 声明为 .{claimed_ext}（期望 {expected_mime}），"
        f"但实际检测为 {detected_mime}"
    )


def validate_file_size(content_length: int) -> tuple[bool, str | None]:
    """
    校验文件内容大小。

    Args:
        content_length: 文件字节数

    Returns:
        (is_valid, error_message)
    """
    if content_length > settings.MAX_FILE_SIZE:
        max_mb = settings.MAX_FILE_SIZE // (1024 * 1024)
        actual_mb = round(content_length / (1024 * 1024), 2)
        return False, f"文件大小 {actual_mb}MB 超过限制 {max_mb}MB"
    return True, None


async def save_upload_file(file: UploadFile, content: bytes) -> str:
    """
    保存上传文件到磁盘。

    文件保存路径格式：uploads/YYYY/MM/DD/uuid_filename.ext
    例如：uploads/2024/08/20/a1b2c3d4_resume.pdf

    Args:
        file: FastAPI UploadFile对象
        content: 文件二进制内容

    Returns:
        文件存储路径
    """
    now = datetime.now(timezone.utc)
    date_dir = now.strftime("%Y/%m/%d")

    # 生成唯一文件名：uuid_原始文件名
    file_uuid = uuid.uuid4().hex[:8]
    safe_filename = _sanitize_filename(file.filename or "unknown")
    stored_name = f"{file_uuid}_{safe_filename}"

    # 构建完整路径
    upload_base = Path(settings.UPLOAD_DIR)
    target_dir = upload_base / date_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / stored_name
    file_path.write_bytes(content)

    return str(file_path)


async def delete_file(file_path: str) -> None:
    """
    删除已写入磁盘的文件（用于事务回滚时清理）。

    Args:
        file_path: 文件路径
    """
    path = Path(file_path)
    if path.exists():
        path.unlink()


def get_file_path(stored_path: str) -> Path:
    """
    获取文件的Path对象。

    Args:
        stored_path: 数据库中存储的文件路径

    Returns:
        文件的Path对象
    """
    return Path(stored_path)


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写）"""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除路径分隔符和特殊字符。
    保留原始文件名的可读性，确保安全存储。

    安全措施：
    1. NFKC标准化（处理Unicode变体攻击）
    2. 跨平台取basename
    3. 移除控制字符和不可见字符
    4. 白名单模式：只允许安全字符
    5. 移除连续点号
    6. 限制长度
    """
    # 1. NFKC标准化（处理Unicode变体）
    name = unicodedata.normalize("NFKC", filename)

    # 2. 跨平台取basename
    name = name.replace("\\", "/")
    name = name.split("/")[-1]

    # 3. 移除控制字符和不可见字符
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '_', name)

    # 4. 只允许安全字符（字母、数字、点、横杠、下划线、空格、中文等Unicode字母数字）
    name = re.sub(r'[^\w.\-\s]', '_', name, flags=re.UNICODE)

    # 5. 移除连续点号（防止目录遍历变体）
    name = re.sub(r'\.{2,}', '.', name)

    # 6. 限制长度
    if len(name) > 200:
        parts = name.rsplit('.', 1)
        if len(parts) == 2:
            name = parts[0][:195] + '.' + parts[1]
        else:
            name = name[:200]

    return name.strip() or "unnamed"
