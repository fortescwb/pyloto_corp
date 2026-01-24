"""Cliente outbound para envio de mensagens via Meta/WhatsApp.

Responsabilidade:
- Construir requisições conforme API Meta
- Gerenciar idempotência via dedupe_key
- Implementar retry logic com backoff
- Evitar exposição de secrets em logs
- Rastrear envios para auditoria (sem PII)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest, OutboundMessageResponse
from pyloto_corp.adapters.whatsapp.validators import ValidationError, WhatsAppMessageValidator
from pyloto_corp.domain.enums import InteractiveType, MessageType

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OutboundMessage:
    """Mensagem outbound estruturada (interno)."""

    to: str
    message_type: str
    text: str | None = None
    media_id: str | None = None
    media_url: str | None = None
    media_filename: str | None = None
    buttons: list[dict[str, str]] | None = None
    interactive_type: str | None = None
    template_name: str | None = None
    template_params: dict[str, Any] | None = None
    category: str | None = None
    idempotency_key: str | None = None


class WhatsAppOutboundClient:
    """Cliente para envio outbound (esqueleto com validação).

    TODO: integrar com HTTP client (httpx) e Meta API endpoint.
    TODO: implementar retry loop com exponential backoff.
    TODO: armazenar dedupe_key em Firestore para idempotência.
    """

    def __init__(self, api_endpoint: str, access_token: str, phone_number_id: str):
        """Inicializa o cliente.

        Args:
            api_endpoint: URL base da API Meta (ex: https://graph.instagram.com/v20.0)
            access_token: Bearer token para autenticação
            phone_number_id: ID do número de telefone registrado
        """
        self.api_endpoint = api_endpoint
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.validator = WhatsAppMessageValidator()

    def send_message(self, request: OutboundMessageRequest) -> OutboundMessageResponse:
        """Envia uma mensagem individual.

        Args:
            request: Requisição de envio validada

        Returns:
            Resposta do envio
        """
        # Validar requisição
        try:
            self.validator.validate_outbound_request(request)
        except ValidationError as exc:
            return OutboundMessageResponse(
                success=False,
                error_code="VALIDATION_ERROR",
                error_message=str(exc),
            )

        # Construir payload conforme tipo
        try:
            self._build_payload(request)
        except Exception as exc:
            # Nunca registrar "to" (telefone) em logs - é PII.
            # Usar apenas message_type e idempotency_key para rastreamento.
            logger.exception(
                "Error building payload",
                extra={
                    "message_type": request.message_type,
                    "idempotency_key": request.idempotency_key,
                },
            )
            return OutboundMessageResponse(
                success=False,
                error_code="PAYLOAD_BUILD_ERROR",
                error_message=str(exc),
            )

        # TODO: enviar via HTTP (httpx)
        # TODO: implementar retry logic
        # TODO: registrar em Firestore para idempotência e auditoria

        # Registrar apenas metadados não-PII: tipo de mensagem, categoria e
        # idempotency_key para rastreamento. Nunca incluir "to" (telefone).
        logger.info(
            "Message sent (mock)",
            extra={
                "message_type": request.message_type,
                "category": request.category,
                "idempotency_key": request.idempotency_key,
            },
        )

        return OutboundMessageResponse(
            success=True,
            message_id="mock_message_id",
        )

    def send_batch(
        self, requests: list[OutboundMessageRequest]
    ) -> list[OutboundMessageResponse]:
        """Envia lote de mensagens.

        Args:
            requests: Lista de requisições de envio

        Returns:
            Lista de respostas (uma por requisição, mesma ordem)
        """
        responses: list[OutboundMessageResponse] = []
        for request in requests:
            response = self.send_message(request)
            responses.append(response)
        return responses

    def _build_payload(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói o payload JSON para a API Meta.

        Args:
            request: Requisição de envio

        Returns:
            Payload pronto para enviar à Meta

        Raises:
            ValueError: Se payload inválido
        """
        msg_type = MessageType(request.message_type)

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": request.to,
            "type": request.message_type,
        }

        # Template ou session message
        if request.template_name:
            payload["template"] = {
                "name": request.template_name,
                "language": {"code": "pt_BR"},
            }
            if request.template_params:
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(p)} 
                            for p in request.template_params.values()
                        ],
                    }
                ]
        else:
            # Session message (free-form)
            if msg_type == MessageType.TEXT:
                payload[msg_type] = {"preview_url": False, "body": request.text}

            elif msg_type in (MessageType.IMAGE, MessageType.VIDEO):
                payload[msg_type] = self._build_media_object(
                    request.media_id, request.media_url, request.text
                )

            elif msg_type == MessageType.AUDIO:
                payload[msg_type] = self._build_media_object(
                    request.media_id, request.media_url
                )

            elif msg_type == MessageType.DOCUMENT:
                doc_obj = self._build_media_object(
                    request.media_id, request.media_url, request.text
                )
                if request.media_filename:
                    doc_obj["filename"] = request.media_filename
                payload[msg_type] = doc_obj

            elif msg_type == MessageType.LOCATION:
                payload[msg_type] = {
                    "latitude": request.location_latitude,
                    "longitude": request.location_longitude,
                    "name": request.location_name or None,
                    "address": request.location_address or None,
                }

            elif msg_type == MessageType.ADDRESS:
                payload[msg_type] = {
                    "street": request.address_street or None,
                    "city": request.address_city or None,
                    "state": request.address_state or None,
                    "zip_code": request.address_zip_code or None,
                    "country_code": request.address_country_code or None,
                }

            elif msg_type == MessageType.INTERACTIVE:
                payload[msg_type] = self._build_interactive_object(request)

        # Adicionar idempotency_key se fornecido (x-idempotency-key header)
        # será adicionado no HTTP client

        return payload

    def _build_media_object(
        self, media_id: str | None, media_url: str | None, caption: str | None = None
    ) -> dict[str, Any]:
        """Constrói objeto de mídia para payload.

        Args:
            media_id: ID de mídia hospedada
            media_url: URL pública para upload
            caption: Legenda opcional

        Returns:
            Objeto media conforme API Meta
        """
        media_obj: dict[str, Any] = {}

        if media_id:
            media_obj["id"] = media_id
        elif media_url:
            media_obj["link"] = media_url

        if caption:
            media_obj["caption"] = caption

        return media_obj

    def _build_interactive_object(
        self, request: OutboundMessageRequest
    ) -> dict[str, Any]:
        """Constrói objeto interativo para payload.

        Args:
            request: Requisição com dados interativos

        Returns:
            Objeto interactive conforme API Meta
        """
        # Validação já garante valor válido
        int_type = InteractiveType(request.interactive_type)

        interactive_obj: dict[str, Any] = {
            "type": int_type.value,
            "body": {"text": request.text},
        }

        if int_type == InteractiveType.BUTTON:
            interactive_obj["action"] = {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": btn["id"], "title": btn["title"]},
                    }
                    for btn in (request.buttons or [])
                ]
            }

        elif int_type == InteractiveType.LIST:
            interactive_obj["action"] = {
                "button": "Ver opções",
                "sections": request.buttons or [],
            }

        elif int_type == InteractiveType.FLOW:
            interactive_obj["action"] = {
                "name": "flow",
                "parameters": {
                    "flow_message_version": request.flow_message_version,
                    "flow_token": request.flow_token,
                    "flow_id": request.flow_id,
                    "flow_cta": request.flow_cta,
                    "flow_action": request.flow_action,
                },
            }

        elif int_type == InteractiveType.CTA_URL:
            interactive_obj["action"] = {
                "name": "cta_url",
                "parameters": {
                    "display_text": request.cta_display_text,
                    "url": request.cta_url,
                },
            }

        elif int_type == InteractiveType.LOCATION_REQUEST_MESSAGE:
            interactive_obj["action"] = {
                "name": "send_location",
            }

        if request.footer:
            interactive_obj["footer"] = {"text": request.footer}

        return interactive_obj

    @staticmethod
    def _generate_dedupe_key(
        to: str, message_type: str, content_hash: str
    ) -> str:
        """Gera chave de deduplicação baseada em conteúdo.

        Args:
            to: Número destino (E.164)
            message_type: Tipo de mensagem
            content_hash: Hash do conteúdo

        Returns:
            Dedupe key SHA256
        """
        key_material = f"{to}:{message_type}:{content_hash}"
        return hashlib.sha256(key_material.encode()).hexdigest()
