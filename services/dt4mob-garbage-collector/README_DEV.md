# dt4mob-garbage-collector — Developer Documentation

## Overview

`dt4mob-garbage-collector` is a standalone Python batch job that connects to [Eclipse Ditto](https://www.eclipse.org/ditto/) via WebSocket and REST API, searches for digital twins whose `attributes/expiry_ts` has elapsed, and deletes them by sending Ditto protocol `delete` commands.

It runs to completion and exits, designed to be scheduled as a **Kubernetes CronJob** (or any periodic scheduler).

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.13 |
| Package manager | [uv](https://docs.astral.sh/uv/) (Astral) |
| Async runtime | `asyncio` (stdlib) |
| WebSocket client | `websockets` 16.0 |
| HTTP client | `httpx` 0.28.1 (async) |
| Configuration | `pydantic-settings` 2.13.0 |
| Data validation | `pydantic` 2.12.5 |
| Deployment | Docker (Alpine) + Helm (Kubernetes CronJob) |

---

## Project Structure

```
dt4mob-garbage-collector/
├── main.py                                  # Entry point
├── pyproject.toml                           # Project metadata & dependencies
├── uv.lock                                  # Locked dependency versions
├── Dockerfile                               # Container build
├── .python-version                          # Python version pin
├── README_DEV.md
├── README_USER.md
└── src/
    ├── models/
    │   ├── __init__.py
    │   └── ditto.py                         # Pydantic models (SearchResponse, DittoProtocolEnvelope, etc.)
    ├── services/
    │   ├── auth/
    │   │   └── __init__.py                 # AuthenticationService (OIDC password grant)
    │   ├── ditto_api/
    │   │   ├── __init__.py                 # DittoClient singleton factory
    │   │   └── ditto_api.py                # DittoClient (WebSocket + REST)
    │   ├── envelope_formatter/
    │   │   └── ditto_thing/
    │   │       ├── __init__.py             # DittoThingEnvelopeFormatter singleton factory
    │   │       └── DittoProtocol.py        # DittoProtocolEnvelope builder
    │   └── garbage_collector/
    │       ├── __init__.py                 # GarbageCollector singleton factory
    │       └── garbage_collector.py        # GarbageCollector orchestration
    └── settings/
        ├── __init__.py                     # Settings (pydantic-settings root)
        ├── auth.py                         # AuthSettings
        └── ditto.py                        # DittoSettings
```

External to this directory:

```
charts/dt4mob-garbage-collector/             # Helm chart
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl
    ├── garbage-collector-job.yaml           # CronJob definition
    └── garbage-collector-secret.yaml        # Secret for credentials
```

---

## Architecture & Data Flow

```
main.py
  │
  ├── ditto_client.connect()                 # WebSocket handshake + JWT auth
  │     └── background tasks:
  │           ├── _listen_loop()             # reads WS messages, resolves futures
  │           └── _token_refresh_loop()      # refreshes JWT before expiry
  │
  ├── garbage_collector.get_expired_envelops()
  │     │
  │     ├── ditto_client.get_things_expired_lt(now)
  │     │     └── REST GET /api/2/search/things?filter=lt(attributes/expiry_ts,'...')
  │     │         (paginated via cursor parameter)
  │     │
  │     └── for each thing ID:
  │           └── formatter.delete_message(id)
  │                 └── DittoProtocolEnvelope { topic, headers, path }
  │
  ├── for each envelope:
  │     └── ditto_client.send_ws_message(msg)   # sends JSON over WS, waits for ACK
  │
  └── ditto_client.close()
```

---

## Implementation Details

### Singleton Pattern

Each service module exposes a module-level singleton via a `_new_instance()` factory:

- `src/services/auth/__init__.py` → `auth_service`
- `src/services/ditto_api/__init__.py` → `ditto_client`
- `src/services/envelope_formatter/ditto_thing/__init__.py` → `envelop_formater`
- `src/services/garbage_collector/__init__.py` → `garbage_collector`

Dependencies are resolved at construction time and passed to downstream consumers.

### WebSocket & Token Lifecycle

1. `DittoClient.connect()` opens a WebSocket to `{ws_url}/?x-csrf-token=no-csrf-check`.
2. Sends `START-SEND-EVENTS` control message.
3. Starts two background `asyncio` tasks:
   - **`_listen_loop()`**: reads every incoming message. If the message is a JSON response with a `correlation-id`, it resolves the corresponding future in `_responses`. Non-JSON control messages are logged.
   - **`_token_refresh_loop()`**: calculates remaining token lifetime, sleeps until 5 seconds before expiry, obtains a new token from the OIDC endpoint, and sends it as a control message: `JWT-TOKEN?jwtToken=<new_token>`.

### Correlation-id Response Matching

Each outgoing envelope carries a UUID in `headers.correlation-id`. The sender stores a future keyed by this UUID. The listen loop matches incoming responses by the same `correlation-id` and resolves the future, enabling reliable send-and-await semantics over WebSocket.

### Pagination

`get_things_expired_lt()` performs a paginated search using Ditto's cursor mechanism. It requests `DittoSettings.search_size` items per page (default 200, max 500 hard-coded). The loop continues until no cursor is returned.

### Garbage Collection Loop

In `main.py`, after obtaining the list of delete envelopes, the script iterates through them sending each one via WebSocket. The outer `while` loop re-fetches expired things after each batch and continues until fewer than 5 envelopes remain, catching any new expirations since the script started.

---

## Dependencies

### Direct

| Package | Version | Purpose |
|---|---|---|
| `httpx` | >=0.28.1 | Async HTTP client for Ditto REST API |
| `pydantic` | >=2.12.5 | Data validation & models |
| `pydantic-settings` | >=2.13.0 | Environment-variable-based config |
| `websockets` | >=16.0 | Async WebSocket client |

### Transitive

`annotated-types`, `anyio`, `certifi`, `h11`, `httpcore`, `idna`, `pydantic-core`, `python-dotenv`, `typing-extensions`, `typing-inspection`.

---

## Configuration

All settings are loaded via `pydantic-settings` from environment variables using `__` as a nested delimiter. See `README_USER.md` for the full table of environment variables.

---

## Development Setup

```bash
# Clone and enter the directory
cd services/dt4mob-garbage-collector

# Install uv if not installed (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --locked

# Run
uv run main.py
```

For local run, provide environment variables (via `.env` file or inline):

```bash
DITTO__API_URL=http://localhost:8080 \
AUTH__TOKEN_ENDPOINT=https://keycloak/auth/realms/dt4mob/protocol/openid-connect/token \
AUTH__USERNAME=myuser \
AUTH__PASSWORD=mypass \
uv run main.py
```

---

## Building

```bash
docker build -t dt4mob-garbage-collector:latest .
```

The Dockerfile uses `alpine:edge` with Python 3.13, copies `uv` from `astral/uv:latest`, installs build dependencies, runs `uv sync --locked`, and sets `CMD ["uv","run","main.py"]`.
