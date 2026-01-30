"""Testes E2E: Pipeline com 3 LLM points, ordem garantida, PII safety.

ruff: noqa: SIM117 - nested with statements intencionais para clareza de escopo dos mocks
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyloto_corp.adapters.whatsapp.message_builder import sanitize_payload
from pyloto_corp.ai.assistant_message_type import MessagePlan, MessageSafety
from pyloto_corp.ai.contracts.event_detection import EventDetectionResult
from pyloto_corp.ai.contracts.response_generation import ResponseGenerationResult
from pyloto_corp.application.pipeline_v2 import PipelineV2
from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.session.events import SessionEvent
from pyloto_corp.domain.session.states import SessionState


@pytest.fixture(autouse=True)
def enable_openai_pipeline():
    """Garante caminho LLM nos testes sem exigir chave real do OpenAI."""
    from pyloto_corp.application import pipeline_v2

    previous_flag = pipeline_v2.settings.openai_enabled
    previous_factory = pipeline_v2.get_openai_client

    pipeline_v2.settings.openai_enabled = True
    pipeline_v2.get_openai_client = lambda: MagicMock()

    yield

    pipeline_v2.get_openai_client = previous_factory
    pipeline_v2.settings.openai_enabled = previous_flag


class TestLLMPipelineOrder:
    """Testa que ordem FSM → LLM#1 → LLM#2 → LLM#3 é respeitada."""

    @pytest.fixture
    def mock_stores(self):
        """Mock stores."""
        dedupe = MagicMock()
        dedupe.mark_if_new.return_value = True
        session_store = MagicMock()
        session_store.load.return_value = None
        session_store.save = MagicMock()
        return dedupe, session_store

    @pytest.fixture
    def mock_message(self):
        """Mock de mensagem WhatsApp."""
        msg = MagicMock()
        msg.message_id = "msg_123"
        msg.chat_id = "chat_456"
        msg.sender_phone = "+5511987654321"
        msg.from_number = "+5511987654321"  # Necessário para OutboundMessageRequest
        msg.text = "Olá, o que é a Pyloto?"
        return msg

    def test_order_fsm_before_llm1(self, mock_stores, mock_message):
        """FSM deve executar antes de LLM #1."""
        dedupe, session_store = mock_stores
        pipeline = PipelineV2(dedupe, session_store)

        # Spy na ordem
        call_order = []

        with patch.object(pipeline, "_run_fsm") as mock_fsm:
            mock_fsm.side_effect = lambda s: (call_order.append("fsm"), ("INIT", "NEXT"))[1]

            with patch.object(pipeline, "_run_llm1_event_detection") as mock_llm1:
                mock_llm1.side_effect = lambda m, s: (
                    call_order.append("llm1"),
                    EventDetectionResult(
                        event=SessionEvent.USER_SENT_TEXT,
                        detected_intent=Intent.ENTRY_UNKNOWN,
                        confidence=0.9,
                        requires_followup=False,
                        rationale="Test",
                    ),
                )[1]

                with patch.object(pipeline, "_is_abuse", return_value=False):
                    with patch.object(pipeline, "_run_llm2_response_generation") as mock_llm2:
                        mock_llm2.side_effect = lambda m, llm1_result, s, ns: (
                            call_order.append("llm2"),
                            ResponseGenerationResult(
                                text_content="Bem vindo!",
                                options=[],
                                suggested_next_state=SessionState.GENERATING_RESPONSE,
                                requires_human_review=False,
                                confidence=0.85,
                                rationale="Test",
                            ),
                        )[1]

                        with patch.object(pipeline, "_run_llm3_message_selection") as mock_llm3:
                            mock_llm3.side_effect = lambda s, e, llm2_result: (
                                call_order.append("llm3"),
                                MessagePlan(
                                    kind="TEXT",
                                    reason="Test",
                                    text="Bem vindo!",
                                    safety=MessageSafety(
                                        pii_risk="low",
                                        require_handoff=False,
                                    ),
                                ),
                            )[1]

                            with patch.object(pipeline, "_build_whatsapp_payload") as mock_build:
                                mock_build.return_value = {
                                    "messaging_product": "whatsapp",
                                    "to": "+5511987654321",
                                    "type": "text",
                                    "text": {"body": "Bem vindo!"},
                                }

                                with patch.object(
                                    pipeline, "_get_outbound_client"
                                ) as mock_outbound:
                                    mock_result = MagicMock()
                                    mock_result.success = True
                                    mock_result.message_id = "wamid_test"
                                    (
                                        mock_outbound.return_value.send_message.return_value
                                    ) = mock_result

                                    pipeline._process_message(mock_message)

        # Verificar ordem
        assert call_order == ["fsm", "llm1", "llm2", "llm3"], (
            f"Ordem violada! Esperado ['fsm', 'llm1', 'llm2', 'llm3'], recebido {call_order}"
        )

    def test_llm3_requires_llm2_result(self, mock_stores, mock_message):
        """LLM #3 recebe ResponseGenerationResult como argumento obrigatório."""
        dedupe, session_store = mock_stores
        pipeline = PipelineV2(dedupe, session_store)

        # Mock de LLM #2 com resultado específico
        llm2_result = ResponseGenerationResult(
            text_content="Olá! A Pyloto é uma plataforma...",
            options=[{"id": "opt1", "title": "Saiba mais"}],
            suggested_next_state=SessionState.GENERATING_RESPONSE,
            requires_human_review=False,
            confidence=0.92,
            rationale="Generated by LLM #2",
        )

        with patch.object(pipeline, "_is_abuse", return_value=False):
            with patch.object(pipeline, "_run_fsm", return_value=("INIT", "NEXT")):
                with patch.object(pipeline, "_run_llm1_event_detection") as mock_llm1:
                    mock_llm1.return_value = EventDetectionResult(
                        event=SessionEvent.USER_SENT_TEXT,
                        detected_intent=Intent.CUSTOM_SOFTWARE,
                        confidence=0.95,
                        requires_followup=False,
                        rationale="User asking about Pyloto",
                    )

                    with patch.object(pipeline, "_run_llm2_response_generation") as mock_llm2:
                        mock_llm2.return_value = llm2_result

                        # Capturar argumentos passados para LLM #3
                        with patch.object(pipeline, "_run_llm3_message_selection") as mock_llm3:
                            mock_llm3.return_value = MessagePlan(
                                kind="TEXT",
                                reason="Simple text",
                                text=llm2_result.text_content,
                                safety=MessageSafety(
                                    pii_risk="low",
                                    require_handoff=False,
                                ),
                            )

                            with patch.object(pipeline, "_build_whatsapp_payload") as mock_build:
                                mock_build.return_value = {
                                    "messaging_product": "whatsapp",
                                    "to": "+5511987654321",
                                    "type": "text",
                                    "text": {"body": llm2_result.text_content},
                                }

                                with patch.object(
                                    pipeline, "_get_outbound_client"
                                ) as mock_outbound:
                                    mock_result = MagicMock()
                                    mock_result.success = True
                                    mock_result.message_id = "wamid_test"
                                    (
                                        mock_outbound.return_value.send_message.return_value
                                    ) = mock_result

                                    pipeline._process_message(mock_message)

                                    # Verificar que LLM #3 foi chamado com argumento correto
                                    mock_llm3.assert_called_once()
                                    call_args = mock_llm3.call_args
                                    # Terceiro argumento deve ser llm2_result
                                    assert call_args[0][2] == llm2_result


