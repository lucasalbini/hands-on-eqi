"""Parsing determinístico de datas em formatos brasileiros."""

import re
from datetime import date

from app.validators.base import ValidationResult

_MIN_YEAR = 1900

_MONTHS_PT_BR: dict[str, int] = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

# dd/mm/aaaa, dd-mm-aaaa ou dd.mm.aaaa (separador consistente)
_NUMERIC_PATTERN = re.compile(r"^(\d{1,2})([/\-.])(\d{1,2})\2(\d{4})$")
# Forma cartorial: "12 de março de 2024"
_PROSE_PATTERN = re.compile(r"^(\d{1,2})\s+de\s+([a-zçã]+)\s+de\s+(\d{4})$", re.IGNORECASE)
# ISO aaaa-mm-dd (correções vindas de <input type="date"> da UI)
_ISO_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def parse_date_br(raw: str, max_year: int | None = None) -> ValidationResult:
    """Interpreta uma data brasileira (sempre dia/mês) e normaliza para ISO.

    Aceita ``dd/mm/aaaa``, ``dd-mm-aaaa``, ``dd.mm.aaaa`` e a forma cartorial
    "12 de março de 2024". ``max_year`` limita o ano aceito; se ``None``, usa
    ``date.today().year + 1`` (parâmetro existe para testabilidade).
    """
    if max_year is None:
        max_year = date.today().year + 1

    text = raw.strip()

    iso_match = _ISO_PATTERN.match(text)
    if iso_match:
        return _build_result(
            int(iso_match.group(3)), int(iso_match.group(2)), int(iso_match.group(1)), max_year
        )

    numeric_match = _NUMERIC_PATTERN.match(text)
    if numeric_match:
        day, month, year = (
            int(numeric_match.group(1)),
            int(numeric_match.group(3)),
            int(numeric_match.group(4)),
        )
        return _build_result(day, month, year, max_year)

    prose_match = _PROSE_PATTERN.match(text)
    if prose_match:
        month_name = prose_match.group(2).lower()
        month_number = _MONTHS_PT_BR.get(month_name)
        if month_number is None:
            return ValidationResult(
                is_valid=False,
                normalized=None,
                error=f"mês desconhecido: {prose_match.group(2)!r}",
            )
        return _build_result(
            int(prose_match.group(1)), month_number, int(prose_match.group(3)), max_year
        )

    return ValidationResult(
        is_valid=False,
        normalized=None,
        error="formato de data não reconhecido; use dd/mm/aaaa ou 'dd de mês de aaaa'",
    )


def _build_result(day: int, month: int, year: int, max_year: int) -> ValidationResult:
    if not _MIN_YEAR <= year <= max_year:
        return ValidationResult(
            is_valid=False,
            normalized=None,
            error=f"ano fora da faixa permitida ({_MIN_YEAR} a {max_year})",
        )

    try:
        parsed = date(year, month, day)
    except ValueError:
        return ValidationResult(
            is_valid=False, normalized=None, error="data inexistente no calendário"
        )

    return ValidationResult(is_valid=True, normalized=parsed.isoformat(), error=None)
