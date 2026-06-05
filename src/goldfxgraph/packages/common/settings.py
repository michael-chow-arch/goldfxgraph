import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import AliasChoices, Field, SecretStr, field_validator
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
    agent_api_base_url: str | None = None
    agent_api_key: SecretStr | None = None
    eod_backfill_timezone: str = "America/New_York"
    eod_backfill_cutoff_hour: int = 17
    eod_backfill_cutoff_minute: int = 0
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GOLDFXGRAPH_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    openai_model: str | None = Field(default=None, validation_alias="GOLDFXGRAPH_OPENAI_MODEL")
    openai_base_url: str | None = Field(default=None, validation_alias="GOLDFXGRAPH_OPENAI_BASE_URL")

    model_config = SettingsConfigDict(env_prefix="GOLDFXGRAPH_", extra="ignore", populate_by_name=True)

    @field_validator("agent_api_key", "openai_api_key", mode="before")
    @classmethod
    def _normalize_placeholder_secret(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, SecretStr):
            raw_value = value.get_secret_value().strip()
        else:
            raw_value = str(value).strip()

        if not raw_value:
            return None

        if raw_value.lower() in {
            "change_me",
            "changeme",
            "replace_me",
            "replace-me",
            "todo",
            "todo-change-me",
            "your_secret_here",
            "your-secret-here",
            "secret",
        }:
            return None

        return value


def _env_file_field_keys() -> dict[str, tuple[str, ...]]:
    values: dict[str, tuple[str, ...]] = {}
    env_prefix = GoldFXGraphSettings.model_config.get("env_prefix", "")

    for field_name, field_info in GoldFXGraphSettings.model_fields.items():
        validation_alias = field_info.validation_alias
        if isinstance(validation_alias, AliasChoices):
            values[field_name] = tuple(str(choice) for choice in validation_alias.choices)
            continue
        if isinstance(validation_alias, str):
            values[field_name] = (validation_alias,)
            continue

        values[field_name] = (f"{env_prefix}{field_name.upper()}",)

    return values


def _settings_values_from_env_file(env_file: Path) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if not env_file.exists():
        return values

    env_file_values = dotenv_values(env_file)
    for field_name, keys in _env_file_field_keys().items():
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
