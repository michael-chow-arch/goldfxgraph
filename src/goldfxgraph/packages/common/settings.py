import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GoldFXGraphSettings(BaseSettings):
    env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://goldfxgraph:change_me@localhost:5432/goldfxgraph"
    xauusd_csv_path: Path = Path("data/raw/xauusd_daily.csv")
    current_quote_url: str | None = None
    current_quote_api_key: SecretStr | None = None
    agent_api_base_url: str | None = None
    agent_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(env_prefix="GOLDFXGRAPH_", extra="ignore")


def _settings_values_from_env_file(env_file: Path) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if not env_file.exists():
        return values

    for key, value in dotenv_values(env_file).items():
        if value is None or not key.startswith("GOLDFXGRAPH_"):
            continue
        if key in os.environ:
            continue

        field_name = key.removeprefix("GOLDFXGRAPH_").lower()
        values[field_name] = value if value != "" else None

    return values


def load_settings(env_file: Path = Path("dev.env")) -> GoldFXGraphSettings:
    return GoldFXGraphSettings(**_settings_values_from_env_file(env_file))


@lru_cache
def get_settings() -> GoldFXGraphSettings:
    return load_settings()
