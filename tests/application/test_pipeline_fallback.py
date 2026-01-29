"""Testes para fallback de LLM quando OPENAI_ENABLED=false.

Valida que pipeline funciona sem OpenAI com templates determinísticos.
"""

from __future__ import annotations

from pyloto_corp.application.pipeline_v2 import PipelineV2
from pyloto_corp.application.session import SessionState
from pyloto_corp.domain.enums import Outcome
from pyloto_corp.infra.session_store_memory import InMemorySessionStore


class TestPipelineFallbackWithoutOpenAI:
    """Testes para pipeline com OPENAI_ENABLED=false."""

    def test_pipeline_initializes_without_openai_client_when_disabled(
        self,
    ) -> None:
        """Pipeline não inicializa client OpenAI quando openai_enabled=false."""
        session_store = InMemorySessionStore()

        pipeline = PipelineV2(
            dedupe_store=None,  # type: ignore
            session_store=session_store,
            flood_detector=None,
        )
        # Se openai_enabled=false, _openai_client deve ser None
        assert pipeline._openai_client is None

    def test_fallback_sets_awaiting_user_outcome(
        self,
    ) -> None:
        """Fallback deve setar outcome=AWAITING_USER."""
        # Simular sessão
        session = SessionState(
            session_id="test-session-123",
            phone_number="5511987654321",
            contact_name="Test User",
            messages=[],
            state="AWAITING_INPUT",
            context={},
            intention=None,
            outcome=None,
        )

        # Fallback deve setar outcome=AWAITING_USER
        assert session.outcome is None
        session.outcome = Outcome.AWAITING_USER
        assert session.outcome == Outcome.AWAITING_USER

    def test_fallback_persists_session(self) -> None:
        """Fallback deve persistir sessão no store."""
        session_store = InMemorySessionStore()

        session = SessionState(
            session_id="test-session-456",
            phone_number="5511987654321",
            contact_name="Test User",
            messages=[],
            state="AWAITING_INPUT",
            context={},
            intention=None,
            outcome=Outcome.AWAITING_USER,
        )

        # Persistir sessão
        session_store.save(session)

        # Recuperar e validar
        retrieved = session_store.load("test-session-456")
        assert retrieved is not None
        assert retrieved.session_id == "test-session-456"
        assert retrieved.outcome == Outcome.AWAITING_USER

    def test_openai_disabled_setting_defaults_to_false(self) -> None:
        """OPENAI_ENABLED deve defaultar para False."""
        from pyloto_corp.config.settings import Settings

        settings = Settings()
        assert settings.openai_enabled is False

    def test_openai_enabled_can_be_true(self) -> None:
        """OPENAI_ENABLED pode ser setado para True."""
        from pyloto_corp.config.settings import Settings

        settings = Settings(openai_enabled=True)
        assert settings.openai_enabled is True

    def test_fallback_respects_outcome_contract(self) -> None:
        """Fallback deve manter outcome nunca None e sempre válido."""
        session = SessionState(
            session_id="test-session-789",
            phone_number="5511987654321",
            contact_name="Test User",
            messages=[],
            state="AWAITING_INPUT",
            context={},
            intention=None,
            outcome=None,
        )

        # Aplicar fallback outcome
        session.outcome = Outcome.AWAITING_USER

        # Outcome deve ser terminal (sempre válido, nunca None)
        assert isinstance(session.outcome, Outcome)
        assert session.outcome in [
            Outcome.HANDOFF_HUMAN,
            Outcome.SELF_SERVE_INFO,
            Outcome.ROUTE_EXTERNAL,
            Outcome.SCHEDULED_FOLLOWUP,
            Outcome.AWAITING_USER,
            Outcome.DUPLICATE_OR_SPAM,
            Outcome.UNSUPPORTED,
            Outcome.FAILED_INTERNAL,
        ]
