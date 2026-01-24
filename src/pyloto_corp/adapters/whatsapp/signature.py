"""Validação de assinatura do webhook Meta (HMAC SHA-256)."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True)
class SignatureResult:
    """Resultado da validação de assinatura."""

    valid: bool
    skipped: bool = False
    error: str | None = None


def verify_meta_signature(
    raw_body: bytes,
    headers: Mapping[str, str],
    secret: str | None,
) -> SignatureResult:
    """Valida a assinatura do webhook.

    Se o secret estiver ausente, a validação é ignorada (skipped).
    """

    if not secret:
        return SignatureResult(valid=True, skipped=True)

    signature = headers.get("x-hub-signature-256")
    if not signature:
        return SignatureResult(valid=False, error="missing_signature")

    if not signature.startswith("sha256="):
        return SignatureResult(valid=False, error="invalid_signature_format")

    expected = signature.split("=", 1)[1]
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(digest, expected):
        return SignatureResult(valid=False, error="signature_mismatch")

    return SignatureResult(valid=True)
