from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgrespassword"
    POSTGRES_DB: str = "tg_gateway"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@db:5432/tg_gateway"

    BOT_TOKEN: str = ""
    TG_API_ID: int = 0
    TG_API_HASH: str = ""
    TG_SESSION_STRING: str = ""

    # Адрес для формирования кнопок оплаты (127.0.0.1 вместо localhost)
    BASE_URL: str = "http://127.0.0.1:8080"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()