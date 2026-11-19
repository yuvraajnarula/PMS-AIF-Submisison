from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./mf.db"
    default_rf: float = 0.055
    methodology_version: str = "2026.1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
