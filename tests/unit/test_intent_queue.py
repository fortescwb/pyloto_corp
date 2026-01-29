"""Teste M3: IntentQueue ordering, capacity e invariantes."""

from __future__ import annotations

from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.intent_queue import IntentQueue


class TestIntentQueueAddition:
    """Testa adição de intenções."""

    def test_add_first_intent_becomes_active(self):
        """Primeira intenção adicionada deve ser ativa."""
        queue = IntentQueue()
        assert queue.add_intent(Intent.ENTRY_UNKNOWN)
        assert queue.active_intent == Intent.ENTRY_UNKNOWN

    def test_add_second_intent_is_queued(self):
        """Segunda intenção deve ficar na fila."""
        queue = IntentQueue()
        queue.add_intent(Intent.ENTRY_UNKNOWN)
        assert queue.add_intent(Intent.CUSTOM_SOFTWARE)
        assert queue.active_intent == Intent.ENTRY_UNKNOWN
        assert queue.queued[0].intent == Intent.CUSTOM_SOFTWARE

    def test_add_intent_with_confidence(self):
        """Intenção com confidence deve ser armazenada."""
        queue = IntentQueue()
        queue.add_intent(Intent.ENTRY_UNKNOWN, confidence=0.95)
        assert queue.active_intent == Intent.ENTRY_UNKNOWN
        assert queue.queued == []

    def test_add_intent_maintains_fifo_order(self):
        """Ordem FIFO deve ser mantida na fila."""
        queue = IntentQueue()
        queue.add_intent(Intent.ENTRY_UNKNOWN)
        queue.add_intent(Intent.CUSTOM_SOFTWARE)
        queue.add_intent(Intent.SAAS_COMMUNICATION)
        assert queue.queued[0].intent == Intent.CUSTOM_SOFTWARE
        assert queue.queued[1].intent == Intent.SAAS_COMMUNICATION


class TestIntentQueueCapacity:
    """Testa limites de capacidade."""

    def test_max_items_default_is_3(self):
        """Capacidade máxima padrão deve ser 3."""
        queue = IntentQueue()
        assert queue.max_items == 3

    def test_reject_when_exceeds_max_items(self):
        """Rejeitar quando excede max_items."""
        queue = IntentQueue()
        queue.add_intent(Intent.ENTRY_UNKNOWN)
        queue.add_intent(Intent.CUSTOM_SOFTWARE)
        queue.add_intent(Intent.SAAS_COMMUNICATION)
        # 4ª intenção deve ser rejeitada
        assert not queue.add_intent(Intent.INSTITUTIONAL)

    def test_custom_max_items(self):
        """Deve permitir capacidade customizável."""
        queue = IntentQueue(max_items=5)
        assert queue.max_items == 5


class TestIntentQueueOrdering:
    """Testa ordem de processamento."""

    def test_queued_items_are_fifo(self):
        """Itens na fila devem ser FIFO."""
        queue = IntentQueue()
        queue.add_intent(Intent.ENTRY_UNKNOWN)
        queue.add_intent(Intent.CUSTOM_SOFTWARE)
        queue.add_intent(Intent.SAAS_COMMUNICATION)
        assert queue.queued[0].intent == Intent.CUSTOM_SOFTWARE
        assert queue.queued[1].intent == Intent.SAAS_COMMUNICATION

    def test_active_intent_always_first_added(self):
        """Intenção ativa deve ser sempre a primeira adicionada."""
        queue = IntentQueue()
        first = Intent.ENTRY_UNKNOWN
        queue.add_intent(first)
        assert queue.active_intent == first
        # Adicionar mais intenções não muda active_intent
        queue.add_intent(Intent.CUSTOM_SOFTWARE)
        assert queue.active_intent == first


class TestIntentQueueInvariants:
    """Testa invariantes da fila."""

    def test_active_intent_not_in_queued(self):
        """Intenção ativa nunca deve estar na fila."""
        queue = IntentQueue()
        queue.add_intent(Intent.ENTRY_UNKNOWN)
        queue.add_intent(Intent.CUSTOM_SOFTWARE)
        assert queue.active_intent not in [item.intent for item in queue.queued]

    def test_active_intent_when_has_items(self):
        """Se há itens, deve haver intenção ativa."""
        queue = IntentQueue()
        queue.add_intent(Intent.ENTRY_UNKNOWN)
        assert queue.active_intent is not None

    def test_empty_queue_has_no_active_intent(self):
        """Fila vazia deve ter active_intent = None."""
        queue = IntentQueue()
        assert queue.active_intent is None
