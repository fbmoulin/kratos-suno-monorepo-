"""Smoke tests: garantem que os módulos carregam sem erro de sintaxe/import.

Estes testes rodam sem precisar das libs pesadas (anthropic, librosa) —
só verificam que o código é sintaticamente correto e imports estão OK.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


# Módulos core que devem sempre carregar (sem deps externas pesadas)
CORE_MODULES = [
    "app.schemas.sonic_dna",
    "app.services.prompt_compressor",
]


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_core_module_imports(module_name: str):
    """Cada módulo core importa sem erros."""
    module = importlib.import_module(module_name)
    assert module is not None


def test_prompt_versions_exist():
    """Pelo menos uma versão de prompt existe no diretório esperado."""
    prompts_dir = Path(__file__).parent.parent / "app" / "prompts" / "versions"
    assert prompts_dir.exists(), f"Diretório não existe: {prompts_dir}"
    md_files = list(prompts_dir.glob("*.md"))
    assert len(md_files) >= 1, "Nenhum .md em prompts/versions/"


def test_v1_baseline_prompt_is_not_empty():
    """v1_baseline.md existe e tem conteúdo substancial."""
    path = (
        Path(__file__).parent.parent
        / "app" / "prompts" / "versions" / "v1_baseline.md"
    )
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert len(content) > 500, "v1_baseline.md parece vazio ou truncado"
    # Deve mencionar o schema SonicDNA
    assert "subject_type" in content
    assert "forbidden_terms" in content


def test_test_cases_are_valid_json():
    """Casos de teste do Prompt Lab são JSON válido e têm campos mínimos."""
    import json

    path = (
        Path(__file__).parent.parent
        / "prompt_lab" / "test_cases" / "artists.json"
    )
    assert path.exists()

    with open(path, encoding="utf-8") as f:
        cases = json.load(f)

    assert isinstance(cases, list)
    assert len(cases) >= 3

    for case in cases:
        assert "name" in case
        assert "subject" in case
