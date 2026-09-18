import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "DocuMind AI"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "documind-super-secret-jwt-key-2026-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database Configuration
    DATABASE_URL: str = "postgresql://documind:documind_secret@localhost:5432/documind_db"
    USE_SQLITE_FALLBACK: bool = True

    # Google Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    CHAT_MODEL: str = "gemini-3.5-flash-lite"

    # RAG Ingestion & Search Settings
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    TOP_K_RETRIEVAL: int = 4
    SIMILARITY_THRESHOLD: float = 0.35

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
