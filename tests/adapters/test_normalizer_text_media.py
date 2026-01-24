"""Testes de normalização para text e media (image, video, audio, document)."""

from pyloto_corp.adapters.whatsapp.normalizer import extract_messages


def test_extract_text_message():
    """Testa extração de mensagem de texto."""
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
                                    "text": {"body": "Olá, tudo bem?"},
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
    assert messages[0].message_id == "msg_001"
    assert messages[0].message_type == "text"
    assert messages[0].text == "Olá, tudo bem?"
    assert messages[0].from_number == "5511999999999"


def test_extract_image_message():
    """Testa extração de mensagem com imagem."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_002",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "image",
                                    "image": {
                                        "id": "image_id_123",
                                        "mime_type": "image/jpeg",
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
    assert messages[0].message_type == "image"
    assert messages[0].media_id == "image_id_123"
    assert messages[0].media_mime_type == "image/jpeg"


def test_extract_video_message():
    """Testa extração de mensagem com vídeo."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_003",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "video",
                                    "video": {
                                        "id": "video_id_456",
                                        "mime_type": "video/mp4",
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
    assert messages[0].message_type == "video"
    assert messages[0].media_id == "video_id_456"


def test_extract_audio_message():
    """Testa extração de mensagem com áudio."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_004",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "audio",
                                    "audio": {
                                        "id": "audio_id_789",
                                        "mime_type": "audio/ogg",
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
    assert messages[0].message_type == "audio"
    assert messages[0].media_id == "audio_id_789"


def test_extract_document_message():
    """Testa extração de mensagem com documento."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "msg_005",
                                    "from": "5511999999999",
                                    "timestamp": "1234567890",
                                    "type": "document",
                                    "document": {
                                        "id": "doc_id_111",
                                        "mime_type": "application/pdf",
                                        "filename": "contrato.pdf",
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
    assert messages[0].message_type == "document"
    assert messages[0].media_id == "doc_id_111"
    assert messages[0].media_filename == "contrato.pdf"


def test_extract_malformed_text_block():
    """Testa extração robusta de texto malformado."""
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
                                    "text": "not_a_dict",  # Malformado
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
    assert messages[0].text is None  # Deve ignorar gracefully
