from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )
    database_url: SecretStr
    jwt_secret: SecretStr
    node_env: str = "development"
    app_origin: str = "http://localhost:5173"
    quality_threshold: int = Field(default=50, ge=0)
    state_delay_hours: int = Field(default=48, gt=0)

    student_activation_days: int = Field(default=30, ge=1, le=365)
    certificate_storage: Path = (
        Path(__file__).resolve().parents[2] / ".certiflow-local" / "certificates"
    )

    @property
    def allowed_origins(self) -> set[str]:
        if self.node_env == "production":
            return {self.app_origin}
        return {self.app_origin, "http://localhost:5173", "http://127.0.0.1:5173"}


@lru_cache
def settings() -> Settings:
    config = Settings()
    if len(config.jwt_secret.get_secret_value().encode()) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 bytes.")
    return config