class TestPIISafety:
    """Testa que PII é mascarado em logs."""

    def test_sanitize_payload_phone(self):
        """Telefone deve ser mascarado (últimos 4 dígitos apenas)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511987654321",
            "type": "text",
            "text": {"body": "Olá!"},
        }

        sanitized = sanitize_payload(payload)

        # Telefone deve estar mascarado
        assert sanitized["to"].startswith("***")
        assert sanitized["to"].endswith("4321")
        assert "55119876" not in sanitized["to"]

    def test_sanitize_payload_email_in_text(self):
        """Email em texto deve ser mascarado."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511987654321",
            "type": "text",
            "text": {"body": "Contato: user@example.com"},
        }

        sanitized = sanitize_payload(payload)

        # Email deve estar mascarado
        assert "[EMAIL]" in sanitized["text"]["body"]
        assert "user@example.com" not in sanitized["text"]["body"]

    def test_sanitize_payload_cpf_in_text(self):
        """CPF em texto deve ser mascarado."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511987654321",
            "type": "text",
            "text": {"body": "CPF: 123.456.789-10"},
        }

        sanitized = sanitize_payload(payload)

        # CPF deve estar mascarado
        assert "[DOCUMENT]" in sanitized["text"]["body"]
        assert "123.456.789-10" not in sanitized["text"]["body"]

    def test_sanitize_payload_preserves_structure(self):
        """Estrutura do payload deve ser mantida após sanitização."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511987654321",
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Escolha uma opção"},
                "action": {"buttons": [{"type": "reply", "reply": {"id": "1", "title": "OK"}}]},
            },
        }

        sanitized = sanitize_payload(payload)

        # Estrutura deve estar intacta
        assert sanitized["messaging_product"] == "whatsapp"
        assert sanitized["type"] == "interactive"
        assert sanitized["interactive"]["type"] == "button"
        assert len(sanitized["interactive"]["action"]["buttons"]) == 1


