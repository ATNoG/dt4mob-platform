# dt4mob-historical-writer — Developer Manual

## Project Structure

```
dt4mob-historical-writer/
├── main.py                                          # Entry point
├── pyproject.toml                                   # Dependencies (confluent-kafka, sqlmodel, etc.)
├── dockerfile                                       # Dev Docker image (Alpine + uv)
├── dockerfile.prod                                  # Prod Docker image (no dev deps)
├── .python-version                                  # Python 3.12
├── .env                                             # Local config (gitignored)
├── uv.lock                                          # Lockfile
├── USER_MANUAL_EN.md
├── USER_MANUAL_PT.md
├── DEVELOPER_MANUAL_EN.md
├── DEVELOPER_MANUAL_PT.md
└── src/
    ├── settings/
    │   ├── __init__.py          # Global Settings (pydantic-settings), loaded from .env
    │   ├── kafka.py             # KafkaSettings — broker, SSL, consumer group, topic
    │   └── timescale.py         # TimeScale — connection string, timezone
    ├── models/
    │   ├── __init__.py
    │   └── ditto_events.py      # DittoEvent SQLModel, Action enum, Timescale hypertable config
    ├── database_engines/
    │   ├── __init__.py          # Singleton engine creation + table creation on import
    │   └── TimeScaleEngineManager.py  # SQLAlchemy engine, session factory, create_db_tables
    └── services/
        ├── __init__.py
        ├── KafkaConsumer/
        │   ├── __init__.py      # Re-exports KafkaConsumer
        │   └── kafka_consumer.py  # Kafka poll loop, JSON decode, message dispatch
        ├── MessageProcessor/
        │   ├── __init__.py
        │   └── message_processor.py  # Parses raw Ditto messages into DittoEvent objects
        └── DittoEventsManager/
            ├── __init__.py      # Creates singleton DittoEventsManager with the engine
            └── ditto_events_manager.py  # write(event) — session.add + commit
```

## Startup Sequence

1. **`main.py:13`** — `if __name__ == "__main__": main()` calls `main()`
2. **`src/database_engines/__init__.py:4-5`** — on import, creates `TimescaleDBEgineManager()` singleton and calls `create_db_tables()`, which runs `SQLModel.metadata.create_all(self.engine)`, emitting `CREATE TABLE` and the `after_create` event
3. **`src/services/DittoEventsManager/__init__.py:2-4`** — on import, instantiates `DittoEventsManager(db_engine=timescale_engine)` singleton
4. **`main.py:6`** — `KafkaConsumer()` subscribes to the configured Kafka topic
5. **`main.py:9`** — `consumer.consume(ditto_event_manager)` enters the infinite polling loop

## Message Flow (End-to-End)

```
Kafka Topic
    │
    ▼
KafkaConsumer.consume()                         src/services/KafkaConsumer/kafka_consumer.py:15
    ├── consumer.poll(1.0)                       Polls Kafka with 1s timeout
    ├── msg.value().decode('utf-8')              Decodes bytes to string
    ├── json.loads(message_text)                 Parses JSON
    │
    ▼
parse_message(message_data)                      src/services/MessageProcessor/message_processor.py:5
    ├── Splits msg["topic"] by "/"               Extracts namespace, name, channel, action
    ├── Reads headers["dt4mob-historic-timestamp-override"]  Optional timestamp override
    ├── Falls back to msg["timestamp"]           If override is absent or malformed
    ├── Builds DittoEvent(time, thing_id, action, path, revision, value)
    │
    ▼
DittoEventsManager.write(event)                  src/services/DittoEventsManager/ditto_events_manager.py:9
    ├── db_engine.get_session() as session        Opens a SQLModel session
    ├── session.add(event)                       Queues the INSERT
    ├── session.commit()                         Commits (auto on context manager exit)
    └── On exception: session.rollback()
    │
    ▼
TimescaleDB (dittoevent hypertable)
    ├── CREATE TABLE on first import
    ├── create_hypertable() on after_create
    └── Compression policy applied
```

## Module Deep-Dives

### Settings (`src/settings/`)

Uses **pydantic-settings** with `SettingsConfigDict(env_file=".env")`. The global `settings` singleton is built at import time (`src/settings/__init__.py:28`).

