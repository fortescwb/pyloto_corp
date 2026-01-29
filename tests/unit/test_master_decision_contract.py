from __future__ import annotations

import pytest

from pyloto_corp.domain.conversation_state import ConversationState
from pyloto_corp.domain.enums import MessageType
from pyloto_corp.domain.master_decision import MasterDecisionOutput


def test_master_decision_validates_index_and_text_match():
    output = MasterDecisionOutput(
        final_state=ConversationState.AWAITING_USER,
        apply_state=True,
        selected_response_index=1,
        selected_response_text="resp2",
        message_type=MessageType.TEXT,
        overall_confidence=0.8,
        reason="ok",
        decision_trace={"responses": ["resp1", "resp2", "resp3"]},
    )
    assert output.selected_response_text == "resp2"


def test_master_decision_rejects_bad_index():
    with pytest.raises(ValueError):
        MasterDecisionOutput(
            final_state=ConversationState.AWAITING_USER,
            apply_state=True,
            selected_response_index=5,
            selected_response_text="resp2",
            message_type=MessageType.TEXT,
            overall_confidence=0.8,
            reason="bad",
            decision_trace={"responses": ["a", "b"]},
        )
