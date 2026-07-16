"""Testes do validador de UF."""

import pytest

from app.validators import validate_uf

ALL_UFS = [
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
]


class TestUfValid:
    @pytest.mark.parametrize("uf", ALL_UFS)
    def test_each_of_the_27_ufs_is_valid(self, uf: str) -> None:
        result = validate_uf(uf)

        assert result.is_valid
        assert result.normalized == uf

    def test_lowercase_uf_with_surrounding_spaces_is_normalized_to_upper(self) -> None:
        result = validate_uf("  sp  ")

        assert result.is_valid
        assert result.normalized == "SP"


class TestUfInvalid:
    def test_nonexistent_two_letter_code_is_invalid(self) -> None:
        result = validate_uf("XX")

        assert not result.is_valid
        assert result.error is not None

    def test_full_state_name_is_invalid(self) -> None:
        result = validate_uf("São Paulo")

        assert not result.is_valid

    def test_empty_string_is_invalid(self) -> None:
        result = validate_uf("")

        assert not result.is_valid
        assert result.error == "UF vazia"

    def test_whitespace_only_string_is_invalid(self) -> None:
        result = validate_uf("   ")

        assert not result.is_valid
        assert result.error == "UF vazia"

    def test_invalid_uf_has_no_normalized_value(self) -> None:
        result = validate_uf("XX")

        assert result.normalized is None
