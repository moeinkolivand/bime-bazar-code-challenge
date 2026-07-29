from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str | None = None

    JWT_SECRET_KEY: str = "123456"
    JWT_ACCESS_TOKEN_TIME: int = 30

    DB_ECHO: bool = False

    PROJECT_NAME: str
    VERSION: str

    POSTGRES_USER: str = "fastapi_user"
    POSTGRES_PASSWORD: str = "secret_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "fastapi_db"

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


settings = Settings()