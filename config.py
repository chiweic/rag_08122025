from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ValidationInfo
from typing import Optional, Literal, Union
import os
import json
from dotenv import load_dotenv

# Force reload .env with override=True to ensure latest values are used
load_dotenv(override=True)


class Settings(BaseSettings):
    # API Keys
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, env="DEEPSEEK_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    dashscope_api_key: Optional[str] = Field(default=None, env="DASHSCOPE_API_KEY")
    
    # Custom LLM Configuration
    custom_llm_base_url: Optional[str] = Field(default=None, env="CUSTOM_LLM_BASE_URL")
    custom_llm_api_key: Optional[str] = Field(default="empty", env="CUSTOM_LLM_API_KEY")

    # Ollama Configuration
    ollama_base_url: Optional[str] = Field(default=None, env="OLLAMA_BASE_URL")
    ollama_api_key: Optional[str] = Field(default=None, env="OLLAMA_API_KEY")
    ollama_max_workers: int = Field(default=10, env="OLLAMA_MAX_WORKERS")
    
    # LLM Configuration
    llm_provider: Literal["openai", "deepseek", "google", "dashscope", "custom"] = Field(
        default="openai", env="LLM_PROVIDER"
    )
    llm_model: str = Field(default="gpt-5-mini", env="LLM_MODEL")
    llm_temperature: float = Field(default=0.0, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2000, env="LLM_MAX_TOKENS")
    
    # Embedding Configuration
    embedding_provider: Literal["openai", "google", "huggingface", "local", "ollama", "dashscope"] = Field(
        default="local", env="EMBEDDING_PROVIDER"
    )
    embedding_model: str = Field(
        default="/home/chiweic/repo/synthetic_dataset/emb_finetune_small_32/final", env="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=512, env="EMBEDDING_DIMENSION")
    
    # Qdrant Configuration
    qdrant_url: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    qdrant_api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="ddm_rag", env="QDRANT_COLLECTION")
    
    # RAG Configuration
    retrieval_top_k: int = Field(default=5, env="RETRIEVAL_TOP_K")
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    cors_origins: Union[str, list[str]] = Field(
        default=["*"], env="CORS_ORIGINS"
    )

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or JSON array."""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        if isinstance(v, list):
            return v
        return ["*"]  # Fallback to allow all

    # Processing
    max_workers: int = Field(default=4, env="MAX_WORKERS")
    batch_size: int = Field(default=100, env="BATCH_SIZE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file


settings = Settings()