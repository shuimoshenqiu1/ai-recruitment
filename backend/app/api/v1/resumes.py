"""简历管理路由"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.crud.resume import (
    create_resume,
    get_resume,
    get_resumes,
    soft_delete_resume,
    update_resume_status,
)
from app.models.user import User
from app.schemas.common import APIResponse, PageResponse
from app.schemas.resume import (
    BatchUploadFileResult,
    BatchUploadResponse,
    ParsedResumeData,
    ResumeResponse,
    ResumeUploadResult,
)
from app.services.file_storage import (
    delete_file,
    get_file_extension,
    save_upload_file,
    validate_file,
    validate_file_content_type,
    validate_file_size,
)
from app.tasks.resume_tasks import parse_resume

router = APIRouter()

# ============================================================
# 常量
# ============================================================

MAX_BATCH_SIZE = 100
CHUNK_SIZE = 64 * 1024  # 64KB


# ============================================================
# 内部工具函数
# ============================================================


async def _read_file_chunked(file: UploadFile) -> bytes:
    """
    分块读取上传文件，超过 MAX_FILE_SIZE 立即中断。
    避免巨大文件一次性加载到内存。

    Raises:
        HTTPException(413): 文件超过大小限制
    """
    total_read = 0
    chunks: list[bytes] = []

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > settings.MAX_FILE_SIZE:
            max_mb = settings.MAX_FILE_SIZE // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件大小超过限制({max_mb}MB)",
            )
        chunks.append(chunk)

    return b"".join(chunks)


# ============================================================
# 路由
# ============================================================


@router.post("/upload", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume_endpoint(
    file: UploadFile = File(..., description="简历文件(pdf/docx/doc/txt/jpg/png)"),
    candidate_name: str | None = Form(default=None, description="候选人姓名"),
    candidate_email: str | None = Form(default=None, description="候选人邮箱"),
    candidate_phone: str | None = Form(default=None, description="候选人电话"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    上传单个简历文件。

    - 支持格式：pdf, docx, doc, txt, jpg, png
    - 最大文件大小：20MB
    - 上传后自动触发异步解析任务
    - 返回resume_id和当前状态
    """
    # 1. 扩展名初筛
    is_valid, error_msg = validate_file(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # 2. 分块读取文件内容（超限立即中断）
    content = await _read_file_chunked(file)

    # 3. Magic-number 内容类型二次校验
    ext = get_file_extension(file.filename or "")
    is_valid, error_msg = validate_file_content_type(content, ext)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # 4. 保存文件到磁盘
    file_path = await save_upload_file(file, content)

    # 5. 创建数据库记录
    try:
        resume = await create_resume(
            db,
            user_id=current_user.id,
            file_name=file.filename or "unknown",
            file_path=file_path,
            file_type=ext,
            file_size=len(content),
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
        )
    except Exception:
        # DB失败则清理已写入的文件
        await delete_file(file_path)
        raise

    # 6. 触发Celery异步解析任务（仅在DB成功后）
    parse_resume.delay(str(resume.id), file_path)

    # 7. 返回结果
    result = ResumeUploadResult(
        resume_id=resume.id,
        file_name=resume.file_name,
        parse_status=resume.parse_status,
    )
    return APIResponse.success(data=result.model_dump(mode="json"), message="上传成功，解析任务已提交")


@router.post("/batch-upload", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def batch_upload_resumes(
    files: list[UploadFile] = File(..., description="简历文件列表"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    批量上传简历文件。

    - 单次最多100份
    - 逐个校验格式和大小
    - 每个文件使用 savepoint 隔离，单个失败不影响其他
    - 处理顺序：校验 -> DB记录 -> 写文件 -> 触发Celery
    - 返回每个文件的上传结果（成功/失败）
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供任何文件",
        )

    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"单次最多上传 {MAX_BATCH_SIZE} 份文件，当前提交 {len(files)} 份",
        )

    results: list[BatchUploadFileResult] = []
    success_count = 0
    failed_count = 0

    for file in files:
        file_name = file.filename or "unknown"

        # --- 阶段1: 校验（扩展名 + 大小 + 内容类型）---
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            results.append(BatchUploadFileResult(
                file_name=file_name,
                success=False,
                error=error_msg,
            ))
            failed_count += 1
            continue

        # 分块读取文件内容
        try:
            content = await _read_file_chunked(file)
        except HTTPException as e:
            results.append(BatchUploadFileResult(
                file_name=file_name,
                success=False,
                error=e.detail,
            ))
            failed_count += 1
            continue
        except Exception:
            results.append(BatchUploadFileResult(
                file_name=file_name,
                success=False,
                error="文件读取失败",
            ))
            failed_count += 1
            continue

        # 内容类型二次校验
        ext = get_file_extension(file_name)
        is_valid, error_msg = validate_file_content_type(content, ext)
        if not is_valid:
            results.append(BatchUploadFileResult(
                file_name=file_name,
                success=False,
                error=error_msg,
            ))
            failed_count += 1
            continue

        # --- 阶段2: 使用 savepoint 隔离每个文件的DB操作 ---
        file_path: str | None = None
        try:
            async with db.begin_nested():
                # DB记录（在savepoint内）
                resume = await create_resume(
                    db,
                    user_id=current_user.id,
                    file_name=file_name,
                    file_path="",  # 先占位，写文件成功后更新
                    file_type=ext,
                    file_size=len(content),
                )

                # 写文件到磁盘
                file_path = await save_upload_file(file, content)

                # 更新文件路径
                resume.file_path = file_path
                await db.flush()

            # savepoint 提交成功后才触发 Celery
            parse_resume.delay(str(resume.id), file_path)

            results.append(BatchUploadFileResult(
                file_name=file_name,
                success=True,
                resume_id=resume.id,
            ))
            success_count += 1

        except Exception as e:
            # savepoint 回滚：仅该文件的DB记录被撤销
            # 如果文件已写入磁盘，需要清理
            if file_path:
                await delete_file(file_path)

            results.append(BatchUploadFileResult(
                file_name=file_name,
                success=False,
                error=f"处理失败: {str(e)}",
            ))
            failed_count += 1

    batch_response = BatchUploadResponse(
        total=len(files),
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )
    return APIResponse.success(
        data=batch_response.model_dump(mode="json"),
        message=f"批量上传完成：成功 {success_count} 份，失败 {failed_count} 份",
    )


@router.get("/", response_model=APIResponse)
async def list_resumes_endpoint(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    parse_status: str | None = Query(
        default=None,
        description="解析状态筛选",
        pattern="^(pending|parsing|completed|failed)$",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取简历列表（分页）。

    - 支持按状态筛选：pending/parsing/completed/failed
    - 按上传时间倒序排列
    - 返回解析进度
    """
    offset = (page - 1) * page_size

    resumes, total = await get_resumes(
        db,
        user_id=current_user.id,
        skip=offset,
        limit=page_size,
        status=parse_status,
    )

    items = [ResumeResponse.model_validate(r) for r in resumes]
    page_data = PageResponse.create(items=items, total=total, page=page, page_size=page_size)

    return APIResponse.success(data=page_data.model_dump(mode="json"))


@router.get("/{resume_id}", response_model=APIResponse)
async def get_resume_detail(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取简历详情（元数据 + 解析结果）"""
    resume = await get_resume(db, resume_id, user_id=current_user.id)

    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="简历不存在或无访问权限",
        )

    return APIResponse.success(
        data=ResumeResponse.model_validate(resume).model_dump(mode="json")
    )


@router.delete("/{resume_id}", response_model=APIResponse)
async def delete_resume_endpoint(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    删除简历（软删除）。

    - 标记 is_deleted=True
    - 不物理删除文件
    """
    deleted = await soft_delete_resume(db, resume_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="简历不存在或无访问权限",
        )

    return APIResponse.success(message="简历已删除")


@router.post("/{resume_id}/parse", response_model=APIResponse)
async def trigger_parse(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    手动触发简历解析。

    将简历状态重置为parsing，重新触发Celery解析任务。
    适用于解析失败后重试。
    """
    resume = await get_resume(db, resume_id, user_id=current_user.id)

    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="简历不存在或无访问权限",
        )

    if resume.parse_status == "parsing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="简历正在解析中，请稍后",
        )

    # 更新状态为解析中
    await update_resume_status(db, resume_id, "parsing")

    # 触发Celery解析任务
    parse_resume.delay(str(resume_id), resume.file_path)

    return APIResponse.success(message="解析任务已提交")


@router.put("/{resume_id}/parsed", response_model=APIResponse)
async def update_parsed_data(
    resume_id: uuid.UUID,
    parsed_data: ParsedResumeData,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新简历解析结果（手动修正或回调更新）。

    允许用户修正AI解析结果中的错误。
    """
    resume = await get_resume(db, resume_id, user_id=current_user.id)

    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="简历不存在或无访问权限",
        )

    updated = await update_resume_status(
        db,
        resume_id,
        "completed",
        parsed_data=parsed_data.model_dump(),
    )

    return APIResponse.success(
        data=ResumeResponse.model_validate(updated).model_dump(mode="json"),
        message="解析结果已更新",
    )
