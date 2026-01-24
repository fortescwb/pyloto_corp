"""Testes de normalização para interactive e reaction."""

from pyloto_corp.adapters.whatsapp.normalizer import extract_messages


def test_extract_interactive_button_message():
    """Testa extração de mensagem interativa com botão."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_008",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button",
                                        "button_reply": {
                                            "id": "btn_001",
                                            "title": "Sim",
                                        },
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_messages(payload)
    assert len(messages) == 1
    assert messages[0].message_type == "interactive"
    assert messages[0].interactive_type == "button"
    assert messages[0].interactive_button_id == "btn_001"


def test_extract_interactive_list_message():
    """Testa extração de mensagem interativa com lista."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_009",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list",
                                        "list_reply": {
                                            "id": "list_item_001",
                                            "title": "Opção 1",
                                        },
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_messages(payload)
    assert len(messages) == 1
    assert messages[0].message_type == "interactive"
    assert messages[0].interactive_type == "list"
    assert messages[0].interactive_list_id == "list_item_001"


def test_extract_reaction_message():
    """Testa extração de mensagem de reação."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_010",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "reaction",
                                    "reaction": {
                                        "message_id": "msg_original",
                                        "emoji": "👍",
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_messages(payload)
    assert len(messages) == 1
    assert messages[0].message_type == "reaction"
    assert messages[0].reaction_message_id == "msg_original"
    assert messages[0].reaction_emoji == "👍"
