from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import isfinite
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
from pydantic import SecretStr

from goldfxgraph.market_data.csv_loader import load_xauusd_daily_csv
from goldfxgraph.schemas.forecast import DailyBar, ForecastDirection


class BackfillValidationError(ValueError):
    """CSV 补数候选数据或写盘过程无法通过校验。"""


@dataclass(slots=True)
class BackfillResult:
    csv_path: Path
    latest_existing_date: date | None
    target_date: date
    missing_dates: list[date]
    appended_dates: list[date]
    written: bool


@dataclass(slots=True)
class BackfillAgentResult:
    summary: str
    direction: ForecastDirection
    confidence: float
    risk_notes: list[str]


class BackfillAgentClient(Protocol):
    def invoke_agent(self, agent_name: str, payload: dict[str, object]) -> BackfillAgentResult: ...


def run_eod_backfill(
    *,
    settings,
    agent_client: BackfillAgentClient | None = None,
    now: datetime | None = None,
    csv_path: Path | None = None,
) -> BackfillResult:
    path = Path(csv_path or settings.xauusd_csv_path)
    market_data = load_xauusd_daily_csv(path)
    bars = list(market_data.bars)
    latest_existing_date = market_data.latest_bar.date
    target_date = _latest_completed_trading_day(
        now=now or datetime.now(UTC),
        timezone_name=settings.eod_backfill_timezone,
        cutoff_hour=settings.eod_backfill_cutoff_hour,
        cutoff_minute=settings.eod_backfill_cutoff_minute,
    )

    missing_dates = _missing_trading_days(latest_existing_date, target_date)
    if not missing_dates:
        return BackfillResult(
            csv_path=path,
            latest_existing_date=latest_existing_date,
            target_date=target_date,
            missing_dates=[],
            appended_dates=[],
            written=False,
        )

    agent = agent_client or _build_default_agent_client(settings)
    appended_bars: list[DailyBar] = []
    for missing_date in missing_dates:
        candidate = _discover_candidate_bar(
            agent_client=agent,
            missing_date=missing_date,
            latest_existing_bar=bars[-1],
            symbol=market_data.symbol,
        )
        appended_bars.append(candidate)
        bars.append(candidate)

    _write_bars_atomically(path, bars)

    return BackfillResult(
        csv_path=path,
        latest_existing_date=latest_existing_date,
        target_date=target_date,
        missing_dates=missing_dates,
        appended_dates=[bar.date for bar in appended_bars],
        written=True,
    )


def _discover_candidate_bar(
    *,
    agent_client: BackfillAgentClient,
    missing_date: date,
    latest_existing_bar: DailyBar,
    symbol: str,
) -> DailyBar:
    agent_result = agent_client.invoke_agent(
        "eod_backfill",
        {
            "missing_date": missing_date.isoformat(),
            "symbol": symbol,
            "latest_existing_bar": _bar_to_payload(latest_existing_bar),
            "required_fields": ["date", "open", "high", "low", "close", "source", "symbol"],
        },
    )
    payload = _parse_candidate_payload(agent_result.summary)
    candidate = _payload_to_daily_bar(payload, fallback_symbol=symbol)
    if candidate.date != missing_date:
        raise BackfillValidationError(
            f"candidate date {candidate.date.isoformat()} does not match missing date {missing_date.isoformat()}"
        )
    if candidate.symbol != symbol:
        raise BackfillValidationError(f"candidate symbol {candidate.symbol} does not match expected symbol {symbol}")
    return candidate


