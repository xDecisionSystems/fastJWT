"""Quick smoke tests against a running fastJWT API."""

import os
import requests

BASE_URL = os.getenv("JWT_API_URL", "http://127.0.0.1:8000")
GENERATE_KEY_URL = f"{BASE_URL}/generate-key"
VALIDATE_KEY_URL = f"{BASE_URL}/validate-key"


def _post(url: str, **kwargs) -> requests.Response:
    response = requests.post(url, **kwargs)
    response.raise_for_status()
    return response


def test_generate_key() -> str:
    response = _post(GENERATE_KEY_URL, json={"sub": "smoke-test-user"})
    data = response.json()
    api_key = data["jwt"]
    print("Generated API Key", api_key)
    print("Expires At", data["expires_at"], "\n")
    return api_key


def test_validate_key(api_key: str) -> None:
    payload = {"jwt": api_key}
    response = _post(VALIDATE_KEY_URL, json=payload)
    print("Validation response:", response.json())


if __name__ == "__main__":
    print("Using", BASE_URL)
    jwt_token = test_generate_key()
    test_validate_key(jwt_token)
