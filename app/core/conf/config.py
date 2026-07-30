from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str | None = None
    REDIS_URL: str | None = None
    OTP_EXPIRE_SECONDS: int = 300

    JWT_SECRET_KEY: str = "123456"
    JWT_ACCESS_TOKEN_TIME: int = 30

    DB_ECHO: bool = False

    PROJECT_NAME: str = "inventory"
    VERSION: str = "1"

    POSTGRES_USER: str = "fastapi_user"
    POSTGRES_PASSWORD: str = "secret_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "fastapi_db"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @model_validator(mode="after")
    def build_database_url(self):
        if self.DATABASE_URL is None:
            self.DATABASE_URL = (
                f"postgresql+psycopg://"
                f"{self.POSTGRES_USER}:"
                f"{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_HOST}:"
                f"{self.POSTGRES_PORT}/"
                f"{self.POSTGRES_DB}"
            )

        return self

    @model_validator(mode="after")
    def build_redis_url(self):
        if self.REDIS_URL is None:
            self.REDIS_URL = (
                f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return self


settings = Settings()


def get_settings() -> BaseSettings:
    return settings
