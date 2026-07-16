"""Validação determinística de CNPJ."""

from app.validators.base import ValidationResult

_WEIGHTS_FIRST_DIGIT = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_SECOND_DIGIT = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _check_digit(digits: str, weights: tuple[int, ...]) -> int:
    total = sum(int(digit) * weight for digit, weight in zip(digits, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def validate_cnpj(raw: str) -> ValidationResult:
    """Valida um CNPJ e normaliza para ``XX.XXX.XXX/XXXX-XX``.

    Aceita entrada com ou sem formatação; qualquer caractere não-dígito é
    descartado antes da validação.
    """
    # "0" <= char <= "9" em vez de isdigit(): isdigit() aceita dígitos Unicode
    # (ex.: "²") que quebrariam int() no cálculo dos verificadores.
    digits = "".join(char for char in raw if "0" <= char <= "9")

    if len(digits) != 14:
        return ValidationResult(is_valid=False, normalized=None, error="CNPJ deve ter 14 dígitos")

    if len(set(digits)) == 1:
        return ValidationResult(
            is_valid=False,
            normalized=None,
            error="CNPJ não pode ser sequência de dígitos repetidos",
        )

    first = _check_digit(digits[:12], _WEIGHTS_FIRST_DIGIT)
    second = _check_digit(digits[:13], _WEIGHTS_SECOND_DIGIT)
    if digits[12] != str(first) or digits[13] != str(second):
        return ValidationResult(
            is_valid=False, normalized=None, error="dígito verificador inválido"
        )

    normalized = f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return ValidationResult(is_valid=True, normalized=normalized, error=None)
