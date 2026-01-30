from __future__ import annotations

import pytest

from pyloto_corp.infra.institutional_context import InstitutionalContextLoader


@pytest.mark.asyncio
async def test_institutional_context_loader_reads_docs(tmp_path):
    docs_path = tmp_path / "docs"
    docs_path.mkdir()

    visao_file = docs_path / "visao_principios-e-posicionamento.md"
    visao_file.write_text("Visao Pyloto", encoding="utf-8")

    vertentes_file = docs_path / "vertentes.md"
    vertentes_file.write_text(
        "# Vertentes\n"
        "## SaaS Comunicacao\n"
        "Descricao curta da vertente\n"
        "- exemplo um\n"
        "constraint: nao vender direto\n"
        "palavra, chave\n",
        encoding="utf-8",
    )

    llm_dir = docs_path / "contexto_llm"
    llm_dir.mkdir()
    llm_file = llm_dir / "doc.md"
    llm_file.write_text(
        "## TECNOLOGIA\n"
        "### CUSTOM_SOFTWARE\n"
        "trigger: sistema, software\n"
        "response: fazemos sistemas sob medida\n"
        "constraint: nunca ignorar requisitos essenciais\n"
        "escalate: true\n"
        "### SENTINEL\n",
        encoding="utf-8",
    )

    loader = InstitutionalContextLoader(docs_path=docs_path)

    loaded = await loader.load()

    assert loaded is True
    assert loader.get_vertente("saaS comunicacao") is not None
    intent = loader.get_intent("TECNOLOGIA", "CUSTOM_SOFTWARE")
    assert intent is not None
    prompt = loader.get_prompt_context()
    assert "Contexto Institucional Pyloto" in prompt
    detected = loader.detect_intent_from_text("Preciso de um sistema novo")
    assert detected is not None
    constraints = loader.get_all_constraints()
    assert constraints
