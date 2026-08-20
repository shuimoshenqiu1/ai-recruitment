"""简历管理路由"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.common import APIResponse, PageResponse
from app.schemas.resume import ParsedResumeData, ResumeResponse

router = APIRouter()


@router.get("/", response_model=APIResponse)
async def list_resumes(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    parse_status: str | None = Query(default=None, description="解析状态筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取简历列表（分页）"""
    # 构建查询
    query = select(Resume).where(Resume.uploaded_by == current_user.id)
    count_query = select(func.count()).select_from(Resume).where(
        Resume.uploaded_by == current_user.id
    )

    if parse_status:
        query = query.where(Resume.parse_status == parse_status)
        count_query = count_query.where(Resume.parse_status == parse_status)

    # 查询总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    query = query.order_by(Resume.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    resumes = result.scalars().all()

    items = [ResumeResponse.model_validate(r) for r in resumes]
    page_data = PageResponse.create(items=items, total=total, page=page, page_size=page_size)

    return APIResponse.success(data=page_data.model_dump())


@router.post("/upload", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(..., description="简历文件(pdf/docx/doc/txt)"),
    candidate_name: str | None = Form(default=None, description="候选人姓名"),
    candidate_email: str | None = Form(default=None, description="候选人邮箱"),
    candidate_phone: str | None = Form(default=None, description="候选人电话"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    上传简历文件。
    
    - 支持格式：pdf, docx, doc, txt
    - 最大20MB
    - 上传后状态为pending，需调用 /parse 触发解析
    """
    # 验证文件类型
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {ext}，允许: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    # 验证文件大小
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超限，最大: {settings.MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # 保存文件
    file_id = uuid.uuid4()
    upload_dir = Path(settings.UPLOAD_DIR) / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{file_id}.{ext}"

    with open(file_path, "wb") as f:
        f.write(content)

    # 创建数据库记录
    resume = Resume(
        id=file_id,
        uploaded_by=current_user.id,
        file_name=file.filename,
        file_path=str(file_path),
        file_type=ext,
        file_size=len(content),
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone,
        parse_status="pending",
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)

    return APIResponse.success(
        data=ResumeResponse.model_validate(resume).model_dump(),
        message="上传成功",
    )


@router.get("/{resume_id}", response_model=APIResponse)
async def get_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取简历详情"""
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.uploaded_by == current_user.id)
    )
    resume = result.scalar_one_or_none()

    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="简历不存在")

    return APIResponse.success(data=ResumeResponse.model_validate(resume).model_dump())


@router.post("/{resume_id}/parse", response_model=APIResponse)
async def trigger_parse(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    触发简历AI解析。
    
    将简历状态置为parsing，实际解析由后台任务完成。
    （此处模拟触发，生产中应发送Celery任务）
    """
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.uploaded_by == current_user.id)
    )
    resume = result.scalar_one_or_none()

    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="简历不存在")

    if resume.parse_status == "parsing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="简历正在解析中")

    # 更新状态为解析中
    resume.parse_status = "parsing"
    await db.flush()

    # TODO: 生产环境应发送Celery异步任务
    # celery_app.send_task("tasks.parse_resume", args=[str(resume_id)])

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
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.uploaded_by == current_user.id)
    )
    resume = result.scalar_one_or_none()

    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="简历不存在")

    # 更新解析数据
    resume.parsed_data = parsed_data.model_dump()
    resume.parse_status = "completed"

    # 同步更新候选人基本信息
    if parsed_data.name:
        resume.candidate_name = parsed_data.name
    if parsed_data.email:
        resume.candidate_email = parsed_data.email
    if parsed_data.phone:
        resume.candidate_phone = parsed_data.phone

    await db.flush()
    await db.refresh(resume)

    return APIResponse.success(
        data=ResumeResponse.model_validate(resume).model_dump(),
        message="解析结果已更新",
    )
