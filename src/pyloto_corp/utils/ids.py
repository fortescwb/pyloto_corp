"""Geradores de identificadores."""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid


def new_session_id() -> str:
    """Gera um session_id único."""

    return str(uuid.uuid4())


def derive_user_key(phone_e164: str, pepper_secret: str) -> str:
    """Deriva um identificador estável e não reversível para o usuário.

    Regra: user_key = base64url(HMAC_SHA256(PEPPER_SECRET, phone_e164)) sem padding.
    """

    digest = hmac.new(
        pepper_secret.encode("utf-8"),
        phone_e164.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
