from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import selectinload

from goldfxgraph.persistence.database import SessionFactory
from goldfxgraph.persistence.models import (
    ForecastEvaluationModel,
    ForecastModel,
    MarketDataBarModel,
    ResearchRunModel,
    SchedulerRunModel,
)
from goldfxgraph.schemas.forecast import (
    Actionability,
    CommitteeDecision,
    DailyBar,
    DebateCase,
    DebateRebuttal,
    DecisionValidationResult,
    EvidencePackage,
    FinalBias,
    FinalDebatePosition,
    FinalForecast,
    ForecastDirection,
    ForecastEvaluationResult,
    ForecastHistoryItem,
    ForecastResult,
    ForecastWindowDirection,
    PromptVersionMetadata,
    ResearchRunResult,
    SchedulerRunStatus,
)
from goldfxgraph.timeframes import trading_day_for_timestamp

JsonObject = dict[str, Any]
_JSON_OBJECT_ADAPTER: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)


class MarketDataRepository:
    _UPSERT_BATCH_SIZE = 1000

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def upsert_market_bars(self, bars: list[DailyBar]) -> int:
        unique_bars = self._dedupe_bars(bars)
        if not unique_bars:
            return 0

        written_at = datetime.now(UTC)

        async with self._session_factory.sessionmaker() as session:
            for chunk in _chunked(unique_bars, self._UPSERT_BATCH_SIZE):
                rows = [_daily_bar_to_row(bar, written_at) for bar in chunk]
                insert_statement = self._build_upsert_statement(session, rows, written_at)
                await session.execute(insert_statement)
            await session.commit()
        return len(unique_bars)

    async def get_latest_market_bar(self, symbol: str = "XAUUSD") -> DailyBar | None:
        normalized_symbol = _normalize_symbol(symbol)
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(MarketDataBarModel)
                .where(MarketDataBarModel.symbol == normalized_symbol)
                .order_by(MarketDataBarModel.bar_date.desc(), MarketDataBarModel.id.desc())
                .limit(1)
            )
            result = await session.execute(statement)
            model = result.scalars().first()
            if model is None:
                return None
            return _daily_bar_from_model(model)

    async def get_market_bars_between(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[DailyBar]:
        normalized_symbol = _normalize_symbol(symbol)
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(MarketDataBarModel)
                .where(
                    MarketDataBarModel.symbol == normalized_symbol,
                    MarketDataBarModel.bar_date >= start_date,
                    MarketDataBarModel.bar_date <= end_date,
                )
                .order_by(MarketDataBarModel.bar_date.asc(), MarketDataBarModel.id.asc())
            )
            result = await session.execute(statement)
            models = result.scalars().all()
            return [_daily_bar_from_model(model) for model in models]

    async def get_recent_market_bars(self, symbol: str = "XAUUSD", limit: int = 60) -> list[DailyBar]:
        normalized_symbol = _normalize_symbol(symbol)
        normalized_limit = max(1, min(int(limit), 180))
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(MarketDataBarModel)
                .where(MarketDataBarModel.symbol == normalized_symbol)
                .order_by(MarketDataBarModel.bar_date.desc(), MarketDataBarModel.id.desc())
                .limit(normalized_limit)
            )
            result = await session.execute(statement)
            models = list(result.scalars().all())
            return [_daily_bar_from_model(model) for model in reversed(models)]

    async def get_market_bars_for_date(self, symbol: str, target_date: date) -> DailyBar | None:
        normalized_symbol = _normalize_symbol(symbol)
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(MarketDataBarModel)
                .where(
                    MarketDataBarModel.symbol == normalized_symbol,
                    MarketDataBarModel.bar_date == target_date,
                )
                .limit(1)
            )
            result = await session.execute(statement)
            model = result.scalars().first()
            if model is None:
                return None
            return _daily_bar_from_model(model)

    async def get_market_bars_count(self, symbol: str = "XAUUSD") -> int:
        normalized_symbol = _normalize_symbol(symbol)
        async with self._session_factory.sessionmaker() as session:
            statement = select(func.count(MarketDataBarModel.id)).where(MarketDataBarModel.symbol == normalized_symbol)
            result = await session.execute(statement)
            count = result.scalar_one()
            return int(count)

    @staticmethod
    def _dedupe_bars(bars: list[DailyBar]) -> list[DailyBar]:
        unique_bars: dict[tuple[str, date], DailyBar] = {}
        for bar in bars:
            unique_bars[_market_bar_key(bar)] = bar
        return list(unique_bars.values())

    @staticmethod
    def _build_upsert_statement(session: Any, rows: list[dict[str, Any]], written_at: datetime) -> Any:
        dialect_name = getattr(getattr(session, "bind", None), "dialect", None)
        dialect_name = getattr(dialect_name, "name", "")
        insert_builder = sqlite_insert if dialect_name == "sqlite" else postgres_insert
        insert_statement = insert_builder(MarketDataBarModel).values(rows)
        return insert_statement.on_conflict_do_update(
            index_elements=[MarketDataBarModel.symbol, MarketDataBarModel.bar_date],
            set_={
                "open": insert_statement.excluded.open,
                "high": insert_statement.excluded.high,
                "low": insert_statement.excluded.low,
                "close": insert_statement.excluded.close,
                "volume": insert_statement.excluded.volume,
                "source": insert_statement.excluded.source,
                "updated_at": written_at,
            },
        )


class ForecastRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._market_data_repository = MarketDataRepository(session_factory)

    async def upsert_market_bars(self, bars: list[DailyBar]) -> int:
        return await self._market_data_repository.upsert_market_bars(bars)

    async def get_latest_market_bar(self, symbol: str = "XAUUSD") -> DailyBar | None:
        return await self._market_data_repository.get_latest_market_bar(symbol)

    async def get_market_bars_between(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[DailyBar]:
        return await self._market_data_repository.get_market_bars_between(symbol, start_date, end_date)

    async def get_recent_market_bars(self, symbol: str = "XAUUSD", limit: int = 60) -> list[DailyBar]:
        return await self._market_data_repository.get_recent_market_bars(symbol, limit)

    async def get_market_bars_for_date(self, symbol: str, target_date: date) -> DailyBar | None:
        return await self._market_data_repository.get_market_bars_for_date(symbol, target_date)

    async def get_market_bars_count(self, symbol: str = "XAUUSD") -> int:
        return await self._market_data_repository.get_market_bars_count(symbol)

    async def create_research_run(self, input_summary: dict[str, object]) -> ResearchRunModel:
        async with self._session_factory.sessionmaker() as session:
            run = ResearchRunModel(status="running", input_summary=_json_safe_object(input_summary))
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    async def create_scheduler_run(self, input_summary: dict[str, object]) -> SchedulerRunModel:
        async with self._session_factory.sessionmaker() as session:
            run = SchedulerRunModel(
                status="running",
                current_stage="scheduled",
                input_summary=_json_safe_object(input_summary),
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    async def update_scheduler_run_stage(
        self,
        run_id: int,
        *,
        current_stage: str,
        agent_statuses: list[dict[str, str]] | None = None,
        agent_diagnostics: list[dict[str, Any]] | None = None,
        status: str = "running",
        last_error: str | None = None,
        completed_at: datetime | None = None,
    ) -> SchedulerRunStatus:
        async with self._session_factory.sessionmaker() as session:
            run = await session.get(SchedulerRunModel, run_id)
            if run is None:
                raise ValueError(f"scheduler run {run_id} not found")
            run.current_stage = current_stage
            run.status = status
            run.agent_statuses = list(agent_statuses or [])
            run.agent_diagnostics = list(agent_diagnostics or [])
            run.last_error = last_error
            run.completed_at = completed_at
            await session.commit()
            await session.refresh(run)
            return self._scheduler_status_from_model(run)

    async def mark_scheduler_run_success(self, run_id: int, *, current_stage: str = "completed") -> SchedulerRunStatus:
        return await self.update_scheduler_run_stage(
            run_id,
            current_stage=current_stage,
            status="success",
            completed_at=datetime.now(UTC),
        )

    async def mark_scheduler_run_failed(
        self,
        run_id: int,
        *,
        current_stage: str,
        last_error: str,
    ) -> SchedulerRunStatus:
        return await self.update_scheduler_run_stage(
            run_id,
            current_stage=current_stage,
            status="failed",
            last_error=last_error,
            completed_at=datetime.now(UTC),
        )

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
                window_directions=[window.model_dump(mode="json") for window in forecast.window_directions],
                entry_price=forecast.entry_price,
                entry_price_low=forecast.entry_price_low,
                entry_price_high=forecast.entry_price_high,
                take_profit_price=forecast.take_profit_price,
                stop_loss_price=forecast.stop_loss_price,
                holding_period=forecast.holding_period,
                intraday_action=forecast.intraday_action,
                long_term_action=forecast.long_term_action,
                confidence_score=forecast.confidence_score,
                technical_summary=forecast.technical_summary,
                macro_summary=forecast.macro_summary,
                news_summary=forecast.news_summary,
                market_sentiment_summary=forecast.market_sentiment_summary,
                alt_data_summary=forecast.alt_data_summary,
                risk_summary=forecast.risk_summary,
                agent_votes=[vote.model_dump(mode="json") for vote in forecast.agent_votes],
                risk_notes=list(forecast.risk_notes),
                disclaimer=forecast.disclaimer,
                evidence_package=_json_model(getattr(forecast, "evidence_package", None)),
                bull_opening_case=_json_model(getattr(forecast, "bull_opening_case", None)),
                bear_opening_case=_json_model(getattr(forecast, "bear_opening_case", None)),
                bull_rebuttal=_json_model(getattr(forecast, "bull_rebuttal", None)),
                bear_rebuttal=_json_model(getattr(forecast, "bear_rebuttal", None)),
                bull_final_position=_json_model(getattr(forecast, "bull_final_position", None)),
                bear_final_position=_json_model(getattr(forecast, "bear_final_position", None)),
                committee_decision=_json_model(getattr(forecast, "committee_decision", None)),
                validation_status=_json_model(getattr(forecast, "validation_status", None)),
                prompt_versions=_json_list_model(getattr(forecast, "prompt_versions", None)),
            )
            session.add(forecast_model)
            await session.commit()
            await session.refresh(forecast_model)
            return self._forecast_result_from_model(forecast_model)

    async def save_forecast_evaluation(
        self,
        forecast_id: int,
        evaluation: ForecastEvaluationResult,
    ) -> ForecastEvaluationResult:
        async with self._session_factory.sessionmaker() as session:
            forecast = await session.get(ForecastModel, forecast_id)
            if forecast is None:
                raise ValueError(f"forecast {forecast_id} not found")
            if evaluation.run_id != forecast.run_id:
                raise ValueError(
                    f"evaluation run_id {evaluation.run_id} does not match forecast run_id {forecast.run_id}"
                )

            evaluation_model = ForecastEvaluationModel(
                forecast_id=forecast_id,
                run_id=forecast.run_id,
                evaluated_at=evaluation.evaluated_at,
                evaluation_window_end=evaluation.evaluation_window_end,
                result=evaluation.result,
                direction_hit=evaluation.direction_hit,
                pnl_points=evaluation.pnl_points,
                settlement_price=evaluation.settlement_price,
                summary=evaluation.summary,
                feedback_notes=list(evaluation.feedback_notes),
                signal_coverage=_json_safe_object(evaluation.signal_coverage),
            )
            session.add(evaluation_model)
            await session.commit()
            await session.refresh(evaluation_model)
            return self._evaluation_result_from_model(evaluation_model)

    async def get_latest_forecast(self) -> ForecastResult | None:
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(ForecastModel)
                .options(selectinload(ForecastModel.evaluation))
                .order_by(
                    ForecastModel.created_at.desc(),
                    ForecastModel.id.desc(),
                )
            )
            result = await session.execute(statement)
            forecast_model = result.scalars().first()
            if forecast_model is None:
                return None
            return self._forecast_result_from_model(forecast_model)

    async def get_forecast_evaluations(self, forecast_id: int) -> list[ForecastEvaluationResult]:
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(ForecastEvaluationModel)
                .where(ForecastEvaluationModel.forecast_id == forecast_id)
                .order_by(ForecastEvaluationModel.evaluated_at.desc(), ForecastEvaluationModel.id.desc())
            )
            result = await session.execute(statement)
            models = result.scalars().all()
            return [self._evaluation_result_from_model(model) for model in models]

    async def get_forecast_history(self, limit: int = 50) -> list[ForecastHistoryItem]:
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(ForecastModel)
                .options(selectinload(ForecastModel.evaluation))
                .order_by(ForecastModel.created_at.desc(), ForecastModel.id.desc())
                .limit(limit)
            )
            result = await session.execute(statement)
            models = result.scalars().all()
            history: list[ForecastHistoryItem] = []
            for model in models:
                history.append(
                    ForecastHistoryItem(
                        forecast=self._forecast_result_from_model(model),
                        evaluation=(
                            self._evaluation_result_from_model(model.evaluation)
                            if model.evaluation is not None
                            else None
                        ),
                    )
                )
            return history

    async def get_daily_forecast_history(
        self,
        limit: int = 50,
        *,
        timezone_name: str,
        cutoff_hour: int,
        cutoff_minute: int,
    ) -> list[ForecastHistoryItem]:
        normalized_limit = max(1, min(int(limit), 500))
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(ForecastModel)
                .options(selectinload(ForecastModel.evaluation))
                .order_by(
                    ForecastModel.reference_time.desc(),
                    ForecastModel.id.desc(),
                )
                .limit(500)
            )
            result = await session.execute(statement)
            models = result.scalars().all()

        history: list[ForecastHistoryItem] = []
        seen_trading_days: set[date] = set()
        for model in models:
            trading_day = trading_day_for_timestamp(
                _ensure_utc(model.reference_time),
                timezone_name=timezone_name,
                cutoff_hour=cutoff_hour,
                cutoff_minute=cutoff_minute,
            )
            if trading_day in seen_trading_days:
                continue

            seen_trading_days.add(trading_day)
            history.append(
                ForecastHistoryItem(
                    forecast=self._forecast_result_from_model(model),
                    evaluation=(
                        self._evaluation_result_from_model(model.evaluation) if model.evaluation is not None else None
                    ),
                    trading_day=trading_day,
                )
            )
            if len(history) >= normalized_limit:
                break

        return history

    async def get_forecast_history_for_date(
        self,
        target_date: date,
        timezone_name: str,
    ) -> list[ForecastHistoryItem]:
        local_timezone = ZoneInfo(timezone_name)
        start_local = datetime(target_date.year, target_date.month, target_date.day, tzinfo=local_timezone)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(UTC)
        end_utc = end_local.astimezone(UTC)

        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(ForecastModel)
                .options(selectinload(ForecastModel.evaluation))
                .where(
                    ForecastModel.reference_time >= start_utc,
                    ForecastModel.reference_time < end_utc,
                )
                .order_by(ForecastModel.reference_time.asc(), ForecastModel.id.asc())
            )
            result = await session.execute(statement)
            models = result.scalars().all()
            history: list[ForecastHistoryItem] = []
            for model in models:
                history.append(
                    ForecastHistoryItem(
                        forecast=self._forecast_result_from_model(model),
                        evaluation=(
                            self._evaluation_result_from_model(model.evaluation)
                            if model.evaluation is not None
                            else None
                        ),
                    )
                )
            return history

    async def get_latest_evaluation_summary(self, limit: int = 5) -> list[str]:
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(ForecastEvaluationModel)
                .order_by(ForecastEvaluationModel.evaluated_at.desc(), ForecastEvaluationModel.id.desc())
                .limit(limit)
            )
            result = await session.execute(statement)
            models = result.scalars().all()
            return [model.summary for model in models]

    async def get_research_run(self, run_id: int) -> ResearchRunResult | None:
        async with self._session_factory.sessionmaker() as session:
            result = await session.execute(
                select(ResearchRunModel)
                .options(
                    selectinload(ResearchRunModel.forecast).selectinload(ForecastModel.evaluation),
                    selectinload(ResearchRunModel.evaluation),
                )
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
                evaluation=self._evaluation_result_from_model(run.evaluation) if run.evaluation else None,
            )

    async def get_latest_scheduler_run(self) -> SchedulerRunStatus | None:
        async with self._session_factory.sessionmaker() as session:
            statement = (
                select(SchedulerRunModel)
                .order_by(
                    SchedulerRunModel.started_at.desc(),
                    SchedulerRunModel.id.desc(),
                )
                .limit(1)
            )
            result = await session.execute(statement)
            model = result.scalars().first()
            if model is None:
                return None
            return self._scheduler_status_from_model(model)

    def _forecast_result_from_model(self, forecast_model: ForecastModel) -> ForecastResult:
        agent_votes = self._json_list(forecast_model.agent_votes)
        base_forecast = ForecastResult(
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
            window_directions=[
                ForecastWindowDirection.model_validate(window)
                for window in self._json_list(forecast_model.window_directions)
            ],
            entry_price=forecast_model.entry_price,
            entry_price_low=forecast_model.entry_price_low,
            entry_price_high=forecast_model.entry_price_high,
            take_profit_price=forecast_model.take_profit_price,
            stop_loss_price=forecast_model.stop_loss_price,
            holding_period=forecast_model.holding_period,
            intraday_action=forecast_model.intraday_action,
            long_term_action=forecast_model.long_term_action,
            confidence_score=forecast_model.confidence_score,
            technical_summary=forecast_model.technical_summary,
            macro_summary=forecast_model.macro_summary,
            news_summary=forecast_model.news_summary,
            market_sentiment_summary=forecast_model.market_sentiment_summary,
            alt_data_summary=forecast_model.alt_data_summary,
            risk_summary=forecast_model.risk_summary,
            agent_votes=agent_votes,
            risk_notes=list(forecast_model.risk_notes),
            disclaimer=forecast_model.disclaimer,
        )
        if (
            forecast_model.evidence_package is None
            and forecast_model.bull_opening_case is None
            and forecast_model.bear_opening_case is None
            and forecast_model.bull_rebuttal is None
            and forecast_model.bear_rebuttal is None
            and forecast_model.bull_final_position is None
            and forecast_model.bear_final_position is None
            and forecast_model.committee_decision is None
            and forecast_model.validation_status is None
            and not forecast_model.prompt_versions
        ):
            return base_forecast

        committee_decision = self._json_object(forecast_model.committee_decision)
        validation_status = self._json_object(forecast_model.validation_status)
        evidence_package = self._json_object(forecast_model.evidence_package)
        bull_opening_case = self._json_object(forecast_model.bull_opening_case)
        bear_opening_case = self._json_object(forecast_model.bear_opening_case)
        bull_rebuttal = self._json_object(forecast_model.bull_rebuttal)
        bear_rebuttal = self._json_object(forecast_model.bear_rebuttal)
        bull_final_position = self._json_object(forecast_model.bull_final_position)
        bear_final_position = self._json_object(forecast_model.bear_final_position)
        prompt_versions = self._json_list(forecast_model.prompt_versions)

        return FinalForecast(
            **base_forecast.model_dump(),
            bull_opening_case=DebateCase.model_validate(bull_opening_case) if bull_opening_case else None,
            bear_opening_case=DebateCase.model_validate(bear_opening_case) if bear_opening_case else None,
            bull_rebuttal=DebateRebuttal.model_validate(bull_rebuttal) if bull_rebuttal else None,
            bear_rebuttal=DebateRebuttal.model_validate(bear_rebuttal) if bear_rebuttal else None,
            bull_final_position=FinalDebatePosition.model_validate(bull_final_position)
            if bull_final_position
            else None,
            bear_final_position=FinalDebatePosition.model_validate(bear_final_position)
            if bear_final_position
            else None,
            final_bias=FinalBias(committee_decision.get("final_bias"))
            if committee_decision.get("final_bias")
            else FinalBias.cautious,
            actionability=Actionability(committee_decision.get("actionability"))
            if committee_decision.get("actionability")
            else Actionability.no_trade,
            evidence_package=EvidencePackage.model_validate(evidence_package) if evidence_package else None,
            committee_decision=CommitteeDecision.model_validate(committee_decision) if committee_decision else None,
            validation_status=DecisionValidationResult.model_validate(validation_status)
            if validation_status
            else None,
            prompt_versions=[
                PromptVersionMetadata.model_validate(prompt_version) for prompt_version in prompt_versions
            ],
        )

    def _evaluation_result_from_model(self, evaluation_model: ForecastEvaluationModel) -> ForecastEvaluationResult:
        return ForecastEvaluationResult(
            id=evaluation_model.id,
            forecast_id=evaluation_model.forecast_id,
            run_id=evaluation_model.run_id,
            evaluated_at=_ensure_utc(evaluation_model.evaluated_at),
            evaluation_window_end=_ensure_utc(evaluation_model.evaluation_window_end),
            result=evaluation_model.result,
            direction_hit=evaluation_model.direction_hit,
            pnl_points=evaluation_model.pnl_points,
            settlement_price=evaluation_model.settlement_price,
            summary=evaluation_model.summary,
            feedback_notes=[str(note) for note in self._json_list(evaluation_model.feedback_notes)],
            signal_coverage=self._json_object(evaluation_model.signal_coverage),
        )

    def _scheduler_status_from_model(self, scheduler_model: SchedulerRunModel) -> SchedulerRunStatus:
        return SchedulerRunStatus(
            id=scheduler_model.id,
            status=scheduler_model.status,
            started_at=_ensure_utc(scheduler_model.started_at),
            completed_at=_ensure_utc(scheduler_model.completed_at) if scheduler_model.completed_at else None,
            current_stage=scheduler_model.current_stage,
            agent_statuses=[dict(status) for status in self._json_list(scheduler_model.agent_statuses)],
            agent_diagnostics=[dict(diagnostic) for diagnostic in self._json_list(scheduler_model.agent_diagnostics)],
            last_error=scheduler_model.last_error,
        )

    @staticmethod
    def _json_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return []

    @staticmethod
    def _json_object(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json_safe_object(value: dict[str, object]) -> JsonObject:
    return _JSON_OBJECT_ADAPTER.dump_python(value, mode="json")


def _json_model(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return _JSON_OBJECT_ADAPTER.dump_python(value, mode="json")
    return None


def _json_list_model(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            if hasattr(item, "model_dump"):
                result.append(item.model_dump(mode="json"))
            elif isinstance(item, dict):
                result.append(_JSON_OBJECT_ADAPTER.dump_python(item, mode="json"))
        return result
    return []


def _normalize_symbol(symbol: str) -> str:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    return normalized_symbol


def _market_bar_key(bar: DailyBar) -> tuple[str, date]:
    return _normalize_symbol(bar.symbol), bar.date


def _daily_bar_to_row(bar: DailyBar, written_at: datetime) -> dict[str, Any]:
    symbol, bar_date = _market_bar_key(bar)
    return {
        "symbol": symbol,
        "bar_date": bar_date,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "source": bar.source,
        "created_at": written_at,
        "updated_at": written_at,
    }


def _daily_bar_from_model(model: MarketDataBarModel) -> DailyBar:
    return DailyBar(
        date=model.bar_date,
        open=model.open,
        high=model.high,
        low=model.low,
        close=model.close,
        volume=model.volume,
        source=model.source,
        symbol=model.symbol,
    )


def _chunked(values: list[DailyBar], batch_size: int) -> list[list[DailyBar]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [values[index : index + batch_size] for index in range(0, len(values), batch_size)]
