from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidTokenError,
)

from app.core.conf.config import settings


class JwtService:
    def __init__(
        self,
    ):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_TIME

    def generate_access_token(self, user_id: int) -> str:
        now = datetime.now(timezone.utc)

        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=self.access_token_expire_minutes),
        }

        return jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.algorithm,
        )

    def get_user_id(self, token: str) -> int:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )

            user_id = payload.get("sub")

            if user_id is None:
                raise InvalidTokenError("Missing subject")

            return int(user_id)

        except ExpiredSignatureError:
            raise ValueError("Token has expired")

        except InvalidTokenError:
            raise ValueError("Invalid token")


def get_jwt_service() -> JwtService:
    return JwtService()