**`KafkaSettings.as_dict()`** (`src/settings/kafka.py:20`) converts the Pydantic fields into the dotted-key format required by `confluent_kafka.Consumer`:
- `bootstrap.servers`, `security.protocol`, `ssl.ca.location`, `ssl.certificate.location`, `ssl.key.location`, `group.id`, `auto.offset.reset`
- `enable.auto.commit` is hardcoded to `False` — commits are manual after each successful message.

**`TimeScale.get_connection()`** (`src/settings/timescale.py:14`) replaces `postgresql://` with `postgresql+psycopg://` so SQLAlchemy uses the psycopg driver.

### KafkaConsumer (`src/services/KafkaConsumer/kafka_consumer.py`)

- **`__init__`**: Creates a `confluent_kafka.Consumer` with `KafkaSettings.as_dict()` and subscribes to the configured topic.
- **`consume(manager)`**: Infinite loop calling `consumer.poll(1.0)`. On each message:
  1. Decodes and JSON-parses the value.
  2. Calls `parse_message()` to build a `DittoEvent`.
  3. Calls `manager.write(event)` to persist.
  4. Calls `self.consumer.commit(asynchronous=False)` — **manual synchronous commit** ensures at-least-once delivery. If the process crashes between `write` and `commit`, the message will be re-delivered, leading to a potential duplicate.

### MessageProcessor (`src/services/MessageProcessor/message_processor.py`)

**`parse_message(msg)`** extracts structured data from a raw Ditto message:

1. **Topic parsing**: `msg["topic"]` is split by `"/"`. Expected format: `{namespace}:{name}/things/{channel}//{action}`. The `thing_id` is reassembled as `namespace:name`, and `action` is the 6th element (index 5).
2. **Timestamp override**: If the header `dt4mob-historic-timestamp-override` is present and a valid ISO-8601 string, it replaces the message's `timestamp`. Otherwise, the original `msg["timestamp"]` is used.
3. **Returns** a `DittoEvent` with `time`, `thing_id`, `action`, `path`, `revision`, `value`.

### DittoEvent Model (`src/models/ditto_events.py`)

**`Action` enum**: `modified`, `created`, `deleted`, `merged`.

**`DittoEvent`** SQLModel (table `dittoevent`):
- **Composite primary key**: `time` (datetime, 1st part) + `index` (auto-increment Identity, 2nd part)
- **`thing_id`**: indexed for query performance
- **`action`**: stored as a native PostgreSQL enum (`action_enum`)
- **`value`**: stored as `JSONB` for flexible nested data

**Timescale hypertable configuration** (`__timescale_config__`):
- `time_column: "time"` — partitioning column
- `chunk_time_interval: "1 days"` — each chunk covers 1 day
- `compress: True` — enables native compression
- `compress_segmentby: "thing_id"` — compressed rows are segmented by thing
- `compress_orderby: "time DESC"` — ordering within compressed segments
- `compress_interval: "7 days"` — compression policy applies to data older than 7 days

The `after_create` event listener (`src/models/ditto_events.py:42`) executes these SQL statements automatically when the table is created:

```sql
SELECT create_hypertable('dittoevent', 'time', chunk_time_interval => INTERVAL '1 days', if_not_exists => TRUE);

ALTER TABLE dittoevent SET (timescaledb.compress, timescaledb.compress_segmentby = 'thing_id', timescaledb.compress_orderby = 'time DESC');

SELECT add_compression_policy('dittoevent', INTERVAL '7 days', if_not_exists => TRUE);
```

### TimeScaleDBEgineManager (`src/database_engines/TimeScaleEngineManager.py`)

- **`__init__`**: Creates a SQLAlchemy `Engine` using the connection string from settings. `echo=True` when `LOG_LEVEL=DEBUG`.
- **`create_db_tables()`**: Calls `SQLModel.metadata.create_all(self.engine)` which emits `CREATE TABLE` and triggers the `after_create` event.
- **`get_session()`**: A `@contextmanager` that yields a `Session`, auto-commits on success and auto-rollbacks on exception.

### DittoEventsManager (`src/services/DittoEventsManager/ditto_events_manager.py`)

Thin wrapper around the database engine. The `write(event)` method opens a session, adds the event, and commits. The session is obtained via the context manager from `TimeScaleDBEgineManager.get_session()`.

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `confluent-kafka` | >= 2.13.0 | Kafka consumer (C-based, high performance) |
| `psycopg[binary]` | >= 3.3.2 | PostgreSQL adapter (async-compatible) |
| `pydantic` | >= 2.12.5 | Data validation |
| `pydantic-settings` | >= 2.12.0 | Settings management from env vars |
| `sqlalchemy` | >= 2.0.45 | ORM core |
| `sqlmodel` | >= 0.0.31 | Pydantic + SQLAlchemy integration, table definition |

