from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://copilot:copilot@localhost:5432/copilot"
    session_secret: str = "development-only-change-this-secret-32"
    environment: Literal["development", "production", "test"] = "development"
    ai_mode: Literal["mock", "live"] = "mock"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout: float = 30
    embedding_enabled: bool = False
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dim: int = 1536
    embedding_timeout: float = 20
    news_mode: Literal["replay", "live"] = "replay"
    send_mode: Literal["manual"] = "manual"
    app_port: int = 8000
    demo_password: str = "Demo-Only-2026!"
    cookie_secure: bool = False

    @model_validator(mode="after")
    def validate_modes(self):
        if self.environment == "production":
            if len(self.session_secret) < 32 or self.session_secret.startswith(("development", "replace")):
                raise ValueError("生产环境必须配置随机 SESSION_SECRET")
            if self.demo_password == "Demo-Only-2026!" or not self.cookie_secure:
                raise ValueError("生产环境禁止默认凭据且必须启用 COOKIE_SECURE")
        if self.ai_mode == "live" and not all([self.llm_base_url, self.llm_api_key, self.llm_model]):
            raise ValueError("live 模式必须配置 LLM_BASE_URL/API_KEY/MODEL")
        if self.embedding_enabled and not all([
            self.embedding_base_url, self.embedding_api_key, self.embedding_model, self.embedding_dim > 0
        ]):
            raise ValueError("启用 embedding 必须单独配置地址、密钥、模型和维度")
        return self

    @property
    def embedding_space(self):
        return f"{self.embedding_base_url}|{self.embedding_model}|{self.embedding_dim}"


@lru_cache
def settings():
    return Settings()
