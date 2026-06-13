"""Authentication helpers for password hashing, JWTs, and current-user loading."""

import os
import warnings
from datetime import UTC, datetime, timedelta
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").lower()
DEFAULT_JWT_SECRET = "dev-secret-key-change-in-production"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or DEFAULT_JWT_SECRET
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "7"))
WEAK_JWT_SECRETS = {
    "",
    "change-me",
    "your-secret-key-change-in-production",
    DEFAULT_JWT_SECRET,
}


def _is_weak_jwt_secret(secret: str) -> bool:
    """Return True when a JWT secret is unsuitable for production."""

    return secret.strip() in WEAK_JWT_SECRETS or len(secret.strip()) < 32


if APP_ENV == "production" and _is_weak_jwt_secret(JWT_SECRET_KEY):
    raise RuntimeError(
        "JWT_SECRET_KEY must be set to a strong unique value in production."
    )

if APP_ENV != "production" and _is_weak_jwt_secret(JWT_SECRET_KEY):
    warnings.warn(
        "Using a weak development JWT_SECRET_KEY. Set a strong JWT_SECRET_KEY before production.",
        RuntimeWarning,
        stacklevel=2,
    )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def raise_auth_error(detail: str = "Invalid or expired token.") -> None:
    """Raise a normalized 401 auth error."""

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"detail": detail, "error_code": "INVALID_TOKEN"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def hash_password(password: str) -> str:
    """Return a bcrypt hash for a plain-text password."""

    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""

    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""

    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token payload."""

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise_auth_error("Token is invalid or expired.")
        raise AssertionError("unreachable") from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise_auth_error("Token is missing the subject claim.")
    return payload


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Load the authenticated active user from a Bearer token."""

    payload = verify_token(token)
    raw_user_id = payload.get("sub")

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError) as exc:
        raise_auth_error("Token subject is invalid.")
        raise AssertionError("unreachable") from exc

    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "User not found.", "error_code": "USER_NOT_FOUND"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Require the authenticated user to be an active admin."""

    if current_user.role != "admin" or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Admin access is required.",
                "error_code": "ADMIN_REQUIRED",
            },
        )
    return current_user
