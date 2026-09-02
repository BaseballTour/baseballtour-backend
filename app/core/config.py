from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KBO Travel API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000"
    )

    tour_api_key: str = ""
    tour_api_connect_timeout_seconds: float = 5.0
    tour_api_read_timeout_seconds: float = 10.0
    tour_api_write_timeout_seconds: float = 5.0
    tour_api_pool_timeout_seconds: float = 5.0
    tour_api_max_attempts: int = 2
    tour_api_retry_backoff_seconds: float = 0.25
    kakao_rest_api_key: str = ""
    firebase_credentials_path: str = (
        "secrets/firebase-service-account.json"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
