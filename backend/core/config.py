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
    cors_allow_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ALLOW_ORIGINS",
    )
    cors_allow_origin_regex: str = Field(
        default=r"https?://(localhost|127\.0\.0\.1):\d+",
        alias="CORS_ALLOW_ORIGIN_REGEX",
    )
    use_mock_llm: bool = Field(default=True, alias="USE_MOCK_LLM")
    enable_real_llm: bool = Field(default=False, alias="ENABLE_REAL_LLM")
    review_engine: str = Field(default="v3_multi_agent", alias="REVIEW_ENGINE")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    mimo_api_key: str | None = Field(default=None, alias="MIMO_API_KEY")
    mimo_base_url: str = Field(default="https://token-plan-cn.xiaomimimo.com/v1", alias="MIMO_BASE_URL")
    mimo_model_name: str = Field(default="mimo-v2.5-pro", alias="MIMO_MODEL_NAME")
    max_files: int = 300
    max_file_size_bytes: int = 200 * 1024
    large_repo_threshold: int = Field(default=300, alias="LARGE_REPO_THRESHOLD")
    final_prompt_token_budget: int = 8000
    llm_connect_timeout: float = Field(default=10.0, alias="LLM_CONNECT_TIMEOUT_SECONDS")
    llm_read_timeout: float = Field(default=180.0, alias="LLM_READ_TIMEOUT_SECONDS")
    llm_write_timeout: float = Field(default=30.0, alias="LLM_WRITE_TIMEOUT_SECONDS")
    llm_pool_timeout: float = Field(default=10.0, alias="LLM_POOL_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")

    # Localization / translation provider settings
    enable_llm_translation: bool = Field(default=False, alias="ENABLE_LLM_TRANSLATION")
    localization_provider: str = Field(default="auto", alias="LOCALIZATION_PROVIDER")
    localization_model: str | None = Field(default=None, alias="LOCALIZATION_MODEL")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    settings.reports_path.mkdir(parents=True, exist_ok=True)
    return settings
