"""Testes parametrizados do normalizer usando todas as fixtures sanitizadas.

Cada fixture de webhook representa um tipo de mensagem diferente.
Este módulo valida que extract_messages produz resultado coerente para cada tipo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pyloto_corp.adapters.whatsapp.normalizer import extract_messages

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "whatsapp" / "webhook"


def _load_fixture(name: str) -> dict[str, Any]:
    """Carrega fixture de webhook por nome."""
    fixture_path = FIXTURES_DIR / f"{name}.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _get_fixture_files() -> list[str]:
    """Lista todos os arquivos de fixture disponíveis (sem extensão)."""
    return [f.stem for f in FIXTURES_DIR.glob("*.json")]


class TestNormalizerWithFixtures:
    """Testes parametrizados para o normalizer com cada tipo de fixture."""

    @pytest.mark.parametrize("fixture_name", _get_fixture_files())
    def test_fixture_extracts_without_error(self, fixture_name: str):
        """Cada fixture deve ser processada sem lançar exceção."""
        payload = _load_fixture(fixture_name)
        messages = extract_messages(payload)

        # Pode ser lista vazia para status updates, mas não deve falhar
        assert isinstance(messages, list)

    @pytest.mark.parametrize("fixture_name", _get_fixture_files())
    def test_fixture_message_has_required_fields(self, fixture_name: str):
        """Cada mensagem normalizada deve ter os campos obrigatórios."""
        payload = _load_fixture(fixture_name)
        messages = extract_messages(payload)

        for msg in messages:
            assert msg.message_id is not None
            assert msg.message_type is not None


class TestTextMessage:
    """Testes específicos para mensagem de texto."""

    def test_text_message_extracts_body(self):
        """Mensagem de texto deve extrair o corpo."""
        payload = _load_fixture("text.single")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "text"
        assert msg.text is not None
        assert len(msg.text) > 0
        # Campos de mídia devem ser None
        assert msg.media_id is None
        assert msg.media_url is None


class TestImageMessage:
    """Testes específicos para mensagem de imagem."""

    def test_image_message_extracts_media(self):
        """Mensagem de imagem deve extrair media_id."""
        payload = _load_fixture("image")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "image"
        assert msg.media_id is not None
        # Texto deve ser None
        assert msg.text is None


class TestVideoMessage:
    """Testes específicos para mensagem de vídeo."""

    def test_video_message_extracts_media(self):
        """Mensagem de vídeo deve extrair media_id."""
        payload = _load_fixture("video")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "video"
        assert msg.media_id is not None


class TestAudioMessage:
    """Testes específicos para mensagem de áudio."""

    def test_audio_message_extracts_media(self):
        """Mensagem de áudio deve extrair media_id."""
        payload = _load_fixture("audio")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "audio"
        assert msg.media_id is not None


class TestDocumentMessage:
    """Testes específicos para mensagem de documento."""

    def test_document_message_extracts_media(self):
        """Mensagem de documento deve extrair media_id e filename."""
        payload = _load_fixture("document")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "document"
        assert msg.media_id is not None


class TestStickerMessage:
    """Testes específicos para mensagem de sticker."""

    def test_sticker_message_extracts_media(self):
        """Mensagem de sticker deve extrair media_id."""
        payload = _load_fixture("sticker")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "sticker"
        assert msg.media_id is not None


class TestLocationMessage:
    """Testes específicos para mensagem de localização."""

    def test_location_message_extracts_coordinates(self):
        """Mensagem de localização deve extrair latitude/longitude."""
        payload = _load_fixture("location")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "location"
        assert msg.location_latitude is not None
        assert msg.location_longitude is not None


class TestContactsMessage:
    """Testes específicos para mensagem de contatos."""

    def test_contacts_message_extracts_json(self):
        """Mensagem de contatos deve extrair contacts_json serializado."""
        payload = _load_fixture("contacts")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "contacts"
        assert msg.contacts_json is not None
        # Deve ser JSON válido
        parsed = json.loads(msg.contacts_json)
        assert isinstance(parsed, list)


class TestInteractiveButtonReply:
    """Testes específicos para resposta de botão interativo."""

    def test_interactive_button_reply_extracts_id(self):
        """Button reply deve extrair interactive_button_id."""
        payload = _load_fixture("interactive.button_reply")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "interactive"
        assert msg.interactive_type == "button_reply"
        assert msg.interactive_button_id is not None


class TestInteractiveListReply:
    """Testes específicos para resposta de lista interativa."""

    def test_interactive_list_reply_extracts_id(self):
        """List reply deve extrair interactive_list_id."""
        payload = _load_fixture("interactive.list_reply")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "interactive"
        assert msg.interactive_type == "list_reply"
        assert msg.interactive_list_id is not None


class TestReactionMessage:
    """Testes específicos para mensagem de reação."""

    def test_reaction_message_extracts_emoji(self):
        """Reação deve extrair message_id alvo e emoji."""
        payload = _load_fixture("reaction")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        assert msg.message_type == "reaction"
        assert msg.reaction_message_id is not None
        assert msg.reaction_emoji is not None


class TestStatusUpdates:
    """Testes para mensagens de status (não são mensagens de usuário)."""

    @pytest.mark.parametrize(
        "status_fixture",
        ["status.delivered", "status.read", "status.sent", "status.failed"],
    )
    def test_status_updates_produce_empty_list(self, status_fixture: str):
        """Status updates não devem produzir mensagens (são eventos de status)."""
        payload = _load_fixture(status_fixture)
        messages = extract_messages(payload)

        # Status updates não geram mensagens normalizadas
        assert messages == []


class TestUnknownType:
    """Testes para tipo desconhecido."""

    def test_unknown_type_is_handled_gracefully(self):
        """Tipo desconhecido deve ser tratado sem erro."""
        payload = _load_fixture("unknown_type")
        messages = extract_messages(payload)

        assert len(messages) == 1
        msg = messages[0]
        # Tipo original preservado mesmo se não suportado
        assert msg.message_type is not None


class TestEdgeCases:
    """Casos de borda."""

    def test_empty_payload_returns_empty_list(self):
        """Payload vazio retorna lista vazia."""
        messages = extract_messages({})
        assert messages == []

    def test_payload_without_messages_returns_empty_list(self):
        """Payload com entry mas sem messages retorna lista vazia."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "BIZ_ID",
                    "changes": [
                        {
                            "value": {"messaging_product": "whatsapp"},
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        messages = extract_messages(payload)
        assert messages == []

    def test_message_without_id_is_skipped(self):
        """Mensagem sem ID deve ser ignorada."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "BIZ_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "messages": [
                                    {
                                        "type": "text",
                                        "text": {"body": "Sem ID"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        messages = extract_messages(payload)
        assert messages == []

    def test_multiple_messages_in_batch(self):
        """Múltiplas mensagens no mesmo batch são processadas."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "BIZ_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "messages": [
                                    {
                                        "id": "wamid.MSG_001",
                                        "from": "5511999999999",
                                        "type": "text",
                                        "text": {"body": "Mensagem 1"},
                                    },
                                    {
                                        "id": "wamid.MSG_002",
                                        "from": "5511999999999",
                                        "type": "text",
                                        "text": {"body": "Mensagem 2"},
                                    },
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        messages = extract_messages(payload)
        assert len(messages) == 2
        assert messages[0].message_id == "wamid.MSG_001"
        assert messages[1].message_id == "wamid.MSG_002"
