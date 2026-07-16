"""Testes do parser de datas brasileiras."""

from datetime import date

import pytest

from app.validators import parse_date_br


class TestDateFormats:
    def test_date_with_slash_separator_is_parsed(self) -> None:
        result = parse_date_br("12/03/2024")

        assert result.is_valid
        assert result.normalized == "2024-03-12"

    def test_date_with_dash_separator_is_parsed(self) -> None:
        result = parse_date_br("12-03-2024")

        assert result.is_valid
        assert result.normalized == "2024-03-12"

    def test_date_with_dot_separator_is_parsed(self) -> None:
        result = parse_date_br("12.03.2024")

        assert result.is_valid
        assert result.normalized == "2024-03-12"

    def test_prose_date_with_lowercase_month_is_parsed(self) -> None:
        result = parse_date_br("12 de março de 2024")

        assert result.is_valid
        assert result.normalized == "2024-03-12"

    def test_prose_date_with_uppercase_month_is_parsed(self) -> None:
        result = parse_date_br("12 DE MARÇO DE 2024")

        assert result.is_valid
        assert result.normalized == "2024-03-12"

    @pytest.mark.parametrize(
        ("month_name", "month_number"),
        [
            ("janeiro", 1),
            ("fevereiro", 2),
            ("março", 3),
            ("abril", 4),
            ("maio", 5),
            ("junho", 6),
            ("julho", 7),
            ("agosto", 8),
            ("setembro", 9),
            ("outubro", 10),
            ("novembro", 11),
            ("dezembro", 12),
        ],
    )
    def test_each_month_name_maps_to_its_number(self, month_name: str, month_number: int) -> None:
        result = parse_date_br(f"1 de {month_name} de 2024")

        assert result.normalized == f"2024-{month_number:02d}-01"

    def test_day_and_month_with_single_digit_are_parsed(self) -> None:
        result = parse_date_br("5/3/2024")

        assert result.is_valid
        assert result.normalized == "2024-03-05"


class TestDayMonthInterpretation:
    def test_ambiguous_date_is_interpreted_as_day_first(self) -> None:
        # 11/11/2025 é 11 de novembro, nunca mês/dia.
        result = parse_date_br("11/11/2025")

        assert result.normalized == "2025-11-11"

    def test_day_greater_than_12_confirms_day_first_interpretation(self) -> None:
        result = parse_date_br("25/03/2024")

        assert result.normalized == "2024-03-25"


class TestDateInvalid:
    def test_nonexistent_calendar_date_is_rejected(self) -> None:
        result = parse_date_br("31/02/2024")

        assert not result.is_valid
        assert result.error == "data inexistente no calendário"

    def test_year_before_1900_is_rejected(self) -> None:
        result = parse_date_br("01/01/1899", max_year=2027)

        assert not result.is_valid
        assert result.error is not None

    def test_year_beyond_max_year_is_rejected(self) -> None:
        result = parse_date_br("01/01/2030", max_year=2027)

        assert not result.is_valid

    def test_year_equal_to_max_year_is_accepted(self) -> None:
        result = parse_date_br("01/01/2027", max_year=2027)

        assert result.is_valid

    def test_default_max_year_is_next_year(self) -> None:
        next_year = date.today().year + 1

        assert parse_date_br(f"01/01/{next_year}").is_valid
        assert not parse_date_br(f"01/01/{next_year + 1}").is_valid

    def test_unrecognizable_format_is_rejected(self) -> None:
        result = parse_date_br("2024-03-12T00:00:00")

        assert not result.is_valid
        assert result.error is not None

    def test_mixed_separators_are_rejected(self) -> None:
        result = parse_date_br("12/03-2024")

        assert not result.is_valid

    def test_unknown_month_name_is_rejected(self) -> None:
        result = parse_date_br("12 de framboesa de 2024")

        assert not result.is_valid

    def test_empty_string_is_rejected(self) -> None:
        result = parse_date_br("")

        assert not result.is_valid

    def test_invalid_date_has_no_normalized_value(self) -> None:
        result = parse_date_br("31/02/2024")

        assert result.normalized is None
