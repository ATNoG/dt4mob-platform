# Developer Manual — Ditto Events API

## 1. Architecture Overview

```
┌──────────────┐     ┌─────────────────────────────────┐     ┌────────────┐
│   Client     │────▶│  dt4mob-historical-api (FastAPI) │────▶│ TimescaleDB│
│  (REST)      │     │                                  │     │ (Hypertable)│
│              │◀────│  - Router → Service → SQLModel   │◀────│            │
└──────────────┘     │  - Auth: Keycloak OIDC           │     └────────────┘
                     └─────────────────────────────────┘
                                │
                     ┌──────────▼──────────┐
                     │     Keycloak        │
                     │  (JWT Validation)   │
                     └─────────────────────┘
```

The API is a **read/write REST layer** on top of TimescaleDB. It shares the same database schema as `dt4mob-historical-writer` (the Kafka ingestion service), but the two are independent processes.

---

## 2. Directory Structure

```
dt4mob-historical-api/
├── app/
│   ├── __init__.py                     # Empty
│   ├── main.py                         # FastAPI application entry point
│   ├── dependencies.py                 # Empty (reserved)
│   │
│   ├── database_engine/
│   │   ├── __init__.py                 # Engine singleton + get_session()
│   │   └── TimeScaleEngineManager.py   # SQLAlchemy engine wrapper
│   │
│   ├── models/
│   │   ├── __init__.py                 # Empty
│   │   ├── ditto_events.py            # DittoEvent SQLModel table
│   │   ├── paths_response.py          # PathResponseObject Pydantic model
│   │   └── util.py                    # Action enum
│   │
│   ├── routers/
│   │   ├── __init__.py                 # Empty
│   │   └── events.py                  # All REST API endpoints
│   │
│   ├── services/
│   │   ├── __init__.py                 # Empty
│   │   └── events_service.py          # Business logic / query building
│   │
│   ├── settings/
│   │   ├── __init__.py                 # Global Settings (combines auth + timescale)
│   │   ├── auth.py                    # AuthSettings (Keycloak)
│   │   └── timescale.py               # TimeScaleSettings (DB connection)
│   │
│   └── static/                        # Custom Swagger UI assets
│       ├── swagger-ui-bundle.js
│       ├── swagger-ui-standalone-preset.js
│       ├── swagger-ui.css
│       └── swagger-initializer.js
│
├── dockerfile                          # Production Docker image
├── pyproject.toml                      # Python dependencies
├── uv.lock                             # Lock file
├── USER_MANUAL.en.md
├── USER_MANUAL.pt.md
├── DEVELOPER_MANUAL.en.md
└── DEVELOPER_MANUAL.pt.md
```

---

## 3. Data Flow

```
HTTP Request
    │
    ▼
┌─────────────────────┐
│  FastAPI            │
│  app/main.py        │
│  root_path="/historic"│
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  OIDC Auth          │
│  (fastapi-oidc)     │
│  JWT token          │
│  validation         │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Router             │
│  app/routers/events.py│
│  - Parses params    │
│  - Injects session  │
│  - Calls service    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  EventsService      │
│  app/services/      │
│  events_service.py  │
│  - Builds SQL       │
│  - Executes queries │
│  - Returns results  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  SQLModel /         │
│  SQLAlchemy         │
│  - Session          │
│  - DittoEvent model │
│  - Raw SQL for      │
│    TimescaleDB      │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  TimescaleDB        │
│  (Hypertable)       │
└─────────────────────┘
```

---

## 4. Module Details

### 4.1 `app/main.py` — Application Entry Point

Creates the FastAPI application with:
- `root_path="/historic"` — all routes are prefixed with `/historic`
- `default_response_class=ORJSONResponse` — fast JSON serialization via `orjson`
- Custom Swagger UI served at `/historic/` using static assets
- No automatic docs/redoc URLs (custom Swagger only)

```python
app = FastAPI(
    root_path=root_path,
    docs_url=None,
    redoc_url=None,
    default_response_class=ORJSONResponse,
    title="Ditto Events API",
    description="API to manage historical events from Eclipse Ditto",
)
```

### 4.2 `app/routers/events.py` — API Endpoints

This file defines all REST endpoints and their dependencies.

**Key dependencies:**

- **`auth`**: Instance returned by `get_auth()` from `fastapi-oidc`. Configures OIDC validation with the settings.
- **`get_events_service(session)`**: FastAPI dependency that creates an `EventsService` with a database session.
- **`check_role(roles)`**: Returns a dependency function that inspects the Keycloak token's `resource_access` to verify the required roles.

**Role verification logic (`check_role`)**:
```python
def check_role(roles: list[str]):
    def check_role_inner(token: KeycloakToken):
        if settings.auth.client_id not in token.resource_access:
            raise HTTPException(403)
        token_roles = token.resource_access[settings.auth.client_id].roles
        if not any(role in token_roles for role in roles):
            raise HTTPException(403)
    return check_role_inner
```

**Token model** (`KeycloakToken`):
```python
class KeycloakToken(IDToken):
    resource_access: dict[str, ClientResourceAccess] = {}
```

**`ClientResourceAccess`**:
```python
class ClientResourceAccess(BaseModel):
    roles: list[str] = []
```

**Endpoint list** (all under APIRouter with `dependencies=[Depends(auth)]`):

| Endpoint Function | Path | Method | Service Method |
|---|---|---|---|
| `read_available_things` | `/things` | GET | `get_available_things()` |
| `read_event_paths` | `/events/{thing_id}/paths` | GET | `get_event_paths_with_action()` |
| `read_events` | `/events` | GET | `get_events()` |
| `read_events_by_thing` | `/events/{thing_id}` | GET | `get_events_by_thing()` |
| `insert_events` | `/events` | POST | `insert_events()` |
| `delete_events` | `/events/{thing_id}` | DELETE | `delete_events()` |
| `read_jsonpath_projection` | `/events/projection/{thing_id}` | GET | `get_jsonpath_projection()` |
| `read_events_custom_time_buckets` | `/events/time-buckets/{thing_id}` | GET | `get_events_custom_time_buckets()` or `get_events_custom_time_buckets_with_path()` |

### 4.3 `app/services/events_service.py` — Business Logic

The `EventsService` class encapsulates all database operations. It receives a SQLModel `Session` via constructor injection.

#### Methods:

**`get_available_things(thing_id_prefix)`**
- SQL: `SELECT DISTINCT thing_id FROM dittoevent [WHERE thing_id LIKE prefix%]`
- Returns list of distinct `thing_id` strings.

**`get_event_paths_with_action(thing_id, since, until)`**
- SQL: `SELECT DISTINCT path, action FROM dittoevent WHERE thing_id = :id AND time BETWEEN :since AND :until`
- Returns `list[PathResponseObject]`.

**`get_events(since, until, thing_id_prefix, path_prefix, action, limit)`**
- SQL: `SELECT * FROM dittoevent WHERE time BETWEEN :since AND :until [AND thing_id LIKE prefix%] [AND action = :action] [AND path LIKE prefix%] ORDER BY time DESC [LIMIT :limit]`
- Returns `list[DittoEvent]`.

**`get_events_by_thing(thing_id, since, until, path_prefix, action)`**
- Same as `get_events` but filtered by exact `thing_id`.

**`insert_events(events)`**
- Iterates over events, adds each to session, commits.
- Returns `None`.

**`delete_events(thing_id, since, until)`**
- SQL: `DELETE FROM dittoevent WHERE thing_id = :id AND time BETWEEN :since AND :until`
- Returns count of deleted rows.

**`get_jsonpath_projection(json_path, thing_id, since, path_prefix, until)`**
- Uses PostgreSQL `jsonb_path_query()` function to extract values matching a JSONPath expression.
- SQL (simplified):
  ```sql
  SELECT jsonb_path_query(value, CAST(:json_path AS JSONPATH))
  FROM dittoevent
  WHERE thing_id = :id AND time BETWEEN :since AND :until [AND path LIKE prefix%]
  ```

