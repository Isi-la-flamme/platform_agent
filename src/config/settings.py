from functools import lru_cache

from pydantic import Field
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from src.config.environments import Environment


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "agent-platform"

    APP_ENV: Environment = Environment.DEVELOPMENT

    DEBUG: bool = True

    LOG_LEVEL: str = "INFO"

    OPENAI_API_KEY: SecretStr = Field(
        default=SecretStr(""),
    )

    OPENAI_MODEL: str = "gpt-4.1-mini"

    REQUEST_TIMEOUT: int = 60

    MAX_RETRIES: int = 3

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == Environment.DEVELOPMENT

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        return self.APP_ENV == Environment.TESTING


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()