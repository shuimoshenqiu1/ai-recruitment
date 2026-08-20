"""应用配置"""

from pydantic import model_validator
from pydantic_settings import BaseSettings


_DEFAULT_SECRET_KEY = "dev-secret-key-change-in-production"
_DEFAULT_DATABASE_PASSWORD = "recruitment_dev_2024"


class Settings(BaseSettings):
    """应用配置项 - 从环境变量读取"""

    # 应用
    APP_NAME: str = "AI招聘匹配系统"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # 安全
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 默认30分钟
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
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "docx", "doc", "txt", "jpg", "png"]

    # LLM默认配置
    DEFAULT_LLM_PROVIDER: str = "openai"
    LLM_REQUEST_TIMEOUT: int = 30  # 秒
    LLM_MAX_RETRIES: int = 3

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """非 development 环境下校验敏感配置"""
        if self.ENVIRONMENT == "development":
            return self

        # C-1: SECRET_KEY 不能是默认值且长度 >= 32
        if self.SECRET_KEY == _DEFAULT_SECRET_KEY:
            raise ValueError(
                f"[{self.ENVIRONMENT}] SECRET_KEY 不能使用默认值，"
                "请通过环境变量设置安全的密钥"
            )
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                f"[{self.ENVIRONMENT}] SECRET_KEY 长度必须 >= 32 字符，"
                f"当前长度: {len(self.SECRET_KEY)}"
            )

        # H-4: DATABASE_URL 不能包含默认密码
        if _DEFAULT_DATABASE_PASSWORD in self.DATABASE_URL:
            raise ValueError(
                f"[{self.ENVIRONMENT}] DATABASE_URL 包含默认密码 "
                f"'{_DEFAULT_DATABASE_PASSWORD}'，请通过环境变量设置安全的数据库连接"
            )

        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
