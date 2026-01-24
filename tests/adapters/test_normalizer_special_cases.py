"""Testes de normalização para casos especiais e múltiplas mensagens."""

from pyloto_corp.adapters.whatsapp.normalizer import extract_messages


def test_extract_multiple_messages():
    """Testa extração de múltiplas mensagens no mesmo payload."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_001",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {"body": "Primeira"},
                                },
                                {
                                    "id": "msg_002",
                                    "from": "5511999999999",
                                    "timestamp": "1234567891",
                                    "type": "text",
                                    "text": {"body": "Segunda"},
                                },
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_messages(payload)
    assert len(messages) == 2
    assert messages[0].message_id == "msg_001"
    assert messages[1].message_id == "msg_002"


def test_extract_no_message_id():
    """Testa que mensagens sem ID são ignoradas."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {"body": "Sem ID"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = extract_messages(payload)
    assert len(messages) == 0


def test_extract_empty_payload():
    """Testa payload vazio."""
    payload = {}
    messages = extract_messages(payload)
    assert len(messages) == 0
