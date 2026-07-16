"""Estágio de análise: resumo executivo + análise qualitativa com modelo forte."""

import json
from collections.abc import Mapping

from app.config import settings
from app.llm.client import structured_completion
from app.llm.prompt_loader import load_prompt
from app.schemas import AnalysisResult

# Análise qualitativa tolera leve variação de redação; extração literal usa 0.0.
ANALYSIS_TEMPERATURE = 0.3


async def run_analysis(
    contract_text: str, extracted_metadata: Mapping[str, str | None]
) -> tuple[AnalysisResult, str]:
    """Chama o LLM de análise e retorna (resultado, versão do prompt).

    Recebe os metadados já validados para dar contexto e coerência ao resumo.
    """
    system, user_template, version = load_prompt(settings.analysis_prompt_version)
    metadata_json = json.dumps(extracted_metadata, ensure_ascii=False, indent=2)
    # .replace, não .format: o texto do contrato é não confiável e pode conter chaves.
    user = user_template.replace("{contract_text}", contract_text).replace(
        "{extracted_metadata}", metadata_json
    )
    result = await structured_completion(
        model=settings.analysis_model,
        system=system,
        user=user,
        schema=AnalysisResult,
        temperature=ANALYSIS_TEMPERATURE,
    )
    return result, version