**`get_events_custom_time_buckets(json_path, since, until, bucket_minutes, agg_type, thing_id)`**
- Groups events into time buckets and applies an aggregation function on a JSONPath-extracted value.
- **All-time mode** (`bucket_minutes <= 0 or None`): Returns a single bucket with `MIN(time)` as label.
- **Bucket mode**: Uses `EXTRACT(epoch FROM time) / bucket_seconds` arithmetic to compute bucket boundaries, then `to_timestamp()` to convert back.
- Aggregation functions: `count`, `sum`, `avg`, `min`, `max`.
- For numeric aggregations (`sum`, `avg`, `min`, `max`), the extracted value is cast to `Float`.
- **Error handling**:
  - `DataError` with "cannot cast jsonb object to double precision" → 400 with helpful message.
  - `ProgrammingError` (invalid JSONPath syntax) → 400.
  - Both trigger `session.rollback()`.

**`get_events_custom_time_buckets_with_path(json_path, since, until, path_prefixes, bucket_minutes, agg_type, thing_id)`**
- Same as above but also groups by `DittoEvent.path`.
- `path_prefixes` is a comma-separated string that gets split into an array and used in an OR condition via `sqlalchemy.or_()`.
- Returns results segmented by path.

### 4.4 `app/models/ditto_events.py` — Database Model

```python
class DittoEvent(SQLModel, table=True):
    time: datetime = Field(primary_key=True)           # Partition column (hypertable)
    index: Optional[int] = Field(..., Identity(...))   # Auto-increment, also PK
    thing_id: str = Field(index=True)                  # Indexed for filtering
    action: Action = Field(sa_column=Column(SAEnum))   # created/modified/deleted/merged
    revision: PositiveInt | None
    path: str                                          # Ditto feature path
    value: dict = Field(sa_type=JSONB)                 # JSON payload
```

**TimescaleDB configuration** (set via `__timescale_config__` and an `after_create` event listener):

| Property | Value |
|---|---|
| `time_column` | `time` |
| `chunk_time_interval` | 1 day |
| `compress` | Yes |
| `compress_segmentby` | `thing_id` |
| `compress_orderby` | `time DESC` |
| `compress_interval` | 7 days (compression policy) |

The `create_timescale_features()` function (registered via `@event.listens_for(..., "after_create")`) executes three SQL commands when the table is created:
1. `SELECT create_hypertable(...)` — converts the table to a hypertable
2. `ALTER TABLE ... SET (timescaledb.compress, ...)` — enables native compression
3. `SELECT add_compression_policy(...)` — sets the automatic compression schedule

This model is duplicated in `dt4mob-historical-writer` to keep the services independent.

### 4.5 `app/models/paths_response.py` — Response Model

```python
class PathResponseObject(BaseModel):
    path: str
    action: Action
    model_config = {"from_attributes": True}
```

Used by the `/events/{thing_id}/paths` endpoint.

### 4.6 `app/models/util.py` — Action Enum

```python
class Action(str, Enum):
    MODIFIED = "modified"
    CREATE = "created"
    DELETE = "deleted"
    MERGED = "merged"
```

Used as a column type and as a query filter parameter.

### 4.7 `app/database_engine/__init__.py` — Engine Singleton

```python
timescale_engine = TimescaleDBEgineManager()
timescale_engine.create_db_tables()
```

- Creates the SQLAlchemy engine **once** at module import time.
- Calls `SQLModel.metadata.create_all(engine)` — this creates the `dittoevent` table and triggers the `after_create` event that sets up the TimescaleDB hypertable.
- **Important**: Imports `DittoEvent` model before `create_db_tables()` to ensure the model is registered in `SQLModel.metadata`.
- `get_session()` is a generator that yields a `Session`, rolls back on exception, and closes in `finally`.

### 4.8 `app/database_engine/TimeScaleEngineManager.py` — Engine Wrapper

```python
class TimescaleDBEgineManager:
    def __init__(self):
        self.engine = create_engine(
            url=settings.timescale.get_connection(),
            echo= (settings.log_level == "DEBUG"),
        )

    def create_db_tables(self):
        SQLModel.metadata.create_all(self.engine)
```

- `get_connection()` replaces `postgresql://` with `postgresql+psycopg://` to use the `psycopg` driver.
- Engine `echo` is enabled only when `LOG_LEVEL=DEBUG`.

### 4.9 `app/settings/__init__.py` — Global Settings

```python
class Settings(BaseSettings):
    log_level: LogLevel = Field(validation_alias="LOG_LEVEL", default="INFO")
    auth: AuthSettings
    timescale: TimeScaleSettings

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # Enables AUTH__CLIENT_ID syntax
        extra="ignore",
    )
```

