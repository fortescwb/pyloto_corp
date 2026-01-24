"""Testes de normalização para location e contacts."""

from pyloto_corp.adapters.whatsapp.normalizer import extract_messages


def test_extract_location_message():
    """Testa extração de mensagem de localização."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_006",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "location",
                                    "location": {
                                        "latitude": -23.550520,
                                        "longitude": -46.633309,
                                        "name": "Pátio do Colégio",
                                        "address": "Rua São Bento, São Paulo, SP",
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
    assert messages[0].message_type == "location"
    assert messages[0].location_latitude == -23.550520
    assert messages[0].location_longitude == -46.633309
    assert messages[0].location_name == "Pátio do Colégio"


def test_extract_contacts_message():
    """Testa extração de mensagem com contatos."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_007",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "contacts",
                                    "contacts": [
                                        {
                                            "name": {
                                                "first_name": "João",
                                                "last_name": "Silva",
                                            },
                                            "phones": [
                                                {"phone": "+5511988776655"}
                                            ],
                                        }
                                    ],
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
    assert messages[0].message_type == "contacts"
    assert messages[0].contacts_json is not None
    # Validar que foi serializado
    assert "João" in messages[0].contacts_json
