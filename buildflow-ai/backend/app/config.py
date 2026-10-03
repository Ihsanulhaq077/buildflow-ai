from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-only-change-me"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    tz_offset_hours: float = 5.0     # business timezone (Pakistan = UTC+5, no DST)
    price_anomaly_pct: int = 10  # flag quotes this % above the last purchase rate


settings = Settings()
