"""Small token encryption helper for OAuth credentials.

Tokens are encrypted before they are stored in the database. The encryption key
is derived from TOKEN_ENCRYPTION_KEY so deployments can rotate it through env.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


class TokenCryptoError(RuntimeError):
    """Raised when OAuth tokens cannot be encrypted or decrypted."""


def _is_production() -> bool:
    """Return whether the app is running with production safety rules."""

    return os.getenv("APP_ENV", "development").lower() == "production"


def _get_fernet() -> Fernet:
    """Build a Fernet instance from TOKEN_ENCRYPTION_KEY."""

    raw_key = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        message = "TOKEN_ENCRYPTION_KEY is required before saving OAuth tokens."
        if _is_production():
            raise TokenCryptoError(message)
        raise TokenCryptoError(f"{message} Set it in .env for local YouTube OAuth testing.")

    # Accept either a Fernet key or a normal secret phrase and derive a stable key.
    try:
        return Fernet(raw_key.encode("utf-8"))
    except ValueError:
        digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(token: str | None) -> str | None:
    """Encrypt a token string for database storage."""

    if not token:
        return None
    return _get_fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str | None) -> str | None:
    """Decrypt a token string that was previously encrypted for storage."""

    if not encrypted_token:
        return None
    try:
        return _get_fernet().decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise TokenCryptoError("Stored OAuth token could not be decrypted.") from exc