- Singleton: `settings = Settings()` created at module level.
- Reads from environment variables or `.env` file.
- The `__` delimiter allows nesting: `AUTH__CLIENT_ID` → `settings.auth.client_id`.

### 4.10 `app/settings/auth.py` — Auth Settings

```python
class AuthSettings(BaseModel):
    client_id: str
    audience: str = "account"
    server_uri: str
    issuer: str | list[str]
    signature_cache_ttl: PositiveInt = 3600
    read_role: list[str] = ["historical-read"]
    write_role: list[str] = ["historical-write"]
```

### 4.11 `app/settings/timescale.py` — Timescale Settings

```python
class TimeScaleSettings(BaseModel):
    database_timezone: str = "Europe/Lisbon"
    connection: str

    def get_connection(self):
        return self.connection.replace("postgresql", "postgresql+psycopg")
```

---

## 5. Authentication Flow

```
Client Request (with Bearer JWT)
    │
    ▼
fastapi-oidc middleware
    │
    ├── Validates JWT signature (cached for signature_cache_ttl seconds)
    ├── Checks issuer against AUTH__ISSUER
    └── Decodes token into KeycloakToken model
    │
    ▼
check_role(["historical-read"]) or check_role(["historical-write"])
    │
    ├── Extracts resource_access[client_id].roles from token
    ├── Checks if any of the required roles are present
    └── Raises 403 if missing
    │
    ▼
Endpoint handler executes
```

The `fastapi-oidc` library is configured with `token_type=KeycloakToken` so that the decoded token is available as a typed Pydantic model. The custom `check_role()` dependency is used per-endpoint via `Depends()`.

---

## 6. Error Handling Strategy

| Scenario | Handler | HTTP Status | Response Detail |
|---|---|---|---|
| Missing/invalid JWT | `fastapi-oidc` | 401/403 | Automatic |
| Missing role in token | `check_role()` | 403 | `"Missing role"` |
| JSONB→Float cast error (time-buckets) | `events_service.py` | 400 | Suggests using `count` or fixing the JSONPath |
| Invalid JSONPath syntax | `events_service.py` | 400 | Returns the PostgreSQL error message |
| Generic DB error | SQLAlchemy | 500 | Propagated |

In the service layer, errors that occur during query execution trigger `session.rollback()` to revert any uncommitted changes before raising the HTTP exception.

---

## 7. Dependencies

### Python Packages (from `pyproject.toml`)

| Package | Version | Purpose |
|---|---|---|
| `fastapi[standard]` | ≥0.128.0 | Web framework |
| `fastapi-oidc` | ≥0.0.11 | Keycloak OIDC auth middleware |
| `orjson` | ≥3.11.7 | Fast JSON serialization |
| `psycopg[binary]` | ≥3.3.2 | PostgreSQL adapter |
| `pydantic-settings` | ≥2.12.0 | Environment-based configuration |
| `sqlmodel` | ≥0.0.31 | Pydantic + SQLAlchemy ORM integration |

### External Services

| Service | Protocol | Purpose |
|---|---|---|
| **TimescaleDB** | PostgreSQL (psycopg) | Data persistence (hypertable) |
| **Keycloak** | HTTPS (OIDC) | JWT token validation |

---

## 8. Deployment

### Dockerfile

- **Base image**: `python:3.14-slim`
- **Package manager**: `uv` 0.9.27 (copied from `ghcr.io/astral-sh/uv:0.9.27`)
- **Static files**: Explicitly copied from `./app/static`
- **Command**: `fastapi run app/main.py --port 8080 --host 0.0.0.0`

### Helm Chart

The chart at `charts/dt4mob-historical/` deploys both the API and the writer together:

- **API Deployment**: Runs the `data-lake-api` image on port 8080.
- **Writer Deployment**: Runs the `data-gateway` image, connects to Kafka via mTLS.
- **TimescaleDB Cluster**: Managed by Cloud Native PostgreSQL (CNPG) operator with TimescaleDB extension.
- **Kafka Topic**: Managed by Strimzi operator.

### Container Images

Registry: `atnog-harbor.av.it.pt/dt4mob/`
- API: `data-lake-api`
- Writer: `data-gateway`
