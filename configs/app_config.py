from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class AppConfig(BaseSettings):
    """
    Application configuration class, loads from .env or environment variables.
    """
    APP_HOST: str = Field(default="0.0.0.0", description="Host for FastAPI server")
    APP_PORT: int = Field(default=5000, description="Port for FastAPI server")
    APP_DEBUG: bool = Field(default=False, description="Enable debug mode for FastAPI server")
    VLLM_BASE_PORT: int = Field(default=9000, description="Base port for vllm instances")
    VLLM_MAX_INSTANCES: int = Field(default=20, description="Max number of vllm instances")
    VLLM_DEFAULT_DTYPE: str = Field(default="auto", description="Default dtype for vllm")
    VLLM_DEFAULT_KV_CACHE_DTYPE: str = Field(default="auto", description="Default kv-cache-dtype for vllm")
    VLLM_DEFAULT_TRUST_REMOTE_CODE: bool = Field(default=True, description="Trust remote code for vllm")
    VLLM_DEFAULT_TIMEOUT: int = Field(default=600, description="Default timeout for vllm instance (seconds)")
    VLLM_CONFIG: str | None = Field(default="configs/vllm_config.json", description="Optional vllm config file path")
    HF_ENDPOINT: str | None = Field(default=None, description="HuggingFace endpoint (mirror or proxy)")
    HTTP_PROXY: str | None = Field(default=None, description="HTTP/HTTPS proxy for downloading models")
    HF_HOME: str | None = Field(default=None, description="HuggingFace cache directory, defaults to ~/.cache/huggingface")

    # Redis configuration
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_DB: int = Field(default=0, description="Redis database")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
