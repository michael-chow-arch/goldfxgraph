from pathlib import Path

from pydantic import SecretStr
from pytest import MonkeyPatch

from goldfxgraph.packages.common.settings import GoldFXGraphSettings, load_settings


def _clear_openai_and_database_overrides(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOLDFXGRAPH_DATABASE_URL", raising=False)
    monkeypatch.delenv("GOLDFXGRAPH_OPENAI_API_KEY", raising=False)


def test_settings_loads_from_explicit_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "GOLDFXGRAPH_ENV=local",
                "GOLDFXGRAPH_LOG_LEVEL=DEBUG",
                "GOLDFXGRAPH_DATABASE_URL=postgresql+asyncpg://u:p@localhost:5432/db",
                "GOLDFXGRAPH_XAUUSD_CSV_PATH=data/raw/xauusd_daily.csv",
                "GOLDFXGRAPH_CURRENT_QUOTE_URL=https://example.test/quote",
                "GOLDFXGRAPH_AGENT_API_BASE_URL=https://example.test/v1",
                "GOLDFXGRAPH_AGENT_API_KEY=agent-key",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.env == "local"
    assert settings.log_level == "DEBUG"
    assert str(settings.xauusd_csv_path) == "data/raw/xauusd_daily.csv"
    assert settings.agent_api_base_url == "https://example.test/v1"
    assert settings.agent_api_key is not None
    assert settings.agent_api_key.get_secret_value() == "agent-key"


def test_settings_default_eod_backfill_schedule_targets_new_york_close() -> None:
    settings = GoldFXGraphSettings()

    assert settings.eod_backfill_timezone == "America/New_York"
    assert settings.eod_backfill_cutoff_hour == 17
    assert settings.eod_backfill_cutoff_minute == 0


def test_settings_treats_placeholder_secrets_as_unset(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "GOLDFXGRAPH_AGENT_API_KEY=change_me",
                "OPENAI_API_KEY=change_me",
                "GOLDFXGRAPH_OPENAI_MODEL=gpt-5.1",
                "GOLDFXGRAPH_OPENAI_BASE_URL=https://example.test/v1",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.agent_api_key is None
    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-5.1"
    assert settings.openai_base_url == "https://example.test/v1"


def test_settings_repr_does_not_expose_agent_key() -> None:
    settings = GoldFXGraphSettings(
        agent_api_key=SecretStr("super-secret"),
    )

    rendered = repr(settings)

    assert "super-secret" not in rendered


def test_environment_variables_override_env_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "GOLDFXGRAPH_LOG_LEVEL=INFO",
                "GOLDFXGRAPH_XAUUSD_CSV_PATH=data/raw/xauusd_daily.csv",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOLDFXGRAPH_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("GOLDFXGRAPH_XAUUSD_CSV_PATH", "env/path.csv")

    settings = load_settings(env_file=env_file)

    assert settings.log_level == "ERROR"
    assert str(settings.xauusd_csv_path) == "env/path.csv"


def test_settings_support_legacy_env_aliases(monkeypatch: MonkeyPatch) -> None:
    _clear_openai_and_database_overrides(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://legacy:pw@localhost:5432/legacy_db")
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-openai-key")
    monkeypatch.setenv("GOLDFXGRAPH_OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("GOLDFXGRAPH_OPENAI_BASE_URL", "https://example.test/v1")

    settings = GoldFXGraphSettings()

    assert settings.database_url == "postgresql+asyncpg://legacy:pw@localhost:5432/legacy_db"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "legacy-openai-key"
    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.openai_base_url == "https://example.test/v1"


def test_settings_prefers_goldfxgraph_database_url_over_legacy_alias(monkeypatch: MonkeyPatch) -> None:
    _clear_openai_and_database_overrides(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://legacy:pw@localhost:5432/legacy_db")
    monkeypatch.setenv(
        "GOLDFXGRAPH_DATABASE_URL",
        "postgresql+asyncpg://preferred:pw@localhost:5432/preferred_db",
    )

    settings = GoldFXGraphSettings()

    assert settings.database_url == "postgresql+asyncpg://preferred:pw@localhost:5432/preferred_db"


def test_load_settings_supports_legacy_aliases_from_env_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    _clear_openai_and_database_overrides(monkeypatch)
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+asyncpg://legacy:pw@localhost:5432/legacy_db",
                "OPENAI_API_KEY=legacy-openai-key",
                "GOLDFXGRAPH_OPENAI_MODEL=gpt-5.1",
                "GOLDFXGRAPH_OPENAI_BASE_URL=https://example.test/v1",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.database_url == "postgresql+asyncpg://legacy:pw@localhost:5432/legacy_db"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "legacy-openai-key"
    assert settings.openai_model == "gpt-5.1"
    assert settings.openai_base_url == "https://example.test/v1"


def test_load_settings_prefers_goldfxgraph_keys_over_legacy_aliases_in_env_file(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    _clear_openai_and_database_overrides(monkeypatch)
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+asyncpg://legacy:pw@localhost:5432/legacy_db",
                "GOLDFXGRAPH_DATABASE_URL=postgresql+asyncpg://preferred:pw@localhost:5432/preferred_db",
                "OPENAI_API_KEY=legacy-openai-key",
                "GOLDFXGRAPH_OPENAI_API_KEY=preferred-openai-key",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.database_url == "postgresql+asyncpg://preferred:pw@localhost:5432/preferred_db"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "preferred-openai-key"
