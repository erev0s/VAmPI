# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

VAmPI is an intentionally vulnerable Flask/Connexion API for API-security testing and teaching. Its behaviour is deliberately split between vulnerable (`vulnerable=1`, the default) and comparatively secure (`vulnerable=0`) modes. Preserve both modes unless the change explicitly alters that teaching surface.

## Development commands

```bash
python3 -m venv .venv
```

```bash
. .venv/bin/activate && python -m pip install -r requirements.txt
```

```bash
python3 app.py
```

The server listens on `http://127.0.0.1:5000`; Swagger UI is at `/ui/`. Initialize/reset the local SQLite database before exercising stateful endpoints:

```bash
curl http://127.0.0.1:5000/createdb
```

Run both modes with containers (secure on port 5001, vulnerable on port 5002):

```bash
docker compose up --build
```

The application has no committed test suite, test runner, linter, or single-test command. Use these repository-level validation checks after Python changes:

```bash
python3 -m compileall -q app.py config.py api_views models
```

```bash
git diff --check
```

For endpoint-level manual testing, import `openapi_specs/VAmPI.postman_collection.json` into Postman or use the Swagger UI. Set the bearer token returned from `/users/v1/login` and call `/createdb` first when a test needs seeded users or books.

## Architecture

- `app.py` is the executable entry point. It reads `vulnerable` and `tokentimetolive` environment variables into the module-level `vuln` and `alive` values used by the request handlers and JWT model logic.
- `config.py` owns the global Connexion application (`vuln_app`) and Flask-SQLAlchemy handle (`db`), configures the SQLite file at `database/database.db`, registers the OpenAPI document, and normalizes Connexion `ProblemException` responses.
- `openapi_specs/openapi3.yml` is the routing contract. Connexion dispatches each operation through its `operationId`, which points to a function in `api_views`. When adding or renaming an endpoint, update the OpenAPI operation and its handler together; keep the Postman collection aligned as well.
- `api_views/` holds HTTP-layer behaviour: `main.py` initializes the database and serves the root response; `users.py` handles registration, login, JWT validation, and user mutations; `books.py` handles book operations. `json_schemas.py` contains the JSON Schema request validation dictionaries used directly by handlers.
- `models/` defines the SQLAlchemy `User` and `Book` entities, their relationship, database queries, seeded users, and JWT encode/decode helpers. Handlers perform request validation and authorization, then delegate persistence/query work to these models.
- `/createdb` drops and recreates every table, then seeds `name1`, `name2`, and `admin`; it is intentionally destructive and is the expected reset mechanism for a local instance.

## Behavioural constraints

- Vulnerability toggles are implemented inline around the relevant operation (for example SQL injection, mass assignment, BOLA, password update, user enumeration, and ReDoS). A change to endpoint behaviour often requires equivalent updates in both `if vuln` branches.
- Authentication is a JWT passed as `Authorization: Bearer <token>`. `User.encode_auth_token()` issues the token and `api_views.users.token_validator()` parses headers before invoking `User.decode_auth_token()`.
- Database models use the shared `db` imported from `config.py`; do not create a second Flask application or SQLAlchemy instance for ordinary endpoint work.
- The OpenAPI document enables Connexion's Swagger UI and declares `models.user_model.User.decode_auth_token` as the bearer-info function. Keep import paths and operation IDs valid when moving code.
