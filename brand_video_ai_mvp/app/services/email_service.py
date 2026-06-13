"""Email delivery helpers for account verification and password reset."""

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailService:
    """Send transactional account emails, with safe development logging fallback."""

    def __init__(self) -> None:
        self.app_env = os.getenv("APP_ENV", "development").lower()
        self.smtp_host = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "587") or "587")
        self.smtp_username = os.getenv("SMTP_USERNAME", "").strip()
        self.smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()

    @property
    def is_configured(self) -> bool:
        """Return True when enough SMTP settings exist to attempt delivery."""

        return bool(self.smtp_host and self.smtp_from_email)

    def send_verification_email(self, to_email: str, verification_url: str) -> None:
        """Send or log an email verification link."""

        subject = "Verify your OmniSocial AI email"
        body = (
            "Welcome to OmniSocial AI.\n\n"
            "Verify your email address by opening this link:\n"
            f"{verification_url}\n\n"
            "This link expires in 24 hours."
        )
        self._send_or_log(to_email=to_email, subject=subject, body=body, action_url=verification_url)

    def send_password_reset_email(self, to_email: str, reset_url: str) -> None:
        """Send or log a password reset link."""

        subject = "Reset your OmniSocial AI password"
        body = (
            "We received a password reset request for your OmniSocial AI account.\n\n"
            "Reset your password by opening this link:\n"
            f"{reset_url}\n\n"
            "This link expires in 24 hours. Ignore this email if you did not request it."
        )
        self._send_or_log(to_email=to_email, subject=subject, body=body, action_url=reset_url)

    def _send_or_log(self, to_email: str, subject: str, body: str, action_url: str) -> None:
        """Send with SMTP when configured; log in development otherwise."""

        if not self.is_configured:
            if self.app_env == "development":
                logger.warning("SMTP is not configured. Development email for %s:\n%s", to_email, body)
                print(f"[DEV EMAIL] {subject} -> {to_email}\n{body}\nLink: {action_url}")
                return
            raise RuntimeError("SMTP is not configured.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.smtp_from_email
        message["To"] = to_email
        message.set_content(body)

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if self.smtp_username and self.smtp_password:
                smtp.login(self.smtp_username, self.smtp_password)
            smtp.send_message(message)
