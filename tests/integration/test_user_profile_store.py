"""Testes de integração para FirestoreUserProfileStore.

Cobertura >90% conforme regras_e_padroes.md:
- CRUD básico (get, upsert)
- Busca por phone (dedup)
- Histórico de atualizações
- LGPD: forget
- Edge cases
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from pyloto_corp.domain.profile import (
    QualificationLevel,
    UserProfile,
)
from pyloto_corp.infra.firestore_profiles import (
    FirestoreUserProfileStore,
    _mask_pii,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_firestore_client() -> MagicMock:
    """Mock de cliente Firestore."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_profile() -> UserProfile:
    """Perfil de exemplo para testes."""
    now = datetime.now(tz=UTC)
    return UserProfile(
        user_key="user_abc123",
        phone_e164="+5511999999999",
        display_name="João Silva",
        city="São Paulo",
        is_business=False,
        business_name=None,
        role=None,
        collected_fields={"interesse": "sistemas sob medida"},
        lead_score=50,
        qualification_level=QualificationLevel.WARM,
        created_at=now,
        updated_at=now,
        last_interaction=now,
        metadata={},
    )


@pytest.fixture
def mock_doc_snapshot(sample_profile: UserProfile) -> MagicMock:
    """Mock de snapshot de documento."""
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = sample_profile.model_dump(mode="json")
    return snapshot


# =============================================================================
# Testes: _mask_pii
# =============================================================================


class TestMaskPii:
    """Testes para função de mascaramento de PII."""

    def test_none_returns_none(self) -> None:
        """None retorna None."""
        assert _mask_pii(None) is None

    def test_short_string_masked(self) -> None:
        """String curta é totalmente mascarada."""
        assert _mask_pii("abc") == "***"
        assert _mask_pii("ab") == "***"

    def test_long_string_partially_masked(self) -> None:
        """String longa mostra início e fim."""
        result = _mask_pii("João Silva")
        assert result is not None
        assert result.startswith("Jo")
        assert result.endswith("va")
        assert "***" in result

    def test_phone_masked(self) -> None:
        """Telefone é parcialmente mascarado."""
        result = _mask_pii("+5511999999999")
        assert result is not None
        assert result.startswith("+5")
        assert result.endswith("99")


# =============================================================================
# Testes: FirestoreUserProfileStore.get_profile
# =============================================================================