def _parse_candidate_payload(summary: str) -> dict[str, Any]:
    try:
        payload = json.loads(summary)
    except json.JSONDecodeError as exc:
        raise BackfillValidationError("agent candidate payload is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise BackfillValidationError("agent candidate payload must be a JSON object")

    return payload


def _payload_to_daily_bar(payload: dict[str, Any], *, fallback_symbol: str) -> DailyBar:
    source = _optional_string(payload.get("source"))
    symbol = _optional_string(payload.get("symbol")) or fallback_symbol
    date_value = payload.get("date")
    if date_value is None:
        raise BackfillValidationError("candidate payload missing date")

    try:
        parsed_date = pd.to_datetime(date_value, errors="raise").date()
    except Exception as exc:  # noqa: BLE001
        raise BackfillValidationError("candidate payload contains invalid date") from exc

    try:
        return DailyBar(
            date=parsed_date,
            open=_require_positive_float(payload, "open"),
            high=_require_positive_float(payload, "high"),
            low=_require_positive_float(payload, "low"),
            close=_require_positive_float(payload, "close"),
            volume=_optional_float(payload.get("volume")),
            source=source,
            symbol=symbol,
        )
    except ValueError as exc:
        raise BackfillValidationError(str(exc)) from exc


def _require_positive_float(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if value is None:
        raise BackfillValidationError(f"candidate payload missing {key}")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BackfillValidationError(f"candidate payload contains invalid {key}") from exc
    if parsed <= 0 or not isfinite(parsed):
        raise BackfillValidationError(f"candidate payload contains invalid {key}")
    return parsed


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise BackfillValidationError("candidate payload contains invalid volume") from exc


def _optional_string(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    rendered = str(value).strip()
    return rendered or None


def _bar_to_payload(bar: DailyBar) -> dict[str, Any]:
    return {
        "date": bar.date.isoformat(),
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "source": bar.source,
        "symbol": bar.symbol,
    }


def _latest_completed_trading_day(
    *,
    now: datetime,
    timezone_name: str,
    cutoff_hour: int,
    cutoff_minute: int,
) -> date:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    candidate = local_now.date()
    cutoff = time(hour=cutoff_hour, minute=cutoff_minute)
    if local_now.weekday() >= 5 or local_now.timetz().replace(tzinfo=None) < cutoff:
        candidate -= timedelta(days=1)

    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)

    return candidate


def _missing_trading_days(latest_existing_date: date, target_date: date) -> list[date]:
    if latest_existing_date >= target_date:
        return []

    missing_dates: list[date] = []
    cursor = latest_existing_date + timedelta(days=1)
    while cursor <= target_date:
        if cursor.weekday() < 5:
            missing_dates.append(cursor)
        cursor += timedelta(days=1)
    return missing_dates


def _write_bars_atomically(path: Path, bars: list[DailyBar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_bar_to_payload(bar) for bar in sorted(bars, key=lambda bar: bar.date)]
    frame = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "source", "symbol"])
    frame["date"] = frame["date"].map(lambda value: value.isoformat() if hasattr(value, "isoformat") else value)

    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        suffix=".csv",
        dir=str(path.parent),
        encoding="utf-8",
    ) as handle:
        temp_path = Path(handle.name)
        frame.to_csv(handle, index=False)

    try:
        os.replace(temp_path, path)
    except Exception as exc:  # noqa: BLE001
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise BackfillValidationError(f"failed to atomically replace CSV: {exc}") from exc


def _build_default_agent_client(settings) -> BackfillAgentClient:
    base_url = settings.openai_base_url or settings.agent_api_base_url
    model = settings.openai_model
    api_key = settings.openai_api_key or settings.agent_api_key
    if not base_url or not model or not api_key:
        raise BackfillValidationError("backfill agent is not configured")
    return _BackfillHttpAgentClient(
        base_url=base_url,
        model=model,
        api_key=api_key,
    )


class _BackfillHttpAgentClient:
    def __init__(self, *, base_url: str, model: str, api_key: SecretStr) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key.get_secret_value()

    def invoke_agent(self, agent_name: str, payload: dict[str, object]) -> BackfillAgentResult:
        request_payload = {
            "model": self._model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 GoldFXGraph 的 EOD 补数 agent。"
                        "请根据输入信息查询并返回一个 JSON object，"
                        "字段必须包含 date、open、high、low、close、source、symbol。"
                        "summary 字段必须是该 JSON object 的字符串形式，不要加额外解释。"
                        "若缺少有效数据，请返回 summary 中的 JSON object 说明 error。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"agent_name": agent_name, "payload": payload},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
        }

        with httpx.Client(timeout=20) as client:
            response = client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        if isinstance(content, dict):
            summary = json.dumps(content, ensure_ascii=False)
        else:
            summary = str(content)

        return BackfillAgentResult(
            summary=summary,
            direction=ForecastDirection.neutral,
            confidence=0.5,
            risk_notes=[],
        )
