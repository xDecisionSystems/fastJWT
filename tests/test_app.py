import os
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789012345")
os.environ.setdefault("JWT_ISSUER", "fastjwt-api")
os.environ.setdefault("JWT_AUDIENCE", "fastjwt-clients")

from app.app import app


client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_key_returns_token():
    response = client.post("/generate-key", json={"sub": "user-123"})
    assert response.status_code == 200
    body = response.json()
    assert "jwt" in body and body["jwt"]
    assert "expires_at" in body


def test_validate_key_succeeds():
    token = client.post("/generate-key", json={"sub": "user-123"}).json()["jwt"]
    response = client.post("/validate-key", json={"jwt": token})
    assert response.status_code == 200
    assert response.json()["status"] == "valid"
    assert response.json()["expires_at"]
    assert response.json()["subject"] == "user-123"


def test_validate_key_missing_token_errors():
    response = client.post("/validate-key", json={})
    assert response.status_code == 422


def test_validate_key_invalid_jwt_returns_invalid_status():
    response = client.post("/validate-key", json={"jwt": "not-a-token"})
    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    assert response.json()["expires_at"] is None
    assert response.json()["subject"] is None


def test_validate_key_expired_jwt_returns_expired_status():
    expired_token = jwt.encode(
        {
            "iss": os.environ["JWT_ISSUER"],
            "aud": os.environ["JWT_AUDIENCE"],
            "sub": "user-123",
            "exp": datetime.utcnow() - timedelta(minutes=5),
            "iat": datetime.utcnow(),
        },
        os.environ["SECRET_KEY"],
        algorithm="HS256",
    )
    response = client.post("/validate-key", json={"jwt": expired_token})
    assert response.status_code == 200
    assert response.json()["status"] == "expired"
    assert response.json()["expires_at"] is None
    assert response.json()["subject"] is None


def test_validate_key_wrong_issuer_returns_invalid_status():
    token = jwt.encode(
        {
            "iss": "unexpected-issuer",
            "aud": os.environ["JWT_AUDIENCE"],
            "sub": "user-123",
            "exp": datetime.utcnow() + timedelta(minutes=10),
            "iat": datetime.utcnow(),
        },
        os.environ["SECRET_KEY"],
        algorithm="HS256",
    )
    response = client.post("/validate-key", json={"jwt": token})
    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
