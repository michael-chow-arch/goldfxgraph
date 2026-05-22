from pathlib import Path

from pydantic import SecretStr
from pytest import MonkeyPatch

from goldfxgraph.packages.common.settings import GoldFXGraphSettings, load_settings


def test_settings_loads_from_explicit_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "GOLDFXGRAPH_ENV=local",
                "GOLDFXGRAPH_LOG_LEVEL=DEBUG",
                "GOLDFXGRAPH_DATABASE_URL=postgresql+asyncpg://u:p@localhost:5432/db",
                "GOLDFXGRAPH_XAUUSD_CSV_PATH=data/raw/xauusd_d.csv",
                "GOLDFXGRAPH_CURRENT_QUOTE_URL=https://example.test/quote",
                "GOLDFXGRAPH_CURRENT_QUOTE_API_KEY=quote-key",
                "GOLDFXGRAPH_AGENT_API_BASE_URL=https://agent.example.test/v1",
                "GOLDFXGRAPH_AGENT_API_KEY=agent-key",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.env == "local"
    assert settings.log_level == "DEBUG"
    assert str(settings.xauusd_csv_path) == "data/raw/xauusd_d.csv"
    assert settings.agent_api_base_url == "https://agent.example.test/v1"
    assert settings.agent_api_key is not None
    assert settings.agent_api_key.get_secret_value() == "agent-key"


def test_settings_repr_does_not_expose_agent_key() -> None:
    settings = GoldFXGraphSettings(
        agent_api_key=SecretStr("super-secret"),
        current_quote_api_key=SecretStr("quote-secret"),
    )

    rendered = repr(settings)

    assert "super-secret" not in rendered
    assert "quote-secret" not in rendered


def test_environment_variables_override_env_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(
        "\n".join(
            [
                "GOLDFXGRAPH_LOG_LEVEL=INFO",
                "GOLDFXGRAPH_XAUUSD_CSV_PATH=data/raw/xauusd_d.csv",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOLDFXGRAPH_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("GOLDFXGRAPH_XAUUSD_CSV_PATH", "env/path.csv")

    settings = load_settings(env_file=env_file)

    assert settings.log_level == "ERROR"
    assert str(settings.xauusd_csv_path) == "env/path.csv"