class TestFallbackSafety:
    """Testa que fallbacks são determinísticos (nunca crash)."""

    @pytest.fixture
    def mock_stores(self):
        dedupe = MagicMock()
        dedupe.mark_if_new.return_value = True
        session_store = MagicMock()
        session_store.load.return_value = None
        session_store.save = MagicMock()
        return dedupe, session_store

    @pytest.fixture
    def mock_message(self):
        msg = MagicMock()
        msg.message_id = "msg_999"
        msg.chat_id = "chat_888"
        msg.sender_phone = "+5511987654321"
        msg.text = "Test message"
        return msg

    def test_fallback_on_llm1_timeout(self, mock_stores, mock_message):
        """LLM #1 timeout deve usar fallback (não crash)."""
        dedupe, session_store = mock_stores
        pipeline = PipelineV2(dedupe, session_store)

        with patch.object(pipeline, "_is_abuse", return_value=False):
            with patch.object(pipeline, "_run_fsm", return_value=("INIT", "NEXT")):
                with patch.object(pipeline, "_run_llm1_event_detection") as mock_llm1:
                    # Simular timeout
                    mock_llm1.side_effect = TimeoutError("API timeout")

                    # Execução não deve crash
                    result = pipeline._process_message(mock_message)

                    # Resultado deve ser válido (fallback)
                    assert result is False or result is True

    def test_fallback_on_payload_build_error(self, mock_stores, mock_message):
        """Erro ao construir payload deve usar fallback."""
        dedupe, session_store = mock_stores
        pipeline = PipelineV2(dedupe, session_store)

        with patch.object(pipeline, "_is_abuse", return_value=False):
            with patch.object(pipeline, "_run_fsm", return_value=("INIT", "NEXT")):
                with patch.object(pipeline, "_run_llm1_event_detection") as mock_llm1:
                    mock_llm1.return_value = EventDetectionResult(
                        event=SessionEvent.USER_SENT_TEXT,
                        detected_intent=Intent.ENTRY_UNKNOWN,
                        confidence=0.9,
                        requires_followup=False,
                        rationale="Test",
                    )

                    with patch.object(pipeline, "_run_llm2_response_generation") as mock_llm2:
                        mock_llm2.return_value = ResponseGenerationResult(
                            text_content="Test",
                            options=[],
                            suggested_next_state=None,
                            requires_human_review=False,
                            confidence=0.8,
                            rationale="Test",
                        )

                        with patch.object(pipeline, "_run_llm3_message_selection") as mock_llm3:
                            mock_llm3.return_value = MessagePlan(
                                kind="TEXT",
                                reason="Test",
                                text="Test",
                                safety=MessageSafety(
                                    pii_risk="low",
                                    require_handoff=False,
                                ),
                            )

                            with patch.object(pipeline, "_build_whatsapp_payload") as mock_build:
                                # Simular erro na construção
                                mock_build.side_effect = ValueError("Invalid payload")

                                # Não deve crash
                                result = pipeline._process_message(mock_message)

                                assert result is False or result is True
