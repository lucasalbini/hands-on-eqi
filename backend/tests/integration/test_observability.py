import json
from typing import Any

import httpx

from app.observability import (
    field_validation_failures_total,
    pipeline_runs_total,
    pipeline_stage_failures_total,
)
from tests.integration.test_pipeline_analysis import VALID_ANALYSIS
from tests.integration.test_pipeline_extraction import VALID_EXTRACTION, _upload_fixture


async def test_metrics_endpoint_is_exposed(client: httpx.AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "pipeline_runs_total" in response.text


async def test_completed_pipeline_increments_runs_metric(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    before = pipeline_runs_total.labels(status="completed")._value.get()
    fake_llm([json.dumps(VALID_EXTRACTION), json.dumps(VALID_ANALYSIS)])
    await _upload_fixture(client)

    after = pipeline_runs_total.labels(status="completed")._value.get()
    assert after == before + 1


async def test_invalid_cnpj_increments_field_validation_metric(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    before = field_validation_failures_total.labels(field_name="provider.cnpj")._value.get()
    payload = json.loads(json.dumps(VALID_EXTRACTION))
    payload["provider"]["cnpj"] = "11.222.333/0001-80"  # DV inválido
    fake_llm([json.dumps(payload), json.dumps(VALID_ANALYSIS)])
    await _upload_fixture(client)

    after = field_validation_failures_total.labels(field_name="provider.cnpj")._value.get()
    assert after == before + 1


async def test_parse_failure_increments_stage_failure_metric(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    before = pipeline_stage_failures_total.labels(stage="parse")._value.get()
    fake_llm([json.dumps(VALID_EXTRACTION)])
    await _upload_fixture(client, "escaneado.pdf")

    after = pipeline_stage_failures_total.labels(stage="parse")._value.get()
    assert after == before + 1
