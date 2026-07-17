"""Logs estruturados (structlog) e métricas Prometheus do pipeline."""

import logging

import structlog
from prometheus_client import Counter, Histogram

# --- Métricas do pipeline ---
# Nomeadas por estágio para dar visibilidade de onde o tempo é gasto e onde falha.

pipeline_runs_total = Counter(
    "pipeline_runs_total",
    "Execuções do pipeline por resultado final",
    labelnames=("status",),
)

pipeline_stage_duration_seconds = Histogram(
    "pipeline_stage_duration_seconds",
    "Duração de cada estágio do pipeline",
    labelnames=("stage",),
)

pipeline_stage_failures_total = Counter(
    "pipeline_stage_failures_total",
    "Falhas por estágio do pipeline",
    labelnames=("stage",),
)

field_validation_failures_total = Counter(
    "field_validation_failures_total",
    "Campos que falharam na validação determinística, por campo",
    labelnames=("field_name",),
)


def configure_logging() -> None:
    """Configura structlog com saída JSON e contextvars de request/pipeline."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
