"""应用配置"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置项 - 从环境变量读取"""

    # 应用
    APP_NAME: str = "AI招聘匹配系统"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # 安全
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    ALGORITHM: str = "HS256"

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://recruitment:recruitment_dev_2024@localhost:5432/recruitment"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 20 * 1024 * 1024  # 20MB
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "docx", "doc", "txt"]

    # LLM默认配置
    DEFAULT_LLM_PROVIDER: str = "openai"
    LLM_REQUEST_TIMEOUT: int = 30  # 秒
    LLM_MAX_RETRIES: int = 3

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
