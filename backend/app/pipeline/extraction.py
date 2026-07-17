"""Estágio de extração: chamada LLM literal + validação determinística por campo."""

from collections.abc import Callable

from app.config import settings
from app.llm.client import structured_completion
from app.llm.prompt_loader import load_prompt
from app.models import ExtractedField
from app.schemas import ContractType, ExtractionResult
from app.validators import ValidationResult, parse_date_br, validate_cnpj, validate_uf


def validate_contract_type(raw: str) -> ValidationResult:
    """Pertinência ao enum de tipos. Na extração é redundante (schema garante);
    existe para as correções do usuário passarem pela mesma régua."""
    value = raw.strip()
    for contract_type in ContractType:
        if value == contract_type.value:
            return ValidationResult(is_valid=True, normalized=contract_type.value, error=None)
    options = ", ".join(c.value for c in ContractType)
    return ValidationResult(
        is_valid=False, normalized=None, error=f"tipo de contrato inválido; use um de: {options}"
    )


FIELD_VALIDATORS: dict[str, Callable[[str], ValidationResult]] = {
    "contract_type": validate_contract_type,
    "issue_date": parse_date_br,
    "provider.cnpj": validate_cnpj,
    "provider.uf": validate_uf,
    "customer.cnpj": validate_cnpj,
    "customer.uf": validate_uf,
}


async def run_extraction(contract_text: str) -> tuple[ExtractionResult, str]:
    """Chama o LLM de extração (temperature 0) e retorna (resultado, versão do prompt)."""
    system, user_template, version = load_prompt(settings.extraction_prompt_version)
    # .replace, não .format: o texto do contrato é não confiável e pode conter chaves.
    user = user_template.replace("{contract_text}", contract_text)
    result = await structured_completion(
        model=settings.extraction_model,
        system=system,
        user=user,
        schema=ExtractionResult,
        temperature=0.0,
    )
    return result, version


def flatten_extraction(result: ExtractionResult) -> dict[str, str | None]:
    """Achata o resultado em paths planos: contract_type, provider.cnpj, ..."""
    fields: dict[str, str | None] = {
        "contract_type": result.contract_type.value if result.contract_type else None,
        "contract_object": result.contract_object,
        "issue_date": result.issue_date,
    }
    for role in ("provider", "customer"):
        party = getattr(result, role)
        for name, value in party.model_dump().items():
            fields[f"{role}.{name}"] = value
    return fields


def build_extracted_fields(flat: dict[str, str | None]) -> list[ExtractedField]:
    """Aplica os validadores determinísticos e monta os registros campo-a-campo.

    Campo inválido nunca é descartado: persiste com is_valid=False e o motivo.
    Ausente (None) não é erro de validação — is_valid=True com valores nulos.
    """
    records: list[ExtractedField] = []
    for field_name, llm_value in flat.items():
        validator = FIELD_VALIDATORS.get(field_name)
        if llm_value is None or validator is None:
            records.append(
                ExtractedField(field_name=field_name, llm_value=llm_value, is_valid=True)
            )
            continue
        outcome = validator(llm_value)
        records.append(
            ExtractedField(
                field_name=field_name,
                llm_value=llm_value,
                normalized_value=outcome.normalized,
                is_valid=outcome.is_valid,
                validation_error=outcome.error,
            )
        )
    return records
