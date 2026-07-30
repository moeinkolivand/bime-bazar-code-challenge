import secrets

from app.modules.user.repository.otp_repository import (
    OtpFallbackRepository,
    OtpRedisRepository,
)
from app.modules.user.services.otp_generator import OTPGenerator


class OtpService:
    def __init__(self, otp_repo: OtpFallbackRepository, otp_generator: OTPGenerator):
        self.otp_repo = otp_repo
        self.otp_generator = otp_generator

    def get_otp(self, phone_number: str) -> str | None:
        return self.otp_repo.get_otp(phone_number)

    def has_active_otp(self, phone_number: str) -> bool:
        return self.otp_repo.exists(phone_number)

    def generate_otp(self, phone_number: str) -> str:
        code = self.otp_generator.generate()
        self.otp_repo.save_otp(phone_number, code)
        return code

    def verify_otp(self, phone_number: str, code: str) -> bool:
        stored_code = self.otp_repo.get_otp(phone_number)
        if stored_code is None:
            return False
        if secrets.compare_digest(stored_code.strip(), code.strip()):
            self.otp_repo.verify_and_consume(phone_number, code)
            return True
        return False
