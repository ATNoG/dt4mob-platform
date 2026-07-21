# User Manual — Ditto Events API

## 1. Introduction

The **Ditto Events API** (`dt4mob-historical-api`) is a FastAPI service that exposes a REST interface for querying, inserting, and deleting historical events produced by **Eclipse Ditto**. Events are stored in a **TimescaleDB** hypertable, enabling efficient time-series queries, JSONPath projections, and time-bucketed aggregations.

This service is part of the **DT4Mob** platform and is deployed alongside `dt4mob-historical-writer`, which ingests events from Kafka into the same database.

---

## 2. Configuration

All configuration is done via environment variables. A `.env` file in the working directory is also supported.

### 2.1 General

| Variable | Required | Default | Description |
|---|---|---|---|
| `LOG_LEVEL` | No | `INFO` | Logging level (`CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`) |

### 2.2 Authentication (Keycloak OIDC)

| Variable | Required | Default | Description |
|---|---|---|---|
| `AUTH__CLIENT_ID` | Yes | — | Keycloak client ID |
| `AUTH__AUDIENCE` | No | `account` | OIDC audience |
| `AUTH__SERVER_URI` | Yes | — | Keycloak realm URI (e.g. `https://keycloak.example.com/realms/myrealm`) |
| `AUTH__ISSUER` | Yes | — | OIDC issuer URL (can be a list: `["url1","url2"]`) |
| `AUTH__SIGNATURE_CACHE_TTL` | No | `3600` | JWT signature cache TTL in seconds |
| `AUTH__READ_ROLE` | No | `["historical-read"]` | Required Keycloak role(s) for read endpoints |
| `AUTH__WRITE_ROLE` | No | `["historical-write"]` | Required Keycloak role(s) for write endpoints |

### 2.3 TimescaleDB

| Variable | Required | Default | Description |
|---|---|---|---|
| `TIMESCALE__CONNECTION` | Yes | — | Connection URI (e.g. `postgresql://user:pass@host:5432/db`) |
| `TIMESCALE__DATABASE_TIMEZONE` | No | `Europe/Lisbon` | Database timezone |

### 2.4 Nested Config Delimiter

The double-underscore `__` separator is used by `pydantic-settings` to nest variables.  
For example: `AUTH__CLIENT_ID` maps to `settings.auth.client_id`.

---

## 3. Running Locally

### 3.1 Prerequisites

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv/) package manager
- A running TimescaleDB instance

### 3.2 Setup

```bash
# Clone the repository and enter the service directory
cd services/dt4mob-historical-api

# Install dependencies
uv sync

# Create a .env file with the required variables (see §2)
# Example:
#   LOG_LEVEL=DEBUG
#   AUTH__CLIENT_ID=my-client
#   AUTH__SERVER_URI=https://keycloak.example.com/realms/myrealm
#   AUTH__ISSUER=https://keycloak.example.com/realms/myrealm
#   TIMESCALE__CONNECTION=postgresql://user:pass@localhost:5432/historical
```

### 3.3 Run

```bash
# Development (auto-reload)
uv run fastapi dev app/main.py --port 8080

# Production
uv run fastapi run app/main.py --port 8080 --host 0.0.0.0
```

The API will be available at `http://localhost:8080/historic/`.  
Swagger UI is served at the root path.

---

## 4. Running with Docker

### 4.1 Build

```bash
docker build -t data-lake-api -f dockerfile .
```

### 4.2 Run

```bash
docker run -p 8080:8080 \
  -e LOG_LEVEL=INFO \
  -e AUTH__CLIENT_ID=my-client \
  -e AUTH__SERVER_URI=https://keycloak.example.com/realms/myrealm \
  -e AUTH__ISSUER=https://keycloak.example.com/realms/myrealm \
  -e TIMESCALE__CONNECTION=postgresql://user:pass@host:5432/db \
  data-lake-api
```

---

## 5. API Endpoints

All endpoints are mounted under the `/historic` root path.  
Read endpoints require the `historical-read` role; write endpoints require `historical-write`.

| Method | Path | Description | Auth Role |
|---|---|---|---|
| `GET` | `/historic/` | Swagger UI (custom HTML) | None |
| `GET` | `/historic/things` | List distinct thing IDs | `historical-read` |
| `GET` | `/historic/events/{thing_id}/paths` | List distinct (path, action) pairs for a thing | `historical-read` |
| `GET` | `/historic/events` | Query events with filters | `historical-read` |
| `GET` | `/historic/events/{thing_id}` | Query events by thing ID | `historical-read` |
| `POST` | `/historic/events` | Insert events | `historical-write` |
| `DELETE` | `/historic/events/{thing_id}` | Delete events in a time range | `historical-write` |
| `GET` | `/historic/events/projection/{thing_id}` | Extract fields via JSONPath | `historical-read` |
| `GET` | `/historic/events/time-buckets/{thing_id}` | Time-bucketed aggregations | `historical-read` |

