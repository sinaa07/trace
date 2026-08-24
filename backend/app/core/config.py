from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://trace:trace_dev_password@localhost:5432/trace"
    )
    evidence_storage_path: Path = Path("../data/raw")
    processed_storage_path: Path = Path("../data/processed")
    app_env: str = "development"
    max_upload_size_mb: int = 50
    parser_version: str = "1.0.0"
    reject_duplicate_hash: bool = True


settings = Settings()
