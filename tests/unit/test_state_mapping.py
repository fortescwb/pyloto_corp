from __future__ import annotations

from pyloto_corp.domain.conversation_state import ConversationState as LLMConv
from pyloto_corp.domain.fsm.state_mapping import map_fsm_to_conversation_state
from pyloto_corp.domain.fsm_states import ConversationState as FSMConv


def test_all_fsm_states_map_to_llm_state():
    for s in FSMConv:
        mapped = map_fsm_to_conversation_state(s)
        assert isinstance(mapped, LLMConv)


def test_unknown_state_fallback_logs(caplog):
    with caplog.at_level("WARNING"):
        mapped = map_fsm_to_conversation_state("NO_SUCH_STATE")
        assert mapped == LLMConv.INIT
        recs = [r for r in caplog.records if r.message == "fsm_state_mapping_fallback"]
        assert recs
