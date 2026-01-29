"""Testes para message_builder.

Valida:
- Construção de payloads para cada tipo de mensagem
- Truncation de textos longos
- Validação de limites do WhatsApp
- Sanitização de PII para logging
- Validação de payload
"""

from __future__ import annotations

import pytest

from pyloto_corp.adapters.whatsapp.message_builder import (
    _mask_sensitive_text,
    build_interactive_buttons_payload,
    build_interactive_list_payload,
    build_reaction_payload,
    build_sticker_payload,
    build_text_payload,
    sanitize_payload,
    validate_payload,
)


class TestBuildTextPayload:
    """Testes para build_text_payload."""

    def test_simple_text_message(self):
        """Texto simples é construído corretamente."""
        payload = build_text_payload("5511999999999", "Olá!")

        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "5511999999999"
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Olá!"

    def test_text_truncation_at_4096(self):
        """Texto maior que 4096 chars é truncado."""
        long_text = "a" * 5000
        payload = build_text_payload("5511999999999", long_text)

        body = payload["text"]["body"]
        assert len(body) == 4096
        assert body.endswith("...")

    def test_text_whitespace_is_stripped(self):
        """Whitespace é removido das bordas."""
        payload = build_text_payload("5511999999999", "  Olá!  ")
        assert payload["text"]["body"] == "Olá!"

    def test_empty_text_raises_error(self):
        """Texto vazio lança ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            build_text_payload("5511999999999", "")

    def test_whitespace_only_raises_error(self):
        """Texto apenas com espaços lança ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            build_text_payload("5511999999999", "   ")

    def test_none_text_raises_error(self):
        """Texto None lança ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            build_text_payload("5511999999999", None)  # type: ignore


class TestBuildInteractiveButtonsPayload:
    """Testes para build_interactive_buttons_payload."""

    def test_single_button(self):
        """Payload com um botão é construído corretamente."""
        payload = build_interactive_buttons_payload(
            to="5511999999999",
            body="Escolha uma opção:",
            buttons=[{"id": "btn_1", "title": "Opção 1"}],
        )

        assert payload["type"] == "interactive"
        assert payload["interactive"]["type"] == "button"
        assert len(payload["interactive"]["action"]["buttons"]) == 1
        assert payload["interactive"]["action"]["buttons"][0]["reply"]["title"] == "Opção 1"

    def test_three_buttons_maximum(self):
        """Payload com três botões (máximo)."""
        buttons = [
            {"id": "btn_1", "title": "Opção 1"},
            {"id": "btn_2", "title": "Opção 2"},
            {"id": "btn_3", "title": "Opção 3"},
        ]
        payload = build_interactive_buttons_payload(
            to="5511999999999",
            body="Escolha:",
            buttons=buttons,
        )

        assert len(payload["interactive"]["action"]["buttons"]) == 3

    def test_four_buttons_raises_error(self):
        """Mais de 3 botões lança ValueError."""
        buttons = [{"id": f"btn_{i}", "title": f"Opção {i}"} for i in range(4)]
        with pytest.raises(ValueError, match="1-3"):
            build_interactive_buttons_payload(
                to="5511999999999",
                body="Escolha:",
                buttons=buttons,
            )

    def test_empty_buttons_raises_error(self):
        """Lista vazia de botões lança ValueError."""
        with pytest.raises(ValueError, match="1-3"):
            build_interactive_buttons_payload(
                to="5511999999999",
                body="Escolha:",
                buttons=[],
            )

    def test_button_title_truncation(self):
        """Título de botão maior que 20 chars é truncado."""
        payload = build_interactive_buttons_payload(
            to="5511999999999",
            body="Escolha:",
            buttons=[{"id": "btn_1", "title": "Título muito longo aqui mesmo"}],
        )

        title = payload["interactive"]["action"]["buttons"][0]["reply"]["title"]
        assert len(title) <= 20

    def test_body_truncation_at_1024(self):
        """Body maior que 1024 chars é truncado."""
        long_body = "x" * 2000
        payload = build_interactive_buttons_payload(
            to="5511999999999",
            body=long_body,
            buttons=[{"id": "btn_1", "title": "Ok"}],
        )

        body = payload["interactive"]["body"]["text"]
        assert len(body) == 1024
        assert body.endswith("...")

    def test_header_and_footer_optional(self):
        """Header e footer são opcionais."""
        payload = build_interactive_buttons_payload(
            to="5511999999999",
            body="Escolha:",
            buttons=[{"id": "btn_1", "title": "Ok"}],
            header="Cabeçalho",
            footer="Rodapé",
        )

        assert payload["interactive"]["header"]["text"] == "Cabeçalho"
        assert payload["interactive"]["footer"]["text"] == "Rodapé"

    def test_header_truncation_at_60(self):
        """Header maior que 60 chars é truncado."""
        payload = build_interactive_buttons_payload(
            to="5511999999999",
            body="Escolha:",
            buttons=[{"id": "btn_1", "title": "Ok"}],
            header="x" * 100,
        )

        assert len(payload["interactive"]["header"]["text"]) == 60


class TestBuildInteractiveListPayload:
    """Testes para build_interactive_list_payload."""

    def test_simple_list(self):
        """Lista simples é construída corretamente."""
        sections = [
            {
                "title": "Seção 1",
                "rows": [
                    {"id": "row_1", "title": "Item 1"},
                    {"id": "row_2", "title": "Item 2"},
                ],
            }
        ]
        payload = build_interactive_list_payload(
            to="5511999999999",
            body="Selecione um item:",
            sections=sections,
        )

        assert payload["type"] == "interactive"
        assert payload["interactive"]["type"] == "list"
        assert len(payload["interactive"]["action"]["sections"]) == 1

    def test_empty_sections_raises_error(self):
        """Seções vazias lançam ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            build_interactive_list_payload(
                to="5511999999999",
                body="Selecione:",
                sections=[],
            )

    def test_button_text_truncation(self):
        """Texto do botão maior que 20 chars é truncado."""
        sections = [{"title": "Seção", "rows": [{"id": "1", "title": "Item"}]}]
        payload = build_interactive_list_payload(
            to="5511999999999",
            body="Selecione:",
            sections=sections,
            button_text="Texto muito longo para o botão",
        )

        assert len(payload["interactive"]["action"]["button"]) == 20


