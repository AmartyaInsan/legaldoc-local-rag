from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os

# Base directory of the backend folder
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    """
    App configuration loaded from .env file.
    Learning note: Using Pydantic BaseSettings makes it easy to read environment
    variables and provide default values for local development.
    """
    model_config = SettingsConfigDict(
        env_file=os.path.join(BACKEND_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "LegalDoc Local RAG"
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Local Database Settings (ChromaDB + SQLite for 100% offline/close-environment storage)
    LOCAL_DATA_DIR: str = os.path.join(BACKEND_DIR, "local_data")
    CHROMA_COLLECTION_NAME: str = "legal_documents_chunks"

    # Local LLM Settings (Ollama)
    # Using local models so sensitive legal documents never leave this computer
    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "qwen2.5:7b"
    SUBAGENT_MODEL: str = "qwen2.5:7b"
    LLM_CONTEXT_WINDOW: int = 8192

    # Local Embedding Model Settings (nomic-embed-text produces 768-dim vectors)
    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_BASE_URL: str = "http://localhost:11434/v1"
    EMBEDDING_API_KEY: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text:latest"
    EMBEDDING_DIMENSIONS: int = 768

    # Optional LangSmith Tracing (from the YouTube tutorial)
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "legal-rag-learning"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


settings = Settings()
