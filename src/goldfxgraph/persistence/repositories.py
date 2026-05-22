from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from goldfxgraph.persistence.database import SessionFactory
from goldfxgraph.persistence.models import ForecastModel, ResearchRunModel
from goldfxgraph.schemas.forecast import ForecastDirection, ForecastResult, ResearchRunResult

JsonObject = dict[str, Any]
_JSON_OBJECT_ADAPTER: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)


class ForecastRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def create_research_run(self, input_summary: dict[str, object]) -> ResearchRunModel:
        async with self._session_factory.sessionmaker() as session:
            run = ResearchRunModel(status="running", input_summary=_json_safe_object(input_summary))
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    async def mark_run_success(self, run_id: int) -> None:
        async with self._session_factory.sessionmaker() as session:
            run = await session.get(ResearchRunModel, run_id)
            if run is None:
                raise ValueError(f"research run {run_id} not found")
            run.status = "success"
            run.completed_at = datetime.now(UTC)
            run.error_message = None
            await session.commit()

    async def mark_run_failed(self, run_id: int, error_message: str) -> None:
        async with self._session_factory.sessionmaker() as session:
            run = await session.get(ResearchRunModel, run_id)
            if run is None:
                raise ValueError(f"research run {run_id} not found")
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            run.error_message = error_message
            await session.commit()

    async def save_forecast(self, run_id: int, forecast: ForecastResult) -> ForecastResult:
        async with self._session_factory.sessionmaker() as session:
            run = await session.get(ResearchRunModel, run_id)
            if run is None:
                raise ValueError(f"research run {run_id} not found")
            forecast_model = ForecastModel(
                run_id=run_id,
                symbol=forecast.symbol,
                reference_time=forecast.reference_time,
                data_timestamp=forecast.data_timestamp,
                data_source=forecast.data_source,
                current_price=forecast.current_price,
                daily_open=forecast.daily_open,
                daily_high=forecast.daily_high,
                daily_low=forecast.daily_low,
                daily_close=forecast.daily_close,
                direction=forecast.direction.value,
                entry_price=forecast.entry_price,
                take_profit_price=forecast.take_profit_price,
                stop_loss_price=forecast.stop_loss_price,
                holding_period=forecast.holding_period,
                intraday_action=forecast.intraday_action,
                long_term_action=forecast.long_term_action,
                confidence_score=forecast.confidence_score,
                technical_summary=forecast.technical_summary,
                macro_summary=forecast.macro_summary,
                news_summary=forecast.news_summary,
                risk_summary=forecast.risk_summary,
                agent_votes=[vote.model_dump(mode="json") for vote in forecast.agent_votes],
                risk_notes=list(forecast.risk_notes),
                disclaimer=forecast.disclaimer,
            )
            session.add(forecast_model)
            await session.commit()
            await session.refresh(forecast_model)
            return self._forecast_result_from_model(forecast_model)

    async def get_latest_forecast(self) -> ForecastResult | None:
        async with self._session_factory.sessionmaker() as session:
            statement = select(ForecastModel).order_by(
                ForecastModel.created_at.desc(),
                ForecastModel.id.desc(),
            )
            result = await session.execute(statement)
            forecast_model = result.scalars().first()
            if forecast_model is None:
                return None
            return self._forecast_result_from_model(forecast_model)

    async def get_research_run(self, run_id: int) -> ResearchRunResult | None:
        async with self._session_factory.sessionmaker() as session:
            result = await session.execute(
                select(ResearchRunModel)
                .options(selectinload(ResearchRunModel.forecast))
                .where(ResearchRunModel.id == run_id)
            )
            run = result.scalars().first()
            if run is None:
                return None
            return ResearchRunResult(
                id=run.id,
                status=run.status,
                started_at=_ensure_utc(run.started_at),
                completed_at=_ensure_utc(run.completed_at) if run.completed_at else None,
                input_summary=dict(run.input_summary),
                error_message=run.error_message,
                forecast=self._forecast_result_from_model(run.forecast) if run.forecast else None,
            )

    def _forecast_result_from_model(self, forecast_model: ForecastModel) -> ForecastResult:
        agent_votes = self._json_list(forecast_model.agent_votes)
        return ForecastResult(
            id=forecast_model.id,
            run_id=forecast_model.run_id,
            symbol=forecast_model.symbol,
            reference_time=_ensure_utc(forecast_model.reference_time),
            data_timestamp=_ensure_utc(forecast_model.data_timestamp),
            data_source=forecast_model.data_source,
            current_price=forecast_model.current_price,
            daily_open=forecast_model.daily_open,
            daily_high=forecast_model.daily_high,
            daily_low=forecast_model.daily_low,
            daily_close=forecast_model.daily_close,
            direction=ForecastDirection(forecast_model.direction),
            entry_price=forecast_model.entry_price,
            take_profit_price=forecast_model.take_profit_price,
            stop_loss_price=forecast_model.stop_loss_price,
            holding_period=forecast_model.holding_period,
            intraday_action=forecast_model.intraday_action,
            long_term_action=forecast_model.long_term_action,
            confidence_score=forecast_model.confidence_score,
            technical_summary=forecast_model.technical_summary,
            macro_summary=forecast_model.macro_summary,
            news_summary=forecast_model.news_summary,
            risk_summary=forecast_model.risk_summary,
            agent_votes=agent_votes,
            risk_notes=list(forecast_model.risk_notes),
            disclaimer=forecast_model.disclaimer,
        )

    @staticmethod
    def _json_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return []


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json_safe_object(value: dict[str, object]) -> JsonObject:
    return _JSON_OBJECT_ADAPTER.dump_python(value, mode="json")
