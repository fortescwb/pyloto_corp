"""FlowSender — Envio e Recepção de WhatsApp Flows com Criptografia.

Responsabilidades:
- Gerenciar envio de Flows
- Validar assinatura de webhook
- Descriptografar/criptografar dados de Flow
- Responder a health checks do Meta

Conforme Meta Flows Specification v24.0.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pyloto_corp.adapters.whatsapp.flow_crypto import (
    FlowCryptoError,
    decrypt_aes_key,
    decrypt_flow_data,
    encrypt_flow_response,
    load_private_key,
)
from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class FlowResponse:
    """Resultado do envio de um Flow."""

    flow_id: str
    recipient_id: str
    message_id: str | None
    success: bool
    error_message: str | None = None


@dataclass(slots=True, frozen=True)
class DecryptedFlowData:
    """Dados descriptografados de um Flow recebido."""

    flow_token: str
    action: str
    screen: str
    data: dict[str, Any]
    version: str | None = None


class FlowSender:
    """Gerencia envio e recepção de WhatsApp Flows com criptografia."""

    def __init__(
        self,
        *,
        private_key_pem: str,
        passphrase: str | None = None,
        flow_endpoint_secret: str,
    ) -> None:
        """Inicializa com chaves criptográficas.

        Args:
            private_key_pem: Chave privada RSA em formato PEM
            passphrase: Senha da chave privada (opcional)
            flow_endpoint_secret: Secret para validação de assinatura
        """
        self._endpoint_secret = flow_endpoint_secret.encode("utf-8")
        try:
            self._private_key = load_private_key(private_key_pem, passphrase)
            logger.info("FlowSender initialized with RSA private key")
        except FlowCryptoError as e:
            logger.error("Failed to load RSA private key", extra={"error": str(e)})
            raise

    def validate_signature(self, payload: bytes, signature: str) -> bool:
        """Valida assinatura HMAC-SHA256 do Meta.

        Args:
            payload: Corpo bruto da requisição
            signature: Header X-Hub-Signature-256

        Returns:
            True se assinatura válida
        """
        if not signature.startswith("sha256="):
            logger.warning("Invalid signature format")
            return False

        expected = signature[7:]  # Remove "sha256="
        computed = hmac.new(self._endpoint_secret, payload, hashlib.sha256).hexdigest()
        is_valid = hmac.compare_digest(computed, expected)

        if not is_valid:
            logger.warning("Signature validation failed")

        return is_valid

    def decrypt_request(
        self,
        encrypted_aes_key: str,
        encrypted_flow_data: str,
        initial_vector: str,
    ) -> DecryptedFlowData:
        """Descriptografa dados de Flow recebidos do Meta.

        Args:
            encrypted_aes_key: Chave AES criptografada (base64)
            encrypted_flow_data: Dados criptografados (base64)
            initial_vector: IV para AES-GCM (base64)

        Returns:
            DecryptedFlowData

        Raises:
            FlowCryptoError: Em falha de decriptografia
        """
        try:
            aes_key = decrypt_aes_key(self._private_key, encrypted_aes_key)
            data_dict = decrypt_flow_data(aes_key, encrypted_flow_data, initial_vector)

            logger.debug("Flow data decrypted successfully")

            return DecryptedFlowData(
                flow_token=data_dict.get("flow_token", ""),
                action=data_dict.get("action", ""),
                screen=data_dict.get("screen", ""),
                data=data_dict.get("data", {}),
                version=data_dict.get("version"),
            )

        except FlowCryptoError:
            raise
        except Exception as e:
            logger.error("Flow decryption failed", extra={"error": str(e)})
            raise FlowCryptoError(f"Decryption failed: {e}") from e

    def encrypt_response(
        self,
        response_data: dict[str, Any],
        aes_key: bytes | None = None,
    ) -> dict[str, str]:
        """Criptografa resposta de Flow.

        Args:
            response_data: Dados da resposta
            aes_key: Chave AES (gera nova se não fornecida)

        Returns:
            Dict com encrypted_response, iv, tag (todos base64)

        Raises:
            FlowCryptoError: Em falha de criptografia
        """
        try:
            result = encrypt_flow_response(response_data, aes_key)
            logger.debug("Flow response encrypted successfully")
            return result
        except FlowCryptoError:
            raise
        except Exception as e:
            logger.error("Flow encryption failed", extra={"error": str(e)})
            raise FlowCryptoError(f"Encryption failed: {e}") from e

    def health_check(self) -> dict[str, Any]:
        """Retorna status de health check para Meta."""
        return {
            "status": "healthy",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "version": "1.0",
        }


def create_flow_sender(
    private_key_pem: str,
    flow_endpoint_secret: str,
    passphrase: str | None = None,
) -> FlowSender:
    """Factory para FlowSender."""
    return FlowSender(
        private_key_pem=private_key_pem,
        passphrase=passphrase,
        flow_endpoint_secret=flow_endpoint_secret,
    )