### 5.1 `GET /historic/things`

Returns all distinct `thing_id` values, optionally filtered by prefix.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `thing_id_prefix` | `str` | No | Filter things whose ID starts with this prefix |

### 5.2 `GET /historic/events/{thing_id}/paths`

Returns distinct (path, action) pairs for a given thing within a time range.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `since` | `datetime` (ISO 8601) | Yes | Start of time range |
| `until` | `datetime` (ISO 8601) | No | End of time range (defaults to now) |

### 5.3 `GET /historic/events`

Queries events across all things with multiple filters.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `since` | `datetime` | Yes | Start of time range |
| `until` | `datetime` | No | End of time range (defaults to now) |
| `thing_id_prefix` | `str` | No | Filter by thing ID prefix |
| `path_prefix` | `str` | No | Filter by path prefix |
| `action` | `enum` | No | Filter by action (`created`, `modified`, `deleted`, `merged`) |

### 5.4 `GET /historic/events/{thing_id}`

Queries events for a specific thing.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `since` | `datetime` | Yes | Start of time range |
| `until` | `datetime` | No | End of time range (defaults to now) |
| `path_prefix` | `str` | No | Filter by path prefix |
| `action` | `enum` | No | Filter by action |

### 5.5 `POST /historic/events`

Inserts one or more events directly (alternative to Kafka ingestion).

**Request body:** JSON object with an `events` array:

```json
{
  "events": [
    {
      "time": "2024-01-01T00:00:00Z",
      "thing_id": "org.eclipse.ditto:my-thing",
      "action": "modified",
      "path": "/features/temperature/properties/value",
      "revision": 1,
      "value": 25.5
    }
  ]
}
```

### 5.6 `DELETE /historic/events/{thing_id}`

Deletes events for a given thing within a time range.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `since` | `datetime` | Yes | Start of time range |
| `until` | `datetime` | Yes | End of time range |

### 5.7 `GET /historic/events/projection/{thing_id}`

Extracts specific fields from JSON event `value` using a JSONPath expression.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `json_path` | `str` | Yes | JSONPath expression (e.g. `$.temperature`) |
| `since` | `datetime` | Yes | Start of time range |
| `until` | `datetime` | No | End of time range (defaults to now) |
| `path_prefix` | `str` | No | Filter by path prefix |

### 5.8 `GET /historic/events/time-buckets/{thing_id}`

Groups events into time buckets and runs aggregations on a JSONPath target.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `json_path` | `str` | Yes | JSONPath to the value to aggregate |
| `since` | `datetime` | Yes | Start of time range |
| `until` | `datetime` | Yes | End of time range |
| `bucket_minutes` | `int` | No | Bucket width in minutes (omit or `<=0` for a single bucket) |
| `agg_type` | `enum` | No | Aggregation function: `count`, `sum`, `avg`, `min`, `max` (default: `count`) |
| `path_prefix` | `str` | No | Comma-separated path prefixes to segment results |

**Note:** When `path_prefix` contains multiple comma-separated values, the endpoint uses `get_events_custom_time_buckets_with_path` which groups results by path as well.

---

## 6. Authentication

The API uses **Keycloak OIDC** (OpenID Connect) for authentication. The `fastapi-oidc` middleware validates JWT tokens on every request.

- Read endpoints require the `historical-read` role (configurable via `AUTH__READ_ROLE`).
- Write endpoints require the `historical-write` role (configurable via `AUTH__WRITE_ROLE`).

To access the API, include a Bearer token in the `Authorization` header:

```
Authorization: Bearer <your-keycloak-jwt-token>
```

---

## 7. Deployment

### 7.1 Kubernetes (Helm)

Both the API and writer services are deployed together via a single Helm chart located at `charts/dt4mob-historical/`.

**Key resources created by the chart:**

| Resource | Kind | Description |
|---|---|---|
| `api-deployment.yaml` | `Deployment` | Runs the API container on port 8080 |
| `api-service.yaml` | `Service` | Exposes the API on port 8080 |
| `writer-deployment.yaml` | `Deployment` | Runs the writer (Kafka consumer) |
| `writer-config.yaml` | `ConfigMap` | Kafka and TimescaleDB config for the writer |
| `kafka-topic.yaml` | `KafkaTopic` (Strimzi) | Topic for Ditto events |
| `timescale-cluster.yaml` | `Cluster` (CNPG) | PostgreSQL + TimescaleDB cluster |

**Container images** (pushed to `atnog-harbor.av.it.pt/dt4mob/`):
- API: `data-lake-api`
- Writer: `data-gateway`

The API is exposed via an ingress that routes `/historic` to the API service.

### 7.2 Environment Variables for Deploy

In the Helm chart, authentication variables are set directly on the deployment, while `TIMESCALE__CONNECTION` is injected via a Kubernetes Secret for security.
