"""Primitivas Criptográficas para Flows — RSA-OAEP e AES-GCM.

Responsabilidades:
- Operações criptográficas (decrypt_aes_key, encrypt_data, etc.)
- Isolamento de cryptography.hazmat
- Suporte a RSA-OAEP e AES-256-GCM

Conforme Meta Flows Specification v24.0 e regras_e_padroes.md.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256

# Constantes conforme Meta Flows Spec
AES_KEY_SIZE = 32  # 256 bits
IV_SIZE = 12  # 96 bits (recomendado para GCM)
TAG_SIZE = 16  # 128 bits


class FlowCryptoError(Exception):
    """Erro em operação criptográfica de Flow."""

    pass


def load_private_key(private_key_pem: str, passphrase: str | None = None) -> Any:
    """Carrega chave privada RSA em formato PEM.

    Args:
        private_key_pem: Chave privada em formato PEM
        passphrase: Senha da chave (opcional)

    Returns:
        Objeto de chave privada RSA

    Raises:
        FlowCryptoError: Se chave inválida
    """
    try:
        passphrase_bytes = passphrase.encode() if passphrase else None
        return serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=passphrase_bytes,
            backend=default_backend(),
        )
    except Exception as e:
        raise FlowCryptoError(f"Invalid private key: {e}") from e


def decrypt_aes_key(private_key: Any, encrypted_aes_key: str) -> bytes:
    """Descriptografa chave AES criptografada com RSA-OAEP.

    Args:
        private_key: Chave privada RSA
        encrypted_aes_key: Chave AES criptografada (base64)

    Returns:
        Chave AES bruta (256 bits)

    Raises:
        FlowCryptoError: Se decriptografia falhar
    """
    try:
        aes_key_encrypted = base64.b64decode(encrypted_aes_key)
        aes_key = private_key.decrypt(
            aes_key_encrypted,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=SHA256()),
                algorithm=SHA256(),
                label=None,
            ),
        )

        if len(aes_key) != AES_KEY_SIZE:
            msg = f"Invalid AES key size: {len(aes_key)}"
            raise FlowCryptoError(msg)

        return aes_key

    except FlowCryptoError:
        raise
    except Exception as e:
        raise FlowCryptoError(f"AES key decryption failed: {e}") from e


def decrypt_flow_data(
    aes_key: bytes,
    encrypted_flow_data: str,
    initial_vector: str,
) -> dict[str, Any]:
    """Descriptografa dados de Flow com AES-256-GCM.

    Args:
        aes_key: Chave AES (256 bits)
        encrypted_flow_data: Dados criptografados (base64)
        initial_vector: IV para GCM (base64)

    Returns:
        Dicionário com dados descriptografados

    Raises:
        FlowCryptoError: Se decriptografia falhar
    """
    try:
        flow_data_encrypted = base64.b64decode(encrypted_flow_data)
        iv = base64.b64decode(initial_vector)

        aesgcm = AESGCM(aes_key)
        decrypted_bytes = aesgcm.decrypt(iv, flow_data_encrypted, None)
        return json.loads(decrypted_bytes.decode("utf-8"))

    except Exception as e:
        raise FlowCryptoError(f"Flow data decryption failed: {e}") from e


def encrypt_flow_response(
    response_data: dict[str, Any],
    aes_key: bytes | None = None,
) -> dict[str, str]:
    """Criptografa resposta de Flow com AES-256-GCM.

    Args:
        response_data: Dados da resposta
        aes_key: Chave AES (gera nova se não fornecida)

    Returns:
        Dict com encrypted_response, iv, tag (todos base64)

    Raises:
        FlowCryptoError: Se criptografia falhar
    """
    try:
        if aes_key is None:
            aes_key = os.urandom(AES_KEY_SIZE)
        iv = os.urandom(IV_SIZE)

        plaintext = json.dumps(response_data).encode("utf-8")
        aesgcm = AESGCM(aes_key)
        ciphertext_with_tag = aesgcm.encrypt(iv, plaintext, None)

        ciphertext = ciphertext_with_tag[:-TAG_SIZE]
        tag = ciphertext_with_tag[-TAG_SIZE:]

        return {
            "encrypted_response": base64.b64encode(ciphertext).decode("utf-8"),
            "iv": base64.b64encode(iv).decode("utf-8"),
            "tag": base64.b64encode(tag).decode("utf-8"),
        }

    except Exception as e:
        raise FlowCryptoError(f"Flow response encryption failed: {e}") from e
