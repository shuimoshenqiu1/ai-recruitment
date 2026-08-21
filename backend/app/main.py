"""AI招聘匹配系统 - FastAPI主入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    await init_db()
    yield


app = FastAPI(
    title="AI招聘匹配系统",
    description="AI驱动的简历解析与智能招聘匹配系统 API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# H-3: SlowAPI 限频异常处理
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """存活检查 - 仅确认服务进程在运行"""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/health/ready")
async def readiness_check():
    """就绪检查 - 确认所有依赖（DB/Redis）可达"""
    import redis.asyncio as aioredis
    from sqlalchemy import text

    from app.core.database import async_session_factory

    checks = {}

    # 检查 PostgreSQL
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # 检查 Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "degraded",
            "version": "1.0.0",
            "checks": checks,
        },
    )
