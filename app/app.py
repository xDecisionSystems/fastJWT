from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Deque, Dict, List, Literal, Optional

import jwt
import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Settings

logger = logging.getLogger(__name__)

settings = Settings()
rate_limit_lock = Lock()
request_windows: Dict[str, Deque[float]] = defaultdict(deque)
stored_results: List[dict] = []

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
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            body_size = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid content-length header"},
            )
        if body_size > settings.max_request_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large"},
            )

    client_host = request.client.host if request.client else "unknown"
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


class ResultSubmission(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=128)
    score: float = Field(..., ge=0, le=1_000_000)
    submitted_at: datetime
    metadata: Dict[str, str] = Field(default_factory=dict)


class SubmissionResponse(BaseModel):
    status: Literal["stored"]
    record_id: int


@app.post("/generate-key", response_model=TokenResponse)
async def generate_key(payload: TokenCreateRequest):
    token, expires_at = _create_token(payload.sub)
    logger.debug("Generated JWT expiring at %s", expires_at.isoformat())
    return TokenResponse(jwt=token, expires_at=expires_at)


@app.post("/validate-key", response_model=ValidationResponse)
async def validate_key(payload: TokenRequest):
    status, decoded = _validate_token(payload.jwt)
    expires_at = decoded.get("exp") if decoded else None
    subject = decoded.get("sub") if decoded else None
    return ValidationResponse(status=status, expires_at=expires_at, subject=subject)


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


@app.post("/submit-results", response_model=SubmissionResponse)
async def submit_results(payload: ResultSubmission, request: Request):
    bearer_token = _extract_bearer_token(request.headers.get("Authorization"))
    if not bearer_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token",
        )

    status_value, decoded = _validate_token(bearer_token)
    if status_value != "valid" or not decoded:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token {status_value}",
        )

    record = payload.dict()
    record["subject"] = decoded["sub"]
    stored_results.append(record)
    return SubmissionResponse(status="stored", record_id=len(stored_results) - 1)


@app.get("/health")
async def health():
    return {"status": "ok"}


def configure_logging() -> None:
    """Initialize logging only when the module is run as a script."""
    logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    configure_logging()