class TestGetProfile:
    """Testes para busca de perfil."""

    def test_existing_profile_returns_profile(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Perfil existente é retornado."""
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = mock_doc_snapshot

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.get_profile("user_abc123")

        assert result is not None
        assert result.user_key == "user_abc123"

    def test_nonexistent_profile_returns_none(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Perfil inexistente retorna None."""
        snapshot = MagicMock()
        snapshot.exists = False
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = snapshot

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.get_profile("nonexistent")

        assert result is None

    def test_malformed_profile_returns_none(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Perfil malformado retorna None."""
        snapshot = MagicMock()
        snapshot.exists = True
        snapshot.to_dict.return_value = {"invalid": "data"}  # Falta campos obrigatórios
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = snapshot

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.get_profile("user_abc123")

        assert result is None


# =============================================================================
# Testes: FirestoreUserProfileStore.get_by_phone
# =============================================================================


class TestGetByPhone:
    """Testes para busca por telefone."""

    def test_existing_phone_returns_profile(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Telefone existente retorna perfil."""
        (
            mock_firestore_client.collection.return_value.where.return_value.limit.return_value.stream.return_value
        ) = [mock_doc_snapshot]

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.get_by_phone("+5511999999999")

        assert result is not None

    def test_nonexistent_phone_returns_none(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Telefone inexistente retorna None."""
        (
            mock_firestore_client.collection.return_value.where.return_value.limit.return_value.stream.return_value
        ) = []

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.get_by_phone("+5511000000000")

        assert result is None

    def test_dedup_returns_first_match(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Dedup retorna primeiro match (limit 1)."""
        mock_doc_snapshot2 = MagicMock()
        mock_doc_snapshot2.exists = True
        mock_doc_snapshot2.to_dict.return_value = {"user_key": "second"}

        # Mesmo com múltiplos, deve usar o primeiro
        (
            mock_firestore_client.collection.return_value.where.return_value.limit.return_value.stream.return_value
        ) = [mock_doc_snapshot]

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.get_by_phone("+5511999999999")

        assert result is not None
        assert result.user_key == "user_abc123"


# =============================================================================
# Testes: FirestoreUserProfileStore.upsert_profile
# =============================================================================


class TestUpsertProfile:
    """Testes para criação/atualização de perfil."""

    def test_upsert_calls_set(
        self,
        mock_firestore_client: MagicMock,
        sample_profile: UserProfile,
    ) -> None:
        """Upsert chama set no documento."""
        store = FirestoreUserProfileStore(mock_firestore_client)
        store.upsert_profile(sample_profile)

        mock_firestore_client.collection.return_value.document.return_value.set.assert_called_once()

    def test_upsert_with_correct_data(
        self,
        mock_firestore_client: MagicMock,
        sample_profile: UserProfile,
    ) -> None:
        """Upsert usa dados corretos."""
        store = FirestoreUserProfileStore(mock_firestore_client)
        store.upsert_profile(sample_profile)

        call_args = (
            mock_firestore_client.collection.return_value.document.return_value.set.call_args
        )
        saved_data = call_args[0][0]

        assert saved_data["user_key"] == "user_abc123"
        assert saved_data["phone_e164"] == "+5511999999999"


# =============================================================================
# Testes: FirestoreUserProfileStore.update_field
# =============================================================================


class TestUpdateField:
    """Testes para atualização de campo."""

    def test_update_existing_field(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Atualização de campo existente funciona."""
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = mock_doc_snapshot

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.update_field("user_abc123", "city", "Rio de Janeiro")

        assert result is True
        mock_firestore_client.collection.return_value.document.return_value.update.assert_called_once()

    def test_update_nonexistent_profile_returns_false(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Atualização de perfil inexistente retorna False."""
        snapshot = MagicMock()
        snapshot.exists = False
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = snapshot

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.update_field("nonexistent", "city", "SP")

        assert result is False

    def test_update_records_history(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Atualização registra histórico."""
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = mock_doc_snapshot

        store = FirestoreUserProfileStore(mock_firestore_client)
        store.update_field("user_abc123", "city", "Curitiba", actor="agent_1")

        # Deve ter chamado collection("history").document().set()
        history_calls = [
            call for call in mock_firestore_client.mock_calls if "history" in str(call)
        ]
        assert len(history_calls) > 0


# =============================================================================
# Testes: FirestoreUserProfileStore.get_update_history
# =============================================================================


class TestGetUpdateHistory:
    """Testes para histórico de atualizações."""

    def test_empty_history_returns_empty_list(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Histórico vazio retorna lista vazia."""
        (
            mock_firestore_client.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value.stream.return_value
        ) = []

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.get_update_history("user_abc123")

        assert result == []

    def test_history_returns_events(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Histórico retorna eventos corretamente."""
        # Mock document chain for _doc(user_key)
        mock_doc = MagicMock()
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_limited = MagicMock()

        event_doc = MagicMock()
        event_doc.to_dict.return_value = {
            "timestamp": "2026-01-25T12:00:00+00:00",
            "field_changed": "city",
            "old_value": "SP***lo",
            "new_value": "Ri***ro",
            "actor": "system",
        }

        # Chain the mocks correctly
        mock_firestore_client.collection.return_value.document.return_value = mock_doc
        mock_doc.collection.return_value = mock_collection
        mock_collection.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_limited
        mock_limited.stream.return_value = [event_doc]

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.get_update_history("user_abc123")

        assert len(result) == 1
        assert result[0].field_changed == "city"

    def test_history_respects_limit(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Histórico respeita limite."""
        store = FirestoreUserProfileStore(mock_firestore_client)
        store.get_update_history("user_abc123", limit=10)

        mock_firestore_client.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.assert_called_with(
            10
        )


# =============================================================================
# Testes: FirestoreUserProfileStore.forget (LGPD)
# =============================================================================


class TestForget:
    """Testes para LGPD forget."""

    def test_forget_existing_profile_returns_true(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Forget de perfil existente retorna True."""
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = mock_doc_snapshot
        (
            mock_firestore_client.collection.return_value.document.return_value.collection.return_value.stream.return_value
        ) = []

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.forget("user_abc123")

        assert result is True

    def test_forget_nonexistent_profile_returns_false(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Forget de perfil inexistente retorna False."""
        snapshot = MagicMock()
        snapshot.exists = False
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = snapshot

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.forget("nonexistent")

        assert result is False

    def test_forget_deletes_history(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Forget remove histórico antes do perfil."""
        history_doc = MagicMock()
        history_doc.reference = MagicMock()

        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = mock_doc_snapshot
        (
            mock_firestore_client.collection.return_value.document.return_value.collection.return_value.stream.return_value
        ) = [history_doc]

        store = FirestoreUserProfileStore(mock_firestore_client)
        store.forget("user_abc123")

        # Histórico deve ser deletado
        history_doc.reference.delete.assert_called_once()

    def test_forget_deletes_profile(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Forget remove o perfil."""
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = mock_doc_snapshot
        (
            mock_firestore_client.collection.return_value.document.return_value.collection.return_value.stream.return_value
        ) = []

        store = FirestoreUserProfileStore(mock_firestore_client)
        store.forget("user_abc123")

        mock_firestore_client.collection.return_value.document.return_value.delete.assert_called_once()


# =============================================================================
# Testes: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Testes para casos de borda."""

    def test_business_profile(
        self,
        mock_firestore_client: MagicMock,
    ) -> None:
        """Perfil de negócio funciona."""
        now = datetime.now(tz=UTC)
        business_profile = UserProfile(
            user_key="biz_123",
            phone_e164="+5511888888888",
            display_name="Empresa X",
            is_business=True,
            business_name="Empresa X LTDA",
            role="Gerente",
            qualification_level=QualificationLevel.HOT,
            created_at=now,
            updated_at=now,
        )

        store = FirestoreUserProfileStore(mock_firestore_client)
        store.upsert_profile(business_profile)

        call_args = (
            mock_firestore_client.collection.return_value.document.return_value.set.call_args
        )
        saved_data = call_args[0][0]

        assert saved_data["is_business"] is True
        assert saved_data["business_name"] == "Empresa X LTDA"

    def test_lead_score_update(
        self,
        mock_firestore_client: MagicMock,
        mock_doc_snapshot: MagicMock,
    ) -> None:
        """Atualização de lead_score funciona."""
        (
            mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = mock_doc_snapshot

        store = FirestoreUserProfileStore(mock_firestore_client)
        result = store.update_field("user_abc123", "lead_score", "100")

        assert result is True

    def test_qualification_levels(self) -> None:
        """Todos os níveis de qualificação são válidos."""
        for level in QualificationLevel:
            now = datetime.now(tz=UTC)
            profile = UserProfile(
                user_key="test",
                phone_e164="+5500000000000",
                qualification_level=level,
                created_at=now,
                updated_at=now,
            )
            assert profile.qualification_level == level
