"""Cliente outbound para envio de mensagens via Meta/WhatsApp.

Responsabilidade:
- Orquestrar validação e construção de payload
- Gerenciar idempotência via dedupe_key
- Evitar exposição de secrets em logs
- Rastrear envios para auditoria (sem PII)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from pyloto_corp.adapters.whatsapp.models import (
    OutboundMessageRequest,
    OutboundMessageResponse,
)
from pyloto_corp.adapters.whatsapp.payload_builders.factory import (
    build_full_payload,
)
from pyloto_corp.adapters.whatsapp.validators import (
    ValidationError,
    WhatsAppMessageValidator,
)

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
    """Cliente para envio outbound via API Meta/WhatsApp.

    Orquestra validação, construção de payload e envio.
    """

    def __init__(
        self,
        api_endpoint: str,
        access_token: str,
        phone_number_id: str,
    ):
        """Inicializa o cliente.

        Args:
            api_endpoint: URL base da API Meta
            access_token: Bearer token para autenticação
            phone_number_id: ID do número de telefone registrado
        """
        self.api_endpoint = api_endpoint
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.validator = WhatsAppMessageValidator()

    def send_message_sync(self, request: OutboundMessageRequest) -> OutboundMessageResponse:
        """Envia mensagem em contexto síncrono (apoio para testes/local)."""

        async def _runner() -> OutboundMessageResponse:
            return await self.send_message(request)

        return asyncio.run(_runner())

    async def send_message(
        self,
        request: OutboundMessageRequest,
    ) -> OutboundMessageResponse:
        """Envia uma mensagem individual (async-first).

        Args:
            request: Requisição de envio

        Returns:
            Resposta do envio
        """
        # 1. Validar requisição
        validation_error = self._validate_request(request)
        if validation_error:
            return validation_error

        # 2. Construir payload
        payload_result = self._build_payload_safe(request)
        if isinstance(payload_result, OutboundMessageResponse):
            return payload_result

        # 3. Enviar via HTTP (async/await, padrão puro)
        return await self._send_real(request)

    def _validate_request(
        self,
        request: OutboundMessageRequest,
    ) -> OutboundMessageResponse | None:
        """Valida requisição e retorna erro se inválida."""
        try:
            self.validator.validate_outbound_request(request)
            return None
        except ValidationError as exc:
            return OutboundMessageResponse(
                success=False,
                error_code="VALIDATION_ERROR",
                error_message=str(exc),
            )

    def _build_payload_safe(
        self,
        request: OutboundMessageRequest,
    ) -> dict[str, Any] | OutboundMessageResponse:
        """Constrói payload com tratamento de erro."""
        try:
            return build_full_payload(request)
        except Exception as exc:
            # Nunca registrar "to" (telefone) em logs - é PII.
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

    async def _send_real(
        self,
        request: OutboundMessageRequest,
    ) -> OutboundMessageResponse:
        """Envia mensagem via WhatsApp HTTP API."""
        from pyloto_corp.adapters.whatsapp.http_client import WhatsAppHttpClient
        from pyloto_corp.config.settings import get_settings

        settings = get_settings()

        # Construir payload
        payload_result = self._build_payload_safe(request)
        if isinstance(payload_result, OutboundMessageResponse):
            return payload_result

        payload = payload_result

        # Construir endpoint para envio
        phone_id = settings.whatsapp_phone_number_id
        api_version = settings.whatsapp_api_version
        base_url = settings.whatsapp_api_base_url
        endpoint = f"{base_url}/{api_version}/{phone_id}/messages"

        try:
            http_client = WhatsAppHttpClient()
            response = await http_client.send_message(
                endpoint=endpoint,
                access_token=settings.whatsapp_access_token,
                payload=payload,
            )

            message_id = response.get("messages", [{}])[0].get("id", "unknown")
            logger.info(
                "message_sent_to_whatsapp_api",
                extra={
                    "message_id": message_id,
                    "request_id": request.idempotency_key,
                },
            )

            return OutboundMessageResponse(
                success=True,
                message_id=message_id,
            )

        except Exception as e:
            logger.error(
                "whatsapp_send_failed",
                extra={
                    "error": str(e),
                    "request_id": request.idempotency_key,
                },
            )
            return OutboundMessageResponse(
                success=False,
                error_code="WHATSAPP_API_ERROR",
                error_message=str(e),
            )

    def send_batch(
        self,
        requests: list[OutboundMessageRequest],
    ) -> list[OutboundMessageResponse]:
        """Envia lote de mensagens em modo síncrono (helper)."""
        responses: list[OutboundMessageResponse] = []
        for request in requests:
            responses.append(self.send_message_sync(request))
        return responses

    @staticmethod
    def generate_dedupe_key(
        to: str,
        message_type: str,
        content_hash: str,
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
