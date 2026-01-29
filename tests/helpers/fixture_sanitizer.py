"""Sanitizador determinístico para fixtures de teste WhatsApp.

Remove PII, tokens e identificadores reais de payloads capturados,
substituindo por placeholders determinísticos.

Regras de sanitização (não negociáveis):
- Números de telefone → PHONE_E164_TEST
- wa_id → WA_ID_TEST  
- message_id, wamid → MSG_ID_TEST_xxx
- status_id → STATUS_ID_TEST
- phone_number_id → PHONE_NUMBER_ID_TEST
- business_id → BUSINESS_ID_TEST
- timestamps → 1700000000
- nomes de contato → CONTACT_NAME_TEST
- URLs de mídia → https://example.test/media/ID
- tokens/secrets → REMOVIDOS completamente
"""

from __future__ import annotations

import copy
import re
from typing import Any

# Placeholders determinísticos
PLACEHOLDERS = {
    "phone": "5511999999999",
    "wa_id": "WA_ID_TEST",
    "from": "5511888888888",
    "display_phone_number": "+55 11 99999-9999",
    "phone_number_id": "PHONE_NUMBER_ID_TEST",
    "business_id": "BUSINESS_ID_TEST",
    "message_id": "wamid.MSG_ID_TEST_",
    "status_id": "wamid.STATUS_ID_TEST_",
    "timestamp": "1700000000",
    "contact_name": "CONTACT_NAME_TEST",
    "media_url": "https://example.test/media/",
    "profile_name": "PROFILE_NAME_TEST",
}

# Chaves que devem ser removidas completamente (tokens/secrets)
KEYS_TO_REMOVE = frozenset({
    "access_token",
    "authorization",
    "appsecret_proof",
    "x-hub-signature-256",
    "bearer",
    "secret",
    "api_key",
    "password",
})

# Chaves que contêm IDs sensíveis
ID_KEYS = frozenset({
    "id",
    "message_id",
    "wamid",
    "wa_id",
    "phone_number_id",
    "business_id",
    "recipient_id",
})

# Chaves que contêm telefones
PHONE_KEYS = frozenset({
    "from",
    "to",
    "phone",
    "phone_number",
    "display_phone_number",
    "wa_id",
    "recipient",
})

# Chaves que contêm timestamps
TIMESTAMP_KEYS = frozenset({
    "timestamp",
    "expiration_timestamp",
    "created_at",
    "updated_at",
})

# Chaves que contêm nomes de contato
NAME_KEYS = frozenset({
    "name",
    "pushname",
    "profile_name",
    "formatted_name",
    "first_name",
    "last_name",
})

# Chaves que contêm URLs
URL_KEYS = frozenset({
    "url",
    "link",
    "media_url",
    "image_url",
    "video_url",
    "audio_url",
    "document_url",
    "sticker_url",
})

# Contador para gerar IDs únicos determinísticos
_id_counter = 0


def _reset_counter() -> None:
    """Reseta contador de IDs (para testes determinísticos)."""
    global _id_counter
    _id_counter = 0


def _next_id() -> int:
    """Retorna próximo ID único."""
    global _id_counter
    _id_counter += 1
    return _id_counter


def _is_phone_number(value: str) -> bool:
    """Detecta se valor parece número de telefone."""
    if not isinstance(value, str):
        return False
    # Remove caracteres não numéricos
    digits = re.sub(r"[^\d]", "", value)
    # Telefone tem 10-15 dígitos
    return 10 <= len(digits) <= 15


def _is_message_id(value: str) -> bool:
    """Detecta se valor parece ID de mensagem WhatsApp."""
    if not isinstance(value, str):
        return False
    # Apenas detecta se começa com wamid. ou parece base64 com comprimento típico
    return value.startswith("wamid.") or (
        len(value) > 30 and re.match(r"^[A-Za-z0-9+/=]+$", value)
    )


