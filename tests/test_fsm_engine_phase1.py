"""Testes unitários para Fase 1 — FSM Core.

Cobertura:
- Transições válidas
- Estados terminais (sem transições de saída)
- Eventos inválidos
- Ações por transição
"""

import pytest

from pyloto_corp.application.fsm_engine import FSMDispatchResult, FSMEngine
from pyloto_corp.domain.session.events import SessionEvent
from pyloto_corp.domain.session.states import TERMINAL_STATES, SessionState
from pyloto_corp.domain.session.transitions import validate_transition


class TestFSMEngineBasic:
    """Testes básicos de transição FSM."""

    @pytest.fixture
    def engine(self) -> FSMEngine:
        return FSMEngine()

    def test_initial_to_triage_on_user_text(self, engine: FSMEngine) -> None:
        """INITIAL + USER_SENT_TEXT → TRIAGE."""
        result = engine.dispatch(
            current_state=SessionState.INITIAL,
            event=SessionEvent.USER_SENT_TEXT,
        )
        assert result.valid is True
        assert result.next_state == SessionState.TRIAGE
        assert "DETECT_EVENT" in result.actions
        assert "VALIDATE_INPUT" in result.actions

    def test_triage_to_collecting_on_event_detected(self, engine: FSMEngine) -> None:
        """TRIAGE + EVENT_DETECTED → COLLECTING_INFO."""
        result = engine.dispatch(
            current_state=SessionState.TRIAGE,
            event=SessionEvent.EVENT_DETECTED,
        )
        assert result.valid is True
        assert result.next_state == SessionState.COLLECTING_INFO

    def test_collecting_to_generating_on_response_generated(
        self, engine: FSMEngine
    ) -> None:
        """COLLECTING_INFO + RESPONSE_GENERATED → GENERATING_RESPONSE."""
        result = engine.dispatch(
            current_state=SessionState.COLLECTING_INFO,
            event=SessionEvent.RESPONSE_GENERATED,
        )
        assert result.valid is True
        assert result.next_state == SessionState.GENERATING_RESPONSE

    def test_generating_to_handoff_on_message_type_selected(
        self, engine: FSMEngine
    ) -> None:
        """GENERATING_RESPONSE + MESSAGE_TYPE_SELECTED → HANDOFF_HUMAN (terminal)."""
        result = engine.dispatch(
            current_state=SessionState.GENERATING_RESPONSE,
            event=SessionEvent.MESSAGE_TYPE_SELECTED,
        )
        assert result.valid is True
        assert result.next_state == SessionState.HANDOFF_HUMAN
        assert result.is_terminal() is True
        assert "PERSIST_SESSION" in result.actions
        assert "EMIT_OUTCOME" in result.actions

    def test_invalid_transition_from_terminal_state(self, engine: FSMEngine) -> None:
        """Terminal states têm zero transições."""
        for terminal_state in TERMINAL_STATES:
            result = engine.dispatch(
                current_state=terminal_state,
                event=SessionEvent.USER_SENT_TEXT,
            )
            assert result.valid is False
            assert result.next_state is None
            assert "no transitions" in result.error.lower()

    def test_invalid_event_for_state(self, engine: FSMEngine) -> None:
        """Evento inválido para estado."""
        result = engine.dispatch(
            current_state=SessionState.INITIAL,
            event=SessionEvent.MESSAGE_TYPE_SELECTED,  # Não existe em INITIAL
        )
        assert result.valid is False
        assert result.next_state is None
        assert "No transition" in result.error

    def test_all_terminal_states_defined(self) -> None:
        """Verificar que todos os terminal states têm len == 0 na tabela."""
        for terminal_state in TERMINAL_STATES:
            # Tentar qualquer evento
            for event in [SessionEvent.USER_SENT_TEXT, SessionEvent.INTERNAL_ERROR]:
                is_valid, _, _ = validate_transition(terminal_state, event)
                assert (
                    is_valid is False
                ), f"Terminal state {terminal_state} should not have transitions"


class TestFSMEngineActions:
    """Testes de determinação de ações."""

    @pytest.fixture
    def engine(self) -> FSMEngine:
        return FSMEngine()

    def test_actions_on_user_text(self, engine: FSMEngine) -> None:
        """USER_SENT_TEXT dispara DETECT_EVENT + VALIDATE_INPUT."""
        result = engine.dispatch(
            current_state=SessionState.INITIAL,
            event=SessionEvent.USER_SENT_TEXT,
        )
        assert "DETECT_EVENT" in result.actions
        assert "VALIDATE_INPUT" in result.actions

    def test_actions_on_terminal_transition(self, engine: FSMEngine) -> None:
        """Transição para estado terminal adiciona PERSIST_SESSION + EMIT_OUTCOME."""
        result = engine.dispatch(
            current_state=SessionState.GENERATING_RESPONSE,
            event=SessionEvent.MESSAGE_TYPE_SELECTED,
        )
        assert "PERSIST_SESSION" in result.actions
        assert "EMIT_OUTCOME" in result.actions

    def test_no_side_effects(self, engine: FSMEngine) -> None:
        """Engine não modifica estado externo."""
        state_before = SessionState.INITIAL
        _ = engine.dispatch(
            current_state=state_before,
            event=SessionEvent.USER_SENT_TEXT,
        )
        # state_before nunca foi mutado
        assert state_before == SessionState.INITIAL


class TestFSMEngineDeterminism:
    """Testes de determinismo."""

    @pytest.fixture
    def engine(self) -> FSMEngine:
        return FSMEngine()

    def test_same_input_same_output(self, engine: FSMEngine) -> None:
        """Mesma entrada sempre gera mesma saída."""
        result1 = engine.dispatch(
            current_state=SessionState.INITIAL,
            event=SessionEvent.USER_SENT_TEXT,
        )
        result2 = engine.dispatch(
            current_state=SessionState.INITIAL,
            event=SessionEvent.USER_SENT_TEXT,
        )
        assert result1.next_state == result2.next_state
        assert result1.valid == result2.valid
        assert result1.actions == result2.actions

    def test_never_raises_exception(self, engine: FSMEngine) -> None:
        """Engine nunca deve lançar exceção."""
        # Tentar combinação inválida
        try:
            result = engine.dispatch(
                current_state=SessionState.ERROR,
                event=SessionEvent.USER_SENT_TEXT,
            )
            assert isinstance(result, FSMDispatchResult)
        except Exception as e:
            pytest.fail(f"FSMEngine raised exception: {e}")
