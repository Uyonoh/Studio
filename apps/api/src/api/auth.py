"""Auth dependency: Supabase JWT verification and CurrentUser extraction."""

import logging
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from studio_core.observability import set_request_context
from studio_core.settings import get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def _get_jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = jwt.PyJWKClient(jwks_url)
    return _jwks_clients[jwks_url]


class CurrentUser(BaseModel):
    """Authenticated caller extracted from the Supabase JWT."""

    id: UUID
    email: str | None = None


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> CurrentUser:
    """Verify a Supabase-issued JWT and return the caller identity.

    Raises HTTP 401 with problem+json on invalid, expired, or missing tokens.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://studio.example.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Missing Authorization header.",
                "error_code": "UNAUTHORIZED",
            },
        )

    settings = get_settings()
    try:
        try:
            unverified_header = jwt.get_unverified_header(credentials.credentials)
            alg = unverified_header.get("alg", "HS256")
        except jwt.PyJWTError:
            alg = "HS256"

        if alg == "HS256":
            payload = jwt.decode(
                credentials.credentials,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},  # Supabase does not set a standard 'aud'
            )
        else:
            jwks_client = _get_jwks_client(settings.supabase_url)
            signing_key = jwks_client.get_signing_key_from_jwt(credentials.credentials)
            payload = jwt.decode(
                credentials.credentials,
                signing_key.key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://studio.example.com/errors/token_expired",
                "title": "Token Expired",
                "status": 401,
                "detail": "The access token has expired.",
                "error_code": "TOKEN_EXPIRED",
            },
        ) from exc
    except jwt.PyJWTError as exc:
        logger.warning("JWT decode failure: %s", exc)
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://studio.example.com/errors/invalid_token",
                "title": "Invalid Token",
                "status": 401,
                "detail": "The access token is invalid.",
                "error_code": "INVALID_TOKEN",
            },
        ) from exc
    except Exception as exc:
        logger.warning("JWT validation error: %s", exc)
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://studio.example.com/errors/invalid_token",
                "title": "Invalid Token",
                "status": 401,
                "detail": "The access token is invalid.",
                "error_code": "INVALID_TOKEN",
            },
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://studio.example.com/errors/invalid_token",
                "title": "Invalid Token",
                "status": 401,
                "detail": "Token is missing 'sub' claim.",
                "error_code": "INVALID_TOKEN",
            },
        )

    try:
        user_id = UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://studio.example.com/errors/invalid_token",
                "title": "Invalid Token",
                "status": 401,
                "detail": "Token 'sub' claim is not a valid UUID.",
                "error_code": "INVALID_TOKEN",
            },
        ) from exc

    email: str | None = payload.get("email")
    request.state.user_id = str(user_id)
    set_request_context(
        request_id=getattr(request.state, "request_id", ""),
        path=request.url.path,
        method=request.method,
        user_id=str(user_id),
    )
    return CurrentUser(id=user_id, email=email)


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
