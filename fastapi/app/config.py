from pydantic_settings import BaseSettings
from functools import lru_cache
from supabase import create_client, Client as SupabaseClient
from langfuse import Langfuse
from langchain_anthropic import ChatAnthropic


class Settings(BaseSettings):
    # API
    app_name: str = "Affiliate Sales AI Agent"
    app_version: str = "0.2.0"
    debug: bool = False

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    anthropic_max_tokens: int = 1024
    anthropic_temperature: float = 0.3

    # Langfuse
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str = "https://cloud.langfuse.com"

    # WhatsApp (used in TASK-015)
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""

    # Telegram (operator notifications)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_supabase_client() -> SupabaseClient:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def get_langfuse_client() -> Langfuse:
    settings = get_settings()
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def get_llm() -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        temperature=settings.anthropic_temperature,
        anthropic_api_key=settings.anthropic_api_key,
    )
