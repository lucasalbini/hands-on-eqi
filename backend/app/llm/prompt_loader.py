"""Loader de prompts versionados.

Formato do arquivo ``app/llm/prompts/{version}.md``: seção SYSTEM seguida da
seção USER, separadas por uma linha contendo exatamente ``---USER---``.
A versão retornada é o nome do arquivo resolvido (sem extensão).
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_DELIMITER = "\n---USER---\n"


def load_prompt(name: str) -> tuple[str, str, str]:
    """Carrega o prompt ``name`` e retorna ``(system, user_template, version)``."""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        available = sorted(p.stem for p in _PROMPTS_DIR.glob("*.md"))
        raise FileNotFoundError(
            f"Prompt {name!r} não encontrado em {_PROMPTS_DIR}. Disponíveis: {available}"
        )
    text = path.read_text(encoding="utf-8")
    if _DELIMITER not in text:
        raise ValueError(f"Prompt {name!r} sem delimitador '---USER---' entre SYSTEM e USER")
    system, user_template = text.split(_DELIMITER, 1)
    return system.strip(), user_template.strip(), path.stem
