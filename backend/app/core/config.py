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

    # Pluggable LLM: heuristic (default) | openai_compatible/ollama/vllm | anthropic
    llm_provider: str = "heuristic"
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_model: str = "llama3.2"
    llm_api_key: str = ""
    investigation_max_iterations: int = 5

    # External weather (Open-Meteo — free, no API key)
    weather_enabled: bool = True
    weather_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    weather_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout_seconds: float = 20.0


settings = Settings()