def _is_url(value: str) -> bool:
    """Detecta se valor é URL."""
    if not isinstance(value, str):
        return False
    return value.startswith(("http://", "https://"))


def _sanitize_value(key: str, value: Any) -> Any:
    """Sanitiza um valor baseado na chave."""
    key_lower = key.lower()
    
    # Remover chaves de token/secret
    if key_lower in KEYS_TO_REMOVE:
        return "[REMOVED]"
    
    # Se não é string, retornar como está (exceto para recursão em dict/list)
    if not isinstance(value, str):
        return value
    
    # Chaves de ID
    if key_lower in ID_KEYS or key_lower.endswith("_id"):
        if key_lower in ("phone_number_id",):
            return PLACEHOLDERS["phone_number_id"]
        if key_lower in ("business_id",):
            return PLACEHOLDERS["business_id"]
        if key_lower in ("wa_id",):
            return PLACEHOLDERS["wa_id"]
        if _is_message_id(value):
            return f"{PLACEHOLDERS['message_id']}{_next_id():03d}"
        return f"ID_TEST_{_next_id():03d}"
    
    # Chaves de telefone
    if key_lower in PHONE_KEYS:
        if key_lower == "display_phone_number":
            return PLACEHOLDERS["display_phone_number"]
        if key_lower == "from":
            return PLACEHOLDERS["from"]
        return PLACEHOLDERS["phone"]
    
    # Chaves de timestamp
    if key_lower in TIMESTAMP_KEYS:
        return PLACEHOLDERS["timestamp"]
    
    # Chaves de nome
    if key_lower in NAME_KEYS:
        if key_lower == "pushname" or key_lower == "profile_name":
            return PLACEHOLDERS["profile_name"]
        return PLACEHOLDERS["contact_name"]
    
    # Chaves de URL
    if key_lower in URL_KEYS or _is_url(value):
        return f"{PLACEHOLDERS['media_url']}{_next_id():03d}"
    
    # Detecção heurística para valores não mapeados
    if _is_phone_number(value):
        return PLACEHOLDERS["phone"]
    
    if _is_message_id(value):
        return f"{PLACEHOLDERS['message_id']}{_next_id():03d}"
    
    return value


def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitiza um dicionário recursivamente."""
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        # Remover chaves de token/secret completamente
        if key_lower in KEYS_TO_REMOVE:
            continue
        
        if isinstance(value, dict):
            result[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = _sanitize_list(key, value)
        else:
            result[key] = _sanitize_value(key, value)
    
    return result


def _sanitize_list(parent_key: str, data: list[Any]) -> list[Any]:
    """Sanitiza uma lista recursivamente."""
    result = []
    for item in data:
        if isinstance(item, dict):
            result.append(_sanitize_dict(item))
        elif isinstance(item, list):
            result.append(_sanitize_list(parent_key, item))
        else:
            result.append(_sanitize_value(parent_key, item))
    return result


def sanitize_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitiza payload de webhook WhatsApp removendo PII.
    
    Args:
        payload: Payload bruto do webhook
        
    Returns:
        Payload sanitizado com placeholders
    """
    _reset_counter()
    return _sanitize_dict(copy.deepcopy(payload))


def sanitize_graph_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitiza response da Graph API removendo PII.
    
    Args:
        payload: Response bruto da API
        
    Returns:
        Response sanitizado com placeholders
    """
    _reset_counter()
    return _sanitize_dict(copy.deepcopy(payload))


def load_and_sanitize(filepath: str) -> dict[str, Any]:
    """Carrega JSON de arquivo e sanitiza.
    
    Args:
        filepath: Caminho do arquivo JSON
        
    Returns:
        Conteúdo sanitizado
    """
    import json
    from pathlib import Path
    
    content = Path(filepath).read_text(encoding="utf-8")
    data = json.loads(content)
    
    # Detecta tipo baseado no path
    if "graph_response" in filepath or "response" in filepath:
        return sanitize_graph_response(data)
    return sanitize_webhook_payload(data)