class TestBuildReactionPayload:
    """Testes para build_reaction_payload."""

    def test_valid_emoji_reaction(self):
        """Reação com emoji válido."""
        payload = build_reaction_payload(
            to="5511999999999",
            emoji="👍",
            message_id="wamid.ABC123",
        )

        assert payload["type"] == "reaction"
        assert payload["reaction"]["emoji"] == "👍"
        assert payload["reaction"]["message_id"] == "wamid.ABC123"

    def test_empty_emoji_uses_default(self):
        """Emoji vazio usa emoji padrão."""
        payload = build_reaction_payload(
            to="5511999999999",
            emoji="",
            message_id="wamid.ABC123",
        )

        assert payload["reaction"]["emoji"] == "👍"


class TestBuildStickerPayload:
    """Testes para build_sticker_payload."""

    def test_valid_sticker(self):
        """Sticker válido é construído corretamente."""
        payload = build_sticker_payload(
            to="5511999999999",
            sticker_id="https://example.com/sticker.webp",
        )

        assert payload["type"] == "sticker"
        assert payload["sticker"]["link"] == "https://example.com/sticker.webp"

    def test_empty_sticker_id_raises_error(self):
        """Sticker ID vazio lança ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            build_sticker_payload(to="5511999999999", sticker_id="")


class TestSanitizePayload:
    """Testes para sanitize_payload."""

    def test_phone_number_masked(self):
        """Número de telefone é mascarado."""
        payload = {"to": "5511999999999", "text": {"body": "Olá"}}
        sanitized = sanitize_payload(payload)

        assert sanitized["to"] == "***9999"
        # Original não é modificado
        assert payload["to"] == "5511999999999"

    def test_email_in_text_masked(self):
        """Email no texto é mascarado."""
        payload = {
            "to": "5511999999999",
            "text": {"body": "Meu email é user@example.com"},
        }
        sanitized = sanitize_payload(payload)

        assert "[EMAIL]" in sanitized["text"]["body"]

    def test_cpf_in_text_masked(self):
        """CPF no texto é mascarado."""
        payload = {
            "to": "5511999999999",
            "text": {"body": "Meu CPF é 123.456.789-00"},
        }
        sanitized = sanitize_payload(payload)

        assert "[DOCUMENT]" in sanitized["text"]["body"]

    def test_phone_in_text_masked(self):
        """Telefone no texto é mascarado."""
        payload = {
            "to": "5511999999999",
            "text": {"body": "Meu telefone é (11) 99999-9999"},
        }
        sanitized = sanitize_payload(payload)

        assert "[PHONE]" in sanitized["text"]["body"]


class TestMaskSensitiveText:
    """Testes para _mask_sensitive_text."""

    def test_mask_email(self):
        """Email é mascarado."""
        text = "Contato: user@example.com"
        masked = _mask_sensitive_text(text)
        assert masked == "Contato: [EMAIL]"

    def test_mask_cpf(self):
        """CPF é mascarado."""
        text = "CPF: 123.456.789-00"
        masked = _mask_sensitive_text(text)
        assert masked == "CPF: [DOCUMENT]"

    def test_mask_phone(self):
        """Telefone é mascarado."""
        text = "Telefone: (11) 99999-9999"
        masked = _mask_sensitive_text(text)
        assert masked == "Telefone: [PHONE]"

    def test_mask_multiple_pii(self):
        """Múltiplos PIIs são mascarados."""
        text = "Email: a@b.com, CPF: 111.222.333-44, Tel: (21) 98888-7777"
        masked = _mask_sensitive_text(text)
        assert "[EMAIL]" in masked
        assert "[DOCUMENT]" in masked
        assert "[PHONE]" in masked


class TestValidatePayload:
    """Testes para validate_payload."""

    def test_valid_text_payload(self):
        """Payload de texto válido."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511999999999",
            "type": "text",
            "text": {"body": "Olá!"},
        }
        is_valid, msg = validate_payload(payload)
        assert is_valid is True
        assert msg == "OK"

    def test_empty_payload_invalid(self):
        """Payload vazio é inválido."""
        is_valid, msg = validate_payload({})
        assert is_valid is False
        assert "non-empty" in msg

    def test_missing_messaging_product_invalid(self):
        """Falta messaging_product é inválido."""
        payload = {"to": "5511999999999", "type": "text"}
        is_valid, msg = validate_payload(payload)
        assert is_valid is False
        assert "messaging_product" in msg

    def test_wrong_messaging_product_invalid(self):
        """messaging_product errado é inválido."""
        payload = {
            "messaging_product": "telegram",
            "to": "5511999999999",
            "type": "text",
        }
        is_valid, msg = validate_payload(payload)
        assert is_valid is False
        assert "whatsapp" in msg

    def test_missing_to_invalid(self):
        """Falta 'to' é inválido."""
        payload = {"messaging_product": "whatsapp", "type": "text"}
        is_valid, msg = validate_payload(payload)
        assert is_valid is False
        assert "to" in msg

    def test_missing_type_invalid(self):
        """Falta 'type' é inválido."""
        payload = {"messaging_product": "whatsapp", "to": "5511999999999"}
        is_valid, msg = validate_payload(payload)
        assert is_valid is False
        assert "type" in msg

    def test_invalid_type_invalid(self):
        """Tipo inválido é inválido."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511999999999",
            "type": "video",  # Não suportado pelo validate_payload
        }
        is_valid, msg = validate_payload(payload)
        assert is_valid is False
        assert "Invalid message type" in msg

    def test_text_without_body_invalid(self):
        """Texto sem body é inválido."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511999999999",
            "type": "text",
            "text": {},
        }
        is_valid, msg = validate_payload(payload)
        assert is_valid is False
        assert "text.body" in msg

    def test_valid_interactive_payload(self):
        """Payload interativo válido."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511999999999",
            "type": "interactive",
            "interactive": {"type": "button", "body": {"text": "Escolha"}},
        }
        is_valid, msg = validate_payload(payload)
        assert is_valid is True

    def test_valid_reaction_payload(self):
        """Payload de reação válido."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511999999999",
            "type": "reaction",
            "reaction": {"message_id": "wamid.123", "emoji": "👍"},
        }
        is_valid, msg = validate_payload(payload)
        assert is_valid is True

    def test_valid_sticker_payload(self):
        """Payload de sticker válido."""
        payload = {
            "messaging_product": "whatsapp",
            "to": "5511999999999",
            "type": "sticker",
            "sticker": {"link": "https://example.com/sticker.webp"},
        }
        is_valid, msg = validate_payload(payload)
        assert is_valid is True
