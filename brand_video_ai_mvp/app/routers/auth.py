"""Authentication routes."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import ACCESS_TOKEN_EXPIRE_DAYS, create_access_token, get_current_user, hash_password, verify_password
from app.core import get_admin_emails, hash_token, normalize_datetime, send_password_reset_for_user, send_verification_for_user, utc_now
from app.database import get_db
from app.models import EmailVerificationToken, PasswordResetToken, User
from app.schemas import ForgotPasswordRequest, MessageResponse, ResetPasswordRequest, TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter()

def build_token_response(user: User, message: str | None = None) -> TokenResponse:
    """Build a JWT response for a successfully authenticated user."""

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "username": user.username},
        expires_delta=timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        message=message,
    )


@router.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a new user and return a JWT token for automatic login."""

    email = payload.email.lower().strip()
    username = payload.username.strip()

    existing_user = db.scalar(
        select(User).where(or_(User.email == email, User.username == username))
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "Email or username already exists.",
                "error_code": "USER_ALREADY_EXISTS",
            },
        )

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(payload.password),
        email_verified=False,
        role="admin" if email in get_admin_emails() else "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        send_verification_for_user(user, db)
    except Exception as exc:  # noqa: BLE001 - return a structured account-delivery error.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "detail": "Account was created, but the verification email could not be sent. Please contact support or try resending verification later.",
                "error_code": "EMAIL_DELIVERY_FAILED",
            },
        ) from exc
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return build_token_response(
        user,
        message="Account created. Please verify your email using the link sent to you.",
    )


@router.post("/api/auth/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Login with email and password and return a JWT token."""

    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "Email or password is incorrect.",
                "error_code": "INVALID_CREDENTIALS",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return build_token_response(user)


@router.post("/api/auth/logout")
def logout_user(_current_user: User = Depends(get_current_user)) -> dict[str, str]:
    """JWT logout is handled by the frontend deleting its stored token."""

    return {"message": "logout success"}


@router.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""

    return UserResponse.model_validate(current_user)


@router.post("/api/auth/resend-verification", response_model=MessageResponse)
def resend_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Resend email verification link for the current user."""

    if current_user.email_verified:
        return MessageResponse(message="Email is already verified.")

    send_verification_for_user(current_user, db)
    return MessageResponse(message="Verification email sent.")


@router.get("/api/auth/verify-email", response_model=MessageResponse)
def verify_email(token: str = Query(..., min_length=16), db: Session = Depends(get_db)) -> MessageResponse:
    """Verify a user email with a one-time token."""

    token_record = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_token(token))
    )
    if token_record is None or token_record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Verification token is invalid.", "error_code": "INVALID_VERIFICATION_TOKEN"},
        )

    if normalize_datetime(token_record.expires_at) < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Verification token has expired.", "error_code": "VERIFICATION_TOKEN_EXPIRED"},
        )

    user = db.get(User, token_record.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Verification token user was not found.", "error_code": "USER_NOT_FOUND"},
        )

    token_record.used_at = utc_now()
    user.email_verified = True
    user.email_verified_at = utc_now()
    db.commit()
    return MessageResponse(message="Email verified successfully.")


@router.post("/api/auth/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Request a password reset link without revealing account existence."""

    user = db.scalar(select(User).where(User.email == payload.email.lower().strip(), User.is_active.is_(True)))
    if user:
        send_password_reset_for_user(user, db)
    return MessageResponse(message="If an account exists for that email, a reset link has been sent.")


@router.post("/api/auth/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Reset a password with a valid one-time token."""

    token_record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(payload.token))
    )
    if token_record is None or token_record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Password reset token is invalid.", "error_code": "INVALID_RESET_TOKEN"},
        )

    if normalize_datetime(token_record.expires_at) < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Password reset token has expired.", "error_code": "RESET_TOKEN_EXPIRED"},
        )

    user = db.get(User, token_record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Password reset token user was not found.", "error_code": "USER_NOT_FOUND"},
        )

    token_record.used_at = utc_now()
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return MessageResponse(message="Password has been reset successfully.")
# ==================== END AUTH ADDITION ====================


