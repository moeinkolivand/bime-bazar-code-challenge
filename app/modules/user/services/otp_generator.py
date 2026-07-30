import secrets
from datetime import datetime, timedelta


class OTPGenerator:
    """
    responsible for generating and validating OTPs.
    This is pure business logic with no external dependencies.
    """

    def __init__(self, expiry_seconds: int = 300):
        self.expiry_seconds: int = expiry_seconds

    def generate(self) -> str:
        """
        Generate a secure OTP code.
        Uses `secrets` module for cryptographically strong randomness.
        """
        return str(secrets.randbelow(900000) + 100000)

    def get_expiry_time(self) -> datetime:
        return datetime.now() + timedelta(seconds=self.expiry_seconds)

    def is_expired(self, expires_at: datetime) -> bool:
        return datetime.now() > expires_at

    def verify(self, input_code: str, stored_code: str, expires_at: datetime) -> bool:
        """
        Verify an OTP code against the stored code and expiry time.
        Uses constant-time comparison to prevent timing attacks.
        """
        if self.is_expired(expires_at):
            return False

        return secrets.compare_digest(input_code.strip(), stored_code.strip())
