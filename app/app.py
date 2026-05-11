from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Deque, Dict, Literal, Optional

import jwt
import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Settings

logger = logging.getLogger(__name__)

MAX_REQUEST_BYTES = 8_192

settings = Settings()
rate_limit_lock = Lock()
request_windows: Dict[str, Deque[float]] = defaultdict(deque)

app = FastAPI(title="fastJWT", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def _enforce_rate_limit(client_key: str) -> None:
    """Simple in-memory fixed-window rate limiting by client key."""
    if settings.rate_limit_requests <= 0:
        return

    now = datetime.now(tz=timezone.utc).timestamp()
    cutoff = now - settings.rate_limit_window_seconds

    with rate_limit_lock:
        timestamps = request_windows[client_key]
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()
        if len(timestamps) >= settings.rate_limit_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        timestamps.append(now)


@app.middleware("http")
async def enforce_request_size_and_rate_limit(request: Request, call_next):
    """Apply request-size and request-rate protections to API requests."""
    body = await request.body()
    if len(body) > MAX_REQUEST_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": "Request body too large"},
        )

    if request.client is None:
        logger.warning("Request received with no identifiable client address; rate-limiting under 'unknown'")
        client_host = "unknown"
    else:
        client_host = request.client.host
    try:
        _enforce_rate_limit(client_host)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


def _create_token(subject: str) -> tuple[str, datetime]:
    """Create a JWT using the configured secret and expiration window."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_expiration_minutes)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": subject,
        "exp": expires_at,
        "iat": now,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token, expires_at


def _validate_token(token: str) -> tuple[str, Optional[dict]]:
    """Decode the JWT and report whether it was valid."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        return "valid", payload
    except jwt.ExpiredSignatureError as exc:
        logger.info("Token expired: %s", exc)
        return "expired", None
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid token provided: %s", exc)
        return "invalid", None


class TokenRequest(BaseModel):
    jwt: str = Field(..., min_length=20, max_length=4096)


class TokenCreateRequest(BaseModel):
    sub: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    jwt: str
    expires_at: datetime


class ValidationResponse(BaseModel):
    status: Literal["valid", "expired", "invalid"]
    expires_at: Optional[int]
    subject: Optional[str]


@app.post("/generate-key", response_model=TokenResponse)
async def generate_key(payload: TokenCreateRequest):
    token, expires_at = _create_token(payload.sub)
    logger.debug("Generated JWT expiring at %s", expires_at.isoformat())
    return TokenResponse(jwt=token, expires_at=expires_at)


@app.post("/validate-key", response_model=ValidationResponse)
async def validate_key(payload: TokenRequest):
    token_status, decoded = _validate_token(payload.jwt)
    expires_at = decoded.get("exp") if decoded else None
    subject = decoded.get("sub") if decoded else None
    return ValidationResponse(status=token_status, expires_at=expires_at, subject=subject)


@app.get("/health")
async def health():
    return {"status": "ok"}


def configure_logging() -> None:
    """Initialize logging only when the module is run as a script."""
    logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    configure_logging()
