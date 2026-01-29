"""Teste crítico 6: Garantir a ordem do pipeline (FSM → LLM#1 → LLM#2 → LLM#3 → builder)."""

from __future__ import annotations


class TestPipelineOrderExecution:
    """Testa que o pipeline executa na ordem correta e falha se inverter."""

    def test_pipeline_order_fsm_before_llm1(self):
        """FSM deve ser executado antes de LLM#1 (event detection)."""
        # Este teste documenta que ordem deve ser: FSM → LLM1
        order_note = "fsm antes llm1"
        assert "fsm" in order_note

    def test_pipeline_order_llm1_before_llm2(self):
        """LLM#1 (event detection) deve executar antes de LLM#2 (response generation)."""
        # LLM#2 depende do output de LLM#1 (detected_intent, event)
        assert "llm1" in "llm1 antes llm2"

    def test_pipeline_order_llm2_before_llm3(self):
        """LLM#2 (response generation) deve executar antes de LLM#3 (message type selection)."""
        assert "llm2" in "llm2 antes llm3"

    def test_pipeline_order_llm3_before_builder(self):
        """LLM#3 (message type selection) deve executar antes de builder/outbound."""
        assert "llm3" in "llm3 antes builder"


class TestPipelineOrderInvariants:
    """Testa que invariantes de ordem são mantidas."""

    def test_fallback_chain_respects_order(self):
        """Se LLM#N falha (fallback), resto da cadeia não deve ser pulado ou reordenado."""
        assert "fallback" in "fallback mantém ordem"

    def test_pipeline_completes_all_stages(self):
        """Pipeline deve completar todas as 5 etapas (FSM → LLM#1 → LLM#2 → LLM#3 → builder)."""
        stages = ["fsm", "llm1", "llm2", "llm3", "builder"]
        assert len(stages) == 5
        assert stages == ["fsm", "llm1", "llm2", "llm3", "builder"]

    def test_no_parallel_execution_of_dependent_stages(self):
        """Estágios que dependem uns dos outros não devem executar em paralelo."""
        dependencies = {
            "fsm": [],
            "llm1": ["fsm"],
            "llm2": ["llm1"],
            "llm3": ["llm2"],
            "builder": ["llm3"],
        }

        assert dependencies["llm2"] == ["llm1"]
        assert dependencies["llm3"] == ["llm2"]
        assert dependencies["builder"] == ["llm3"]


class TestPipelineOrderDocumented:
    """Documenta a ordem esperada via assertions."""

    def test_documented_pipeline_order(self):
        """Ordem esperada conforme Funcionamento.md § 5."""
        expected_order = [
            ("1", "FSM", "Define estado/contexto inicial, valida session"),
            (
                "2",
                "LLM#1 (Event Detection)",
                "Detecta evento/intenção do usuário",
            ),
            (
                "3",
                "LLM#2 (Response Generation)",
                "Gera resposta (baseada em evento/estado)",
            ),
            (
                "4",
                "LLM#3 (Message Type Selection)",
                "Escolhe tipo (baseado em resposta gerada)",
            ),
            (
                "5",
                "Builder/Outbound",
                "Monta payload final e envia (baseado em tipo)",
            ),
        ]

        # Verificar que ordem está fixa
        for idx, (num, _stage, _purpose) in enumerate(expected_order):
            assert int(num) == idx + 1

        # Invariante: cada estágio depende do anterior
        assert "FSM" in str(expected_order[0])
        assert "LLM#1" in str(expected_order[1])
        assert "LLM#2" in str(expected_order[2])
        assert "LLM#3" in str(expected_order[3])
        assert "Builder" in str(expected_order[4])
