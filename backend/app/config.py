from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    upload_dir: Path = Path("./data/uploads")

    litellm_base_url: str = "http://litellm:4000/v1"
    litellm_api_key: str = "sk-litellm-change-me"
    extraction_model: str = "extraction-model"
    analysis_model: str = "analysis-model"
    extraction_prompt_version: str = "extraction_v1"
    analysis_prompt_version: str = "analysis_v1"


settings = Settings()
