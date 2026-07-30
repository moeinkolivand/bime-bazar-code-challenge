class UserServiceError(Exception):
    """Base class for all user/otp-related domain errors."""


class UserNotFoundError(UserServiceError):
    def __init__(self):
        super().__init__(f"User not found")


class OtpExpiredError(UserServiceError):
    def __init__(self):
        super().__init__(f"Otp has expired or does not exist")


class InvalidOtpError(UserServiceError):
    def __init__(self):
        super().__init__(f"Invalid Otp code")
