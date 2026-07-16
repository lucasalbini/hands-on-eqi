"""Validação determinística de UF (unidade federativa brasileira)."""

from app.validators.base import ValidationResult

_UFS: frozenset[str] = frozenset(
    {
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    }
)


def validate_uf(raw: str) -> ValidationResult:
    """Valida uma sigla de UF e normaliza para maiúsculas.

    Nome por extenso ("São Paulo") é inválido de propósito: a UI permite
    corrigir para a sigla.
    """
    normalized = raw.strip().upper()

    if not normalized:
        return ValidationResult(is_valid=False, normalized=None, error="UF vazia")

    if normalized not in _UFS:
        return ValidationResult(
            is_valid=False,
            normalized=None,
            error=f"UF inválida: {normalized!r} não é uma sigla de UF brasileira",
        )

    return ValidationResult(is_valid=True, normalized=normalized, error=None)
