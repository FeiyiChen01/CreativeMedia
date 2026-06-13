"""Pydantic schemas for authentication, questionnaire, and social accounts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserRegister(BaseModel):
    """Request body for registering a new user."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """Allow simple usernames that are safe to display and query."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Username cannot be empty.")
        if not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens.")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """Require at least 1 uppercase, 1 lowercase, and 1 digit."""

        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number.")
        return value

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "UserRegister":
        """Ensure password and confirmation match."""

        if self.password != self.password_confirm:
            raise ValueError("Password confirmation does not match.")
        return self


class UserLogin(BaseModel):
    """Request body for logging in."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Safe user payload returned to the frontend. Password hashes are excluded."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT response returned after register/login."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


class QuestionnaireRequest(BaseModel):
    """Brand questionnaire stored per user after registration/onboarding."""

    brand_name: str = Field(..., min_length=1, max_length=255)
    brand_description: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1, max_length=500)
    video_style: str = Field(..., min_length=1, max_length=100)
    additional_info: dict[str, Any] | None = None


class QuestionnaireResponse(BaseModel):
    """Questionnaire record returned from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    brand_name: str | None = None
    brand_description: str | None = None
    target_audience: str | None = None
    video_style: str | None = None
    additional_info: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class SocialAccountRequest(BaseModel):
    """Manual social account binding. OAuth can be added later."""

    platform: Literal["instagram", "tiktok", "youtube", "facebook", "x", "linkedin"]
    account_url: str | None = Field(default=None, max_length=500)
    account_handle: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_url_or_handle(self) -> "SocialAccountRequest":
        """Require at least one identifier for a linked social account."""

        if not self.account_url and not self.account_handle:
            raise ValueError("Please provide either account_url or account_handle.")
        return self


class SocialAccountResponse(BaseModel):
    """Stored social media account returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    platform: str
    account_url: str | None = None
    account_handle: str | None = None
    linked_at: datetime
