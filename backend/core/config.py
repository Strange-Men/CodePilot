from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    database_path: Path = Field(default=ROOT_DIR / "backend" / "data" / "codepilot.db")
    workspace_path: Path = Field(default=ROOT_DIR / "backend" / "workspace")
    reports_path: Path = Field(default=ROOT_DIR / "reports")
    use_mock_llm: bool = Field(default=True, alias="USE_MOCK_LLM")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    max_files: int = 300
    max_file_size_bytes: int = 200 * 1024
    final_prompt_token_budget: int = 5000


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    settings.reports_path.mkdir(parents=True, exist_ok=True)
    return settings

