import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GoldFXGraphSettings(BaseSettings):
    env: str = "local"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+asyncpg://goldfxgraph:change_me@localhost:5432/goldfxgraph",
        validation_alias=AliasChoices("GOLDFXGRAPH_DATABASE_URL", "DATABASE_URL"),
    )
    xauusd_csv_path: Path = Path("data/raw/xauusd_daily.csv")
    current_quote_url: str | None = None
    current_quote_api_key: SecretStr | None = None
    agent_api_base_url: str | None = None
    agent_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GOLDFXGRAPH_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    openai_model: str | None = Field(default=None, validation_alias="GOLDFXGRAPH_OPENAI_MODEL")
    openai_base_url: str | None = Field(default=None, validation_alias="GOLDFXGRAPH_OPENAI_BASE_URL")

    model_config = SettingsConfigDict(env_prefix="GOLDFXGRAPH_", extra="ignore", populate_by_name=True)


_ENV_FILE_FIELD_KEYS: dict[str, tuple[str, ...]] = {
    "env": ("GOLDFXGRAPH_ENV",),
    "log_level": ("GOLDFXGRAPH_LOG_LEVEL",),
    "database_url": ("GOLDFXGRAPH_DATABASE_URL", "DATABASE_URL"),
    "xauusd_csv_path": ("GOLDFXGRAPH_XAUUSD_CSV_PATH",),
    "current_quote_url": ("GOLDFXGRAPH_CURRENT_QUOTE_URL",),
    "current_quote_api_key": ("GOLDFXGRAPH_CURRENT_QUOTE_API_KEY",),
    "agent_api_base_url": ("GOLDFXGRAPH_AGENT_API_BASE_URL",),
    "agent_api_key": ("GOLDFXGRAPH_AGENT_API_KEY",),
    "openai_api_key": ("GOLDFXGRAPH_OPENAI_API_KEY", "OPENAI_API_KEY"),
    "openai_model": ("GOLDFXGRAPH_OPENAI_MODEL",),
    "openai_base_url": ("GOLDFXGRAPH_OPENAI_BASE_URL",),
}


def _settings_values_from_env_file(env_file: Path) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if not env_file.exists():
        return values

    env_file_values = dotenv_values(env_file)
    for field_name, keys in _ENV_FILE_FIELD_KEYS.items():
        if any(key in os.environ for key in keys):
            continue

        for key in keys:
            value = env_file_values.get(key)
            if value is None:
                continue

            values[field_name] = value if value != "" else None
            break

    return values


def load_settings(env_file: Path = Path("dev.env")) -> GoldFXGraphSettings:
    return GoldFXGraphSettings(**_settings_values_from_env_file(env_file))


@lru_cache
def get_settings() -> GoldFXGraphSettings:
    return load_settings()
