"""Testes para FSM state machine."""

from pyloto_corp.domain.fsm_states import (
    ConversationState,
    FSMStateMachine,
)


class TestFSMStateMachine:
    """Testes da máquina de estados."""

    def test_init_starts_in_init_state(self) -> None:
        """FSM deve iniciar em INIT."""
        fsm = FSMStateMachine()
        assert fsm.current_state == ConversationState.INIT

    def test_valid_transition_init_to_identifying(self) -> None:
        """Transição válida de INIT para IDENTIFYING."""
        fsm = FSMStateMachine()
        result = fsm.transition(
            ConversationState.IDENTIFYING,
            trigger="user_starts_conversation",
        )
        assert result is True
        assert fsm.current_state == ConversationState.IDENTIFYING

    def test_invalid_transition_rejected(self) -> None:
        """Transição inválida deve ser rejeitada."""
        fsm = FSMStateMachine()
        result = fsm.transition(
            ConversationState.GENERATING_RESPONSE,
            trigger="invalid_transition",
        )
        assert result is False
        assert fsm.current_state == ConversationState.INIT

    def test_cannot_transition_from_terminal_state(self) -> None:
        """Não deve transicionar de estado terminal."""
        fsm = FSMStateMachine()
        # Transicionar para COMPLETED via caminho válido
        fsm.transition(ConversationState.IDENTIFYING, trigger="start")
        fsm.transition(ConversationState.UNDERSTANDING_INTENT, trigger="next")
        fsm.transition(ConversationState.PROCESSING, trigger="processing")
        fsm.transition(ConversationState.GENERATING_RESPONSE, trigger="gen")
        fsm.transition(ConversationState.SELECTING_MESSAGE_TYPE, trigger="select")
        fsm.transition(ConversationState.COMPLETED, trigger="complete")

        # Tentar transicionar de COMPLETED (terminal) - deve falhar
        result = fsm.transition(
            ConversationState.IDENTIFYING,
            trigger="attempt_from_terminal",
        )
        assert result is False

    def test_history_tracked(self) -> None:
        """Histórico de transições deve ser rastreado."""
        fsm = FSMStateMachine()
        fsm.transition(ConversationState.IDENTIFYING, trigger="start")
        fsm.transition(ConversationState.UNDERSTANDING_INTENT, trigger="next")

        history = fsm.get_history()
        assert len(history) == 2
        assert history[0].from_state == ConversationState.INIT
        assert history[0].to_state == ConversationState.IDENTIFYING
        assert history[1].from_state == ConversationState.IDENTIFYING
        assert history[1].to_state == ConversationState.UNDERSTANDING_INTENT

    def test_transition_with_metadata(self) -> None:
        """Metadados devem ser salvos na transição."""
        fsm = FSMStateMachine()
        metadata = {"user_id": "123", "reason": "detected_intent"}
        fsm.transition(
            ConversationState.IDENTIFYING,
            trigger="start",
            metadata=metadata,
        )

        history = fsm.get_history()
        assert history[0].metadata == metadata

    def test_transition_confidence(self) -> None:
        """Confidence score deve ser salvo."""
        fsm = FSMStateMachine()
        fsm.transition(
            ConversationState.IDENTIFYING,
            trigger="start",
            confidence=0.75,
        )

        history = fsm.get_history()
        assert history[0].confidence == 0.75

    def test_state_summary(self) -> None:
        """Resumo de estado deve conter informações corretas."""
        fsm = FSMStateMachine()
        fsm.transition(ConversationState.IDENTIFYING, trigger="start")

        summary = fsm.get_state_summary()
        assert summary["current_state"] == ConversationState.IDENTIFYING
        assert summary["transition_count"] == 1
        assert summary["is_terminal"] is False
        assert summary["history_length"] == 1

    def test_reset_clears_state(self) -> None:
        """Reset deve limpar estado."""
        fsm = FSMStateMachine()
        fsm.transition(ConversationState.IDENTIFYING, trigger="start")
        fsm.transition(ConversationState.UNDERSTANDING_INTENT, trigger="next")

        fsm.reset()

        assert fsm.current_state == ConversationState.INIT
        assert len(fsm.get_history()) == 0
        assert fsm.transition_count == 0

    def test_spam_state_terminal(self) -> None:
        """SPAM é estado terminal."""
        fsm = FSMStateMachine()
        fsm.transition(ConversationState.SPAM, trigger="spam_detected")
        result = fsm.transition(ConversationState.AWAITING_USER, trigger="continue")
        assert result is False

    def test_complex_flow(self) -> None:
        """Fluxo complexo com múltiplas transições."""
        fsm = FSMStateMachine()

        # Flow: INIT -> IDENTIFYING -> UNDERSTANDING_INTENT -> PROCESSING
        # -> GENERATING_RESPONSE -> SELECTING_MESSAGE_TYPE -> COMPLETED
        assert fsm.transition(ConversationState.IDENTIFYING, trigger="start")
        assert fsm.transition(
            ConversationState.UNDERSTANDING_INTENT, trigger="intent_detected"
        )
        assert fsm.transition(ConversationState.PROCESSING, trigger="processing")
        assert fsm.transition(
            ConversationState.GENERATING_RESPONSE, trigger="generating"
        )
        assert fsm.transition(
            ConversationState.SELECTING_MESSAGE_TYPE, trigger="selecting"
        )
        assert fsm.transition(ConversationState.COMPLETED, trigger="completed")

        assert fsm.current_state == ConversationState.COMPLETED
        assert fsm.transition_count == 6
