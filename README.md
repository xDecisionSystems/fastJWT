# fastJWT

Small FastAPI authentication service that issues and validates JSON Web Tokens (JWTs). This app is intended to be consumed by other APIs that perform business logic and database storage.

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
| `RATE_LIMIT_REQUESTS` | Max requests per client in rate-limit window (`0` disables) | `60` |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate-limit window duration in seconds | `60` |
| `JWT_API_URL` | Used by `test_app.py` when pointing at a running instance | `http://127.0.0.1:8000` |

Request body size limit is fixed at `8192` bytes in this service.

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

### `GET /health`
Used by readiness checks:
```json
{ "status": "ok" }
```

## Integration guide (React + external API)
Use this section as the source-of-truth contract when generating code with Codex/Claude.

### Architecture
1. React app authenticates the user with your backend.
2. Your backend (trusted server) requests a JWT from fastJWT using `POST /generate-key`.
3. React calls your external business API with `Authorization: Bearer <jwt>`.
4. External API validates JWT claims and signature before accepting/storing data.

### Rules for coding agents
- Do not call `POST /generate-key` directly from browser code.
- Do not expose `SECRET_KEY` in frontend code.
- Use HTTPS for all production traffic.
- Treat fastJWT as auth-only; business data is handled by another API.

### fastJWT token minting request
```http
POST /generate-key
Content-Type: application/json

{ "sub": "user-123" }
```

### Token usage from clients
```http
Authorization: Bearer <jwt>
```

### Validation contract for downstream APIs
Downstream APIs must validate all of the following:
- Algorithm: `HS256`
- Signature key: same `SECRET_KEY` used by fastJWT
- `iss` equals `JWT_ISSUER`
- `aud` equals `JWT_AUDIENCE`
- `sub` exists and maps to an allowed principal
- `exp` is not expired
- `iat` is present and reasonable for your tolerance window

### Optional introspection via fastJWT
Downstream services can call `POST /validate-key`:
- `status: "valid"` -> token accepted
- `status: "invalid"` -> reject with `401`
- `status: "expired"` -> reject with `401` and ask client to refresh session

### `JWT_ISSUER` and `JWT_AUDIENCE` explained
`JWT_ISSUER` (`iss` claim): identifies who created the token (your token service).  
Example: `fastjwt-api`.

`JWT_AUDIENCE` (`aud` claim): identifies who the token is intended for (the consuming API/service).  
Example: `fastjwt-clients` or `results-api`.

Why they matter:
- They prevent token confusion/replay across systems.
- A downstream API should reject tokens if `iss` or `aud` do not match expected values.

In your setup:
- fastJWT issues tokens with these values.
- Your external API must validate those same expected values before accepting data.

### Example environment alignment
Set these values identically on fastJWT and on downstream validators:
- `SECRET_KEY`
- `JWT_ISSUER`
- `JWT_AUDIENCE`

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
