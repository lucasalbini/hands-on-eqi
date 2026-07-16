"""Tipo de resultado compartilhado pelos validadores determinísticos."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """Resultado de uma validação determinística.

    - ``is_valid``: se o valor bruto passou na validação.
    - ``normalized``: valor canônico quando válido, ``None`` caso contrário.
    - ``error``: motivo da rejeição em pt-BR quando inválido, ``None`` caso contrário.
    """

    is_valid: bool
    normalized: str | None
    error: str | None
