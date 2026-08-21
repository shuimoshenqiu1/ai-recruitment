"""API v1路由注册"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.resumes import router as resumes_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.matching import router as matching_router
from app.api.v1.llm_configs import router as llm_configs_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.reports import router as reports_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["认证"])
router.include_router(resumes_router, prefix="/resumes", tags=["简历管理"])
router.include_router(jobs_router, prefix="/jobs", tags=["岗位管理"])
router.include_router(matching_router, prefix="/matching", tags=["智能匹配"])
router.include_router(llm_configs_router, prefix="/llm-configs", tags=["LLM配置"])
router.include_router(dashboard_router, prefix="/dashboard", tags=["数据看板"])
router.include_router(reports_router, prefix="/reports", tags=["报告导出"])
