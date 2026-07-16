"""Testes do validador de CNPJ."""

import pytest

from app.validators import validate_cnpj


class TestCnpjValid:
    def test_cnpj_without_formatting_is_valid(self) -> None:
        result = validate_cnpj("11222333000181")

        assert result.is_valid

    def test_cnpj_with_standard_formatting_is_valid(self) -> None:
        result = validate_cnpj("11.222.333/0001-81")

        assert result.is_valid

    def test_valid_cnpj_is_normalized_to_standard_format(self) -> None:
        result = validate_cnpj("11222333000181")

        assert result.normalized == "11.222.333/0001-81"

    def test_valid_cnpj_has_no_error(self) -> None:
        result = validate_cnpj("11222333000181")

        assert result.error is None

    def test_cnpj_starting_with_zeros_is_not_treated_as_repeated_sequence(self) -> None:
        # Banco do Brasil: começa com muitos zeros mas não é sequência repetida completa.
        result = validate_cnpj("00000000000191")

        assert result.is_valid
        assert result.normalized == "00.000.000/0001-91"


class TestCnpjInvalid:
    def test_cnpj_with_wrong_check_digit_is_invalid(self) -> None:
        result = validate_cnpj("11222333000180")

        assert not result.is_valid
        assert result.error == "dígito verificador inválido"

    def test_cnpj_with_wrong_first_check_digit_is_invalid(self) -> None:
        result = validate_cnpj("11222333000171")

        assert not result.is_valid
        assert result.error == "dígito verificador inválido"

    def test_cnpj_with_fewer_than_14_digits_is_invalid(self) -> None:
        result = validate_cnpj("1122233300018")

        assert not result.is_valid
        assert result.error == "CNPJ deve ter 14 dígitos"

    def test_cnpj_with_more_than_14_digits_is_invalid(self) -> None:
        result = validate_cnpj("112223330001811")

        assert not result.is_valid
        assert result.error == "CNPJ deve ter 14 dígitos"

    @pytest.mark.parametrize("digit", [str(d) for d in range(10)])
    def test_cnpj_with_all_repeated_digits_is_invalid(self, digit: str) -> None:
        result = validate_cnpj(digit * 14)

        assert not result.is_valid
        assert result.error == "CNPJ não pode ser sequência de dígitos repetidos"

    def test_cnpj_with_letter_in_place_of_digit_is_invalid(self) -> None:
        # Letras são descartadas, sobrando menos de 14 dígitos.
        result = validate_cnpj("11.222.333/0001-8A")

        assert not result.is_valid
        assert result.error == "CNPJ deve ter 14 dígitos"

    def test_non_digit_characters_are_stripped_before_validation(self) -> None:
        result = validate_cnpj("cnpj: 11.222.333/0001-81 (matriz)")

        assert result.is_valid
        assert result.normalized == "11.222.333/0001-81"

    def test_empty_string_is_invalid(self) -> None:
        result = validate_cnpj("")

        assert not result.is_valid
        assert result.error == "CNPJ deve ter 14 dígitos"

    def test_invalid_cnpj_has_no_normalized_value(self) -> None:
        result = validate_cnpj("11222333000180")

        assert result.normalized is None
