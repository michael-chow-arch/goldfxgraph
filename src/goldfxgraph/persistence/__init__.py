"""Persistence boundary package."""

from goldfxgraph.persistence.database import SessionFactory, create_session_factory, init_models
from goldfxgraph.persistence.external_source_registry import ExternalSourceRegistryService, ExternalSourceSnapshot
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.persistence.seed_prompt_templates import (
    REQUIRED_ANALYSIS_PROMPT_KEYS,
    REQUIRED_COMMITTEE_PROMPT_KEYS,
    REQUIRED_PROMPT_KEYS,
    PromptRegistryValidationError,
    validate_required_prompt_templates,
)

__all__ = [
    "ForecastRepository",
    "ExternalSourceRegistryService",
    "ExternalSourceSnapshot",
    "SessionFactory",
    "PromptRegistryValidationError",
    "REQUIRED_ANALYSIS_PROMPT_KEYS",
    "REQUIRED_COMMITTEE_PROMPT_KEYS",
    "REQUIRED_PROMPT_KEYS",
    "create_session_factory",
    "init_models",
    "validate_required_prompt_templates",
]
