"""
Cryptographic signature verification for inbound webhooks.
"""

import hmac
import hashlib
from typing import Optional


def compute_signature(payload_bytes: bytes, secret: str) -> str:
    """Computes hexadecimal HMAC-SHA256 digest of payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def verify_signature(payload_bytes: bytes, signature_header: Optional[str], secret: str) -> bool:
    """
    Verifies payload signature using constant-time comparison to prevent timing attacks.
    Expected header format: 'sha256=<hex_digest>' or raw '<hex_digest>'.
    """
    if not signature_header or not secret:
        return False

    raw_signature = signature_header.strip()
    if raw_signature.startswith("sha256="):
        raw_signature = raw_signature[7:]

    expected = compute_signature(payload_bytes, secret)
    return hmac.compare_digest(raw_signature.lower(), expected.lower())
