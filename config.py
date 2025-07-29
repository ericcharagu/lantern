#!/usr/bin/env python3

from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Lantern Foot Traffic Analytics API"
    LLM_MODEL_ID: str = "qwen3:0.6b"

    # Environment-specific file paths for secrets
    WHATSAPP_VERIFICATION_TOKEN_FILE: str = "/run/secrets/whatsapp_verification_token"

    # Service hosts
    OLLAMA_HOST: str = "http://ollama:11434"
    VALKEY_HOST: str = "valkey"
    VALKEY_PORT: int = 6379

    # Load from .env file
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    # Nightly report recipient number
    NIGHTLY_REPORT_RECIPIENT_NUMBER:str = os.getenv("254736391323", "")



# Create a single settings instance to be used across the application
settings = Settings()
