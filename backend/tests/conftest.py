"""集成测试配置 - fixtures 和测试数据库初始化"""

import os
import sys
from unittest.mock import MagicMock

# ============================================================
# Phase 1: Mock heavy dependencies BEFORE any app import
# ============================================================
for mod in (
    "fitz", "docx", "openai",
    "celery", "celery.app", "celery.app.task", "celery.result",
    "redis", "asyncpg", "pgvector",
    "slowapi", "slowapi.util", "slowapi.errors",
    "magic",
):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Make magic.from_buffer return PDF mime by default (tests override as needed)
sys.modules["magic"].from_buffer = lambda content, mime=False: "application/pdf"

# Mock slowapi so decorators and handlers resolve as no-ops
_mock_limiter = MagicMock()
_mock_limiter.limit = lambda *a, **kw: lambda fn: fn
_mock_limiter.shared_limit = lambda *a, **kw: lambda fn: fn
sys.modules["slowapi"].Limiter = MagicMock(return_value=_mock_limiter)
sys.modules["slowapi"].errors = MagicMock()
sys.modules["slowapi"].errors.RateLimitExceeded = type("RateLimitExceeded", (Exception,), {})
sys.modules["slowapi"]._rate_limit_exceeded_handler = lambda req, exc: None
sys.modules["slowapi.errors"].RateLimitExceeded = sys.modules["slowapi"].errors.RateLimitExceeded
sys.modules["slowapi.util"].get_remote_address = lambda request: "127.0.0.1"

# ============================================================
# Phase 2: Set env vars & create test engines BEFORE app import
# ============================================================
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ENVIRONMENT"] = "development"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine as _real_create_engine
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _real_create_async_engine,
)
from sqlalchemy.pool import StaticPool

# Test async engine (SQLite in-memory, StaticPool = shared single connection)
test_engine = _real_create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Test sync engine for modules like resume_tasks.py that create sync engines
_sync_test_engine = _real_create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """启用SQLite外键约束"""
    import sqlite3
    import uuid

    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

    # 注册UUID类型适配器，让SQLite能处理Python UUID对象
    sqlite3.register_adapter(uuid.UUID, lambda u: str(u))
    sqlite3.register_converter("UUID", lambda b: uuid.UUID(b.decode()))


# ============================================================
# Phase 3: Monkey-patch engine creation functions
# ============================================================
import sqlalchemy as _sa
import sqlalchemy.ext.asyncio as _sa_async

_original_cae = _sa_async.create_async_engine
_original_ce = _sa.create_engine


def _fake_create_async_engine(*args, **kwargs):
    return test_engine


def _fake_create_engine(*args, **kwargs):
    return _sync_test_engine


_sa_async.create_async_engine = _fake_create_async_engine
_sa.create_engine = _fake_create_engine

# ============================================================
# Phase 4: NOW import app (all engine creations intercepted)
# ============================================================
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# Restore originals
_sa_async.create_async_engine = _original_cae
_sa.create_engine = _original_ce

# Ensure database module references our test engine
import app.core.database as _db_mod  # noqa: E402

_db_mod.engine = test_engine
_db_mod.AsyncSessionLocal = TestSessionLocal


# ============================================================
# Phase 5: SQLite compatibility patch for PG-specific types
# ============================================================
import uuid as _uuid_mod

from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID


class SQLiteUUID(TypeDecorator):
    """将UUID对象与SQLite的TEXT列透明互转"""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value) if isinstance(value, _uuid_mod.UUID) else value
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return _uuid_mod.UUID(value) if not isinstance(value, _uuid_mod.UUID) else value
        return value


def _patch_models_for_sqlite():
    """将PostgreSQL专用类型(UUID, JSONB)替换为SQLite兼容类型"""
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = SQLiteUUID()
            elif isinstance(column.type, JSONB):
                column.type = JSON()


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture(autouse=True)
async def db_session():
    """每个测试独立的数据库schema（create/drop tables per test）"""
    _patch_models_for_sqlite()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """异步HTTP测试客户端，覆盖get_db依赖使用测试数据库"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """注册+登录获取认证headers"""
    user_data = {
        "email": "test@example.com",
        "password": "Test123!@#",
        "name": "测试用户",
    }

    await client.post("/api/v1/auth/register", json=user_data)
    resp = await client.post("/api/v1/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"],
    })
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_user_headers(client: AsyncClient) -> dict[str, str]:
    """第二个用户的认证headers，用于权限隔离测试"""
    user_data = {
        "email": "second@example.com",
        "password": "Second123!@#",
        "name": "第二用户",
    }

    await client.post("/api/v1/auth/register", json=user_data)
    resp = await client.post("/api/v1/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"],
    })
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def sample_job_data() -> dict:
    """标准岗位创建数据"""
    return {
        "title": "高级Python开发工程师",
        "department": "技术部",
        "level": "P7",
        "headcount": 2,
        "description": "负责后端服务开发与架构设计",
        "requirements": {
            "hard": ["Python 5年+", "FastAPI/Django", "PostgreSQL"],
            "soft": ["团队协作", "沟通能力"],
            "preferred": ["分布式系统经验", "大数据经验"],
        },
    }
