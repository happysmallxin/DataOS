"""DataOS 平台配置 — 对标 DataWorks 多环境配置模式."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """全局配置，从环境变量读取."""

    # 应用
    APP_NAME: str = "DataOS"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "mysql+aiomysql://dataos:dataos_2025@localhost:3306/dataos_platform"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "dataos-jwt-secret-dev-only-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 小时

    # 下游服务地址
    DOLPHINSCHEDULER_URL: str = "http://localhost:12345"
    OPENMETADATA_URL: str = "http://localhost:8585"
    SEATUNNEL_URL: str = "http://localhost:8080"
    CRAWLAB_URL: str = "http://localhost:8088"
    DATAVINES_URL: str = "http://localhost:5600"
    DIRECTUS_URL: str = "http://localhost:8055"
    MEILI_URL: str = "http://localhost:7700"
    MEILI_MASTER_KEY: str = "dataos-meili-dev-key-change-in-prod"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5000", "http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": "../../.env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