## Docker Build

Two Dockerfiles using **Alpine Edge** + **uv**:

- **`dockerfile`** (dev): runs `uv sync --locked` (installs all dependencies including dev).
- **`dockerfile.prod`** (prod): sets `ENV UV_NO_DEV=1` before `uv sync --locked` to exclude dev dependencies.

Both install `build-base`, `python3-dev`, `librdkafka-dev` (for the confluent-kafka C extension). The CMD is `uv run main.py`.

The container expects SSL certificates to be mounted at `/certs/` (or custom paths).

## Kubernetes Deployment

The Kubernetes resources are defined in the **`dt4mob-historical`** Helm chart at `charts/dt4mob-historical/` in the project's infrastructure.

### Chart Structure

```
charts/dt4mob-historical/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl              # Template naming helpers
    ├── writer-deployment.yaml     # Deployment for this service
    ├── writer-config.yaml         # ConfigMap (env vars for the writer)
    ├── kafka-topic.yaml           # Strimzi KafkaTopic (optional)
    ├── timescale-cluster.yaml     # CloudNativePG Cluster with TimescaleDB
    ├── timescale-image-catalog.yaml  # CNPG ImageCatalog
    ├── api-deployment.yaml        # Companion read API (separate codebase)
    └── api-service.yaml           # Companion API Service
```

### Writer Deployment (`writer-deployment.yaml`)

Key aspects:

- **Image**: from `values.images.writer` (default: `atnog-harbor.av.it.pt/dt4mob/data-gateway`).
- **Environment variables** come from two sources:
  - **ConfigMap** (`writer-config.yaml`): `LOG_LEVEL`, `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SSL_CA_LOCATION`, `KAFKA_SSL_CERTIFICATE_LOCATION`, `KAFKA_SSL_KEY_LOCATION`, `KAFKA_CONSUMER_GROUP`, `KAFKA_TOPIC`, `KAFKA_AUTO_OFFSET_RESET`, `TIMESCALE_DATABASE_TIMEZONE`.
  - **Secret reference**: `TIMESCALE_CONNECTION` is read from the CNPG cluster secret (`{release}-cluster-app`, key `uri`).
- **Volume mounts**: Two volumes mount Kafka SSL secrets:
  - `/certs` (user certificate + key) — from `writer.kafka.userSecretName`
  - `/cluster-ca` (CA certificate) — from `writer.kafka.trustSecretName`

### Writer ConfigMap (`writer-config.yaml`)

Maps `values.yaml` fields to environment variable names, constructing the SSL certificate paths from well-known mount points:

```yaml
KAFKA_SSL_CA_LOCATION: "/cluster-ca/ca.crt"
KAFKA_SSL_CERTIFICATE_LOCATION: "/certs/user.crt"
KAFKA_SSL_KEY_LOCATION: "/certs/user.key"
KAFKA_TOPIC: {{ .Values.kafkaTopic.name }}
```

### TimescaleDB Cluster (`timescale-cluster.yaml`)

Uses the **CloudNativePG** operator (`postgresql.cnpg.io/v1`) to provision a PostgreSQL cluster with TimescaleDB:

- **Image**: `timescale/timescaledb-ha:pg18.0-ts2.23.0` (via ImageCatalog)
- **Pre-load library**: `timescaledb` is added to `shared_preload_libraries`
- **Post-init SQL**: `CREATE EXTENSION IF NOT EXISTS timescaledb` — ensures the extension exists before the writer's `after_create` event tries to call `create_hypertable()`
- **Storage**: configurable `storageClass` and `size` (default: `local-path`, `10Gi`)

### KafkaTopic (`kafka-topic.yaml`)

Optionally creates a `KafkaTopic` custom resource (Strimzi) defined by `kafkaTopic.name`. Controlled by `kafkaTopic.create` boolean.

### How It All Connects

1. Helm creates the TimescaleDB cluster (CNPG) and the KafkaTopic.
2. The CNPG operator generates a secret containing the database URI.
3. The writer Deployment reads:
   - TimescaleDB URI from the CNPG secret
   - Other config from the ConfigMap
4. The writer starts, creates the `dittoevent` table + hypertable, subscribes to the Kafka topic, and begins consuming.
