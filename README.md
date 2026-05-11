# fastJWT

Small FastAPI service that issues and validates JSON Web Tokens (JWTs) with a configurable expiration window and optional CORS filtering.

## Features
- Generate HS256-signed JWTs with a configurable expiration window
- Validate JWTs and report expiration or integrity failures
- CORS configuration driven by environment variables
- Lightweight FastAPI project with automated tests and Docker support

## Requirements
- Python 3.9+
- `pip install -r app/requirements.txt`
- Optional dependencies for development/test automation: `pip install -r requirements-dev.txt`

## Environment variables
| Variable | Description | Default |
| --- | --- | --- |
| `SECRET_KEY` | Secret used to sign and verify JWTs (required, no default) | — |
| `JWT_EXPIRATION_MINUTES` | Token lifetime in minutes | `20` |
| `JWT_ISSUER` | Expected and emitted `iss` JWT claim | `fastjwt-api` |
| `JWT_AUDIENCE` | Expected and emitted `aud` JWT claim | `fastjwt-clients` |
| `CORS_ORIGINS` | Comma-delimited whitelist for allowed origins | empty list (no browser origins allowed) |
| `MAX_REQUEST_BYTES` | Maximum accepted HTTP request body size | `1048576` |
| `RATE_LIMIT_REQUESTS` | Max requests per client in rate-limit window (`0` disables) | `60` |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate-limit window duration in seconds | `60` |
| `JWT_API_URL` | Used by `test_app.py` when pointing at a running instance | `http://127.0.0.1:8000` |

## Running locally
```bash
cd app
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```
The application listens on port 8000 inside and outside of Docker.

## API endpoints
### `POST /generate-key`
Request:
```json
{ "sub": "user-123" }
```
Response:
```json
{
  "jwt": "<token>",
  "expires_at": "2026-02-13T12:34:56.789012"
}
```
### `POST /validate-key`
Request example:
```json
{ "jwt": "<token>" }
```
Response:
```json
{ "status": "valid", "expires_at": 1700000000, "subject": "user-123" }
```
Invalid or expired tokens still return HTTP 200, but the `status` field is set to `"invalid"` or `"expired"` and `expires_at` is `null`.

### `POST /submit-results`
Requires `Authorization: Bearer <jwt>`.

Request example:
```json
{
  "task_id": "task-1",
  "score": 92.5,
  "submitted_at": "2026-02-13T12:34:56.789012",
  "metadata": {
    "source": "web"
  }
}
```

Response:
```json
{ "status": "stored", "record_id": 0 }
```

### `GET /health`
Used by readiness checks:
```json
{ "status": "ok" }
```

## Docker
Build and run with:
```bash
docker build -t fastjwt .
docker run --env-file .env -p 8000:8000 fastjwt
```
Example `docker-compose.yml` snippet:
```yaml
version: '3.9'
services:
  fastjwt:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
```

## Testing
Install dev dependencies and run pytest:
```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

## Manual smoke test script
The `test_app.py` script performs end-to-end requests against a running instance. Set `JWT_API_URL` to point at your server (default `http://127.0.0.1:8000`).
```bash
python test_app.py
```
