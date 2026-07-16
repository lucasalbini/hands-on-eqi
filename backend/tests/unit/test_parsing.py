"""Testes do parsing de documentos PDF/DOCX."""

import logging
from pathlib import Path

import docx
import pytest

from app.pipeline.parsing import MIME_DOCX, MIME_PDF, ParsingError, parse_document

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_pdf_com_texto_extrai_clausulas_e_cnpj() -> None:
    text = parse_document(FIXTURES / "contrato_minimo.pdf", MIME_PDF)

    assert "DO OBJETO" in text
    assert "12.345.678/0001-90" in text


def test_docx_extrai_paragrafos_e_celulas_de_tabela() -> None:
    text = parse_document(FIXTURES / "contrato_tabela.docx", MIME_DOCX)

    assert "partes qualificadas" in text
    assert "Empresa Exemplo LTDA" in text
    assert "98.765.432/0001-10" in text


def test_pdf_escaneado_sem_camada_de_texto_levanta_parsing_error() -> None:
    with pytest.raises(ParsingError, match="OCR fora de escopo"):
        parse_document(FIXTURES / "escaneado.pdf", MIME_PDF)


def test_docx_quase_vazio_levanta_parsing_error(tmp_path: Path) -> None:
    vazio = tmp_path / "vazio.docx"
    docx.Document().save(str(vazio))

    with pytest.raises(ParsingError, match="OCR fora de escopo"):
        parse_document(vazio, MIME_DOCX)


def test_mime_type_desconhecido_levanta_parsing_error() -> None:
    with pytest.raises(ParsingError, match="não suportado"):
        parse_document(FIXTURES / "contrato_minimo.pdf", "text/plain")


def test_texto_acima_do_cap_e_truncado_com_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.pipeline.parsing"):
        text = parse_document(FIXTURES / "contrato_minimo.pdf", MIME_PDF, max_chars=100)

    assert len(text) == 100
    assert any("truncado" in record.getMessage().lower() for record in caplog.records)
