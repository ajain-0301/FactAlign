"""Environment-based configuration (see backend/.env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    nli_model: str = "joeddav/xlm-roberta-large-xnli"
    verification_local_only: bool = True
    nli_decision_threshold: float = Field(default=0.75, gt=0.5, le=1)
    nli_decision_margin: float = Field(default=0.15, ge=0, le=1)
    provider_mode: str = "auto"  # auto | demo | real
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'FactAlign.db').as_posix()}"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    llm_timeout_seconds: float = 90.0
    max_input_chars: int = 60000
    max_upload_mb: int = 5
    chunk_chars: int = 6000
    sample_data_dir: str = str(ROOT_DIR / "sample_data")

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_api_key(self) -> bool:
        return bool(self.groq_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
