from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from app.core.settings import get_settings
from app.features.auth.schemas import AccessTokenPayload

password_hash = PasswordHash.recommended()
oauth2_password_bearer = OAuth2PasswordBearer(
    tokenUrl="/api/auth/token",
    auto_error=False,
)
REFRESH_COOKIE_NAME = "refresh_token"


def hash_password(value: str) -> str:
    return password_hash.hash(value)


def verify_password(value: str, password_hash_value: str) -> bool:
    return password_hash.verify(value, password_hash_value)


def create_access_token(user_id: int, username: str, roles: list[str]) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(
    token: str | None,
) -> AccessTokenPayload:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
        )

    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=["HS256"],
        )
        return AccessTokenPayload(**payload)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
        ) from exc
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc


def set_refresh_cookie(
    response: Response,
    raw_token: str,
    remember_me: bool,
) -> None:
    settings = get_settings()
    max_age = settings.refresh_token_expire_days * 24 * 60 * 60 if remember_me else None
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=max_age,
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/auth")
