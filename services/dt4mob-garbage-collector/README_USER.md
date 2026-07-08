# dt4mob-garbage-collector — User Manual

## What is it?

`dt4mob-garbage-collector` is a batch job that periodically cleans up expired digital twins from [Eclipse Ditto](https://www.eclipse.org/ditto/). It connects to Ditto, searches for things whose `attributes/expiry_ts` timestamp is in the past, and deletes them.

It is designed to run as a **Kubernetes CronJob** (default: every 5 minutes), but can also be run locally with Docker or Python.

---

## Prerequisites

- An **Eclipse Ditto** instance (with Thing Search enabled)
- An **OIDC-compatible authentication server** (e.g., Keycloak) with a client able to issue tokens via the **password grant** flow
- For local execution: Python 3.13 + [uv](https://docs.astral.sh/uv/) or Docker

---

## Configuration

All configuration is via environment variables. Nested keys use `__` as a delimiter (e.g., `DITTO__API_URL`).

### General

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Logging level: `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG` |

### Ditto Connection

| Variable | Default | Description |
|---|---|---|
| `DITTO__API_URL` | `http://localhost:8080` | Ditto API base URL |
| `DITTO__BASE_API_PATH` | `/api/2` | REST API path prefix |
| `DITTO__BASE_WS_PATH` | `/ws/2` | WebSocket path prefix |
| `DITTO__SEARCH_SIZE` | `200` | Page size for search results |

### Authentication (OIDC)

| Variable | Default | Description |
|---|---|---|
| `AUTH__TOKEN_ENDPOINT` | `https://localhost:8443/auth/realms/dt4mob/protocol/openid-connect/token` | OIDC token endpoint |
| `AUTH__USERNAME` | — | Username (mutually exclusive with `AUTH__USERNAME_FILE`) |
| `AUTH__USERNAME_FILE` | — | Path to file containing username |
| `AUTH__PASSWORD` | — | Password (mutually exclusive with `AUTH__PASSWORD_FILE`) |
| `AUTH__PASSWORD_FILE` | — | Path to file containing password |
| `AUTH__CLIENT_ID` | `ditto` | OIDC client ID |
| `AUTH__CA_CRT_FILE` | — | Path to CA certificate file for OIDC server TLS |

> **One of `AUTH__USERNAME` or `AUTH__USERNAME_FILE` must be set** (same for password). They are mutually exclusive.

---

## Deployment

### Option 1: Local with Docker

```bash
# Build
docker build -t dt4mob-garbage-collector:latest .

# Run with a .env file
docker run --env-file .env dt4mob-garbage-collector:latest
```

### Option 2: Local with Python + uv

```bash
# Install dependencies
uv sync --locked

# Run
uv run main.py
```

### Option 3: Kubernetes via Helm

The project includes a Helm chart at `charts/dt4mob-garbage-collector/`.

```bash
# Install (from the charts directory)
helm install garbage-collector ./charts/dt4mob-garbage-collector

# Install with custom values
helm install garbage-collector ./charts/dt4mob-garbage-collector \
  --set config.ditto.apiUrl=ditto-gateway:8080 \
  --set config.auth.tokenEndpoint=https://keycloak/auth/realms/dt4mob/protocol/openid-connect/token
```

**Helm values reference:**

| Value | Default | Description |
|---|---|---|
| `image.repository` | `atnog-harbor.av.it.pt/dt4mob/garbage-collector` | Container image |
| `image.tag` | `latest` | Image tag |
| `image.imagePullPolicy` | `Always` | Pull policy |
| `config.schedule` | `*/5 * * * *` | Cron schedule |
| `config.logLevel` | `INFO` | Log level |
| `config.ditto.apiUrl` | `ditto-gateway:8080` | Ditto API URL |
| `config.ditto.baseApiPath` | `/api/2` | Ditto REST path |
| `config.ditto.baseWsPath` | `/ws/2` | Ditto WebSocket path |
| `config.auth.tokenEndpoint` | `https://dt4mob-keycloak:8443/auth/realms/dt4mob/protocol/openid-connect/token` | OIDC token endpoint |
| `config.auth.existingSecret` | `""` | Name of existing Kubernetes Secret (if empty, chart creates one) |
| `config.auth.caSecret` | `""` | Name of Secret containing CA certificate (key: `ca.crt`) |

**Credentials in Kubernetes:**

If `config.auth.existingSecret` is empty and a password is provided, the chart creates a Secret containing the username and password. You can also pre-create a Secret with keys `username` and `password` and reference it via `config.auth.existingSecret`.

---

## How It Works

1. The script opens a **WebSocket** connection to Ditto and authenticates with a JWT Bearer token.
2. It starts a background task that **refreshes the token** before it expires, sending the new token to Ditto via a control message.
3. It queries the Ditto **REST search API** for things where `lt(attributes/expiry_ts,'<current_time>')` — i.e., things whose expiry timestamp is in the past.
4. For each expired thing, it builds a **Ditto Protocol delete command** envelope.
5. It sends each delete command over the **WebSocket** connection and waits for a success response (status 200 or 204).
6. Once all deletions are confirmed, the script **exits**.
7. The **CronJob** (or other scheduler) triggers the next run according to the configured schedule.

---

## Monitoring & Logs

**Docker:**
```bash
docker logs <container_id>
```

**Kubernetes:**
```bash
# List CronJob and its Jobs
kubectl get cj,garbage-collector
kubectl get jobs -l app.kubernetes.io/name=garbage-collector

# View logs from the last run
kubectl logs job/<job_name>
```

Log output includes info on:
- Number of expired things found
- Each delete command sent and its result
- Token refresh events
- Connection lifecycle

---

## Troubleshooting

| Problem | Likely cause | Check |
|---|---|---|
| Script fails to connect | Ditto URL wrong or unreachable | Verify `DITTO__API_URL` and network connectivity |
| Authentication fails | OIDC credentials wrong or expired | Verify `AUTH__USERNAME`/`AUTH__PASSWORD` and `AUTH__TOKEN_ENDPOINT` |
| No things deleted | No expired things, or `expiry_ts` attribute missing on things | Check Ditto things and verify the attribute path |
| Token refresh errors | OIDC token endpoint unreachable or TLS issue | Check `AUTH__CA_CRT_FILE` if using custom CA |
| Helm install fails | Missing required values | Check that username/password or `existingSecret` is provided |
