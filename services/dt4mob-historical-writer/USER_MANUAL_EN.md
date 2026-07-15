# dt4mob-historical-writer — User Manual

## Overview

The **historical-writer** is a service that consumes messages from a **Kafka** topic (following the Eclipse Ditto protocol) and persists them into a **TimescaleDB** hypertable. It is part of the DT4Mob platform's historical data extension.

## Requirements

- **Python** >= 3.12
- **uv** package manager (https://docs.astral.sh/uv/)
- **Kafka** broker (with SSL certificates)
- **TimescaleDB** instance (PostgreSQL + Timescale extension)

## Configuration

All configuration is done via environment variables or a `.env` file placed at the service root.

### Kafka

| Variable | Required | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | Yes | Kafka broker address (e.g. `kafka-cluster-kafka-bootstrap:9092`) |
| `KAFKA_SECURITY_PROTOCOL` | Yes | Security protocol (e.g. `SSL`) |
| `KAFKA_SSL_CA_LOCATION` | Yes | Path to CA certificate file |
| `KAFKA_SSL_CERTIFICATE_LOCATION` | Yes | Path to client certificate file |
| `KAFKA_SSL_KEY_LOCATION` | Yes | Path to client key file |
| `KAFKA_CONSUMER_GROUP` | Yes | Consumer group ID |
| `KAFKA_TOPIC` | Yes | Topic to consume from |
| `KAFKA_AUTO_OFFSET_RESET` | Yes | Offset reset strategy (`latest`, `earliest`) |

### TimescaleDB

| Variable | Required | Default | Description |
|---|---|---|---|
| `TIMESCALE_CONNECTION` | Yes | — | Connection string (e.g. `postgresql://user:pass@host:5432/db`) |
| `TIMESCALE_DATABASE_TIMEZONE` | No | `Europe/Lisbon` | Timezone for timestamp columns |

### General

| Variable | Required | Default | Description |
|---|---|---|---|
| `LOG_LEVEL` | No | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

### Example `.env`

```
KAFKA_BOOTSTRAP_SERVERS=kafka-cluster-kafka-bootstrap:9092
KAFKA_SECURITY_PROTOCOL=SSL
KAFKA_SSL_CA_LOCATION=/certs/ca.crt
KAFKA_SSL_CERTIFICATE_LOCATION=/certs/user.crt
KAFKA_SSL_KEY_LOCATION=/certs/user.key
KAFKA_CONSUMER_GROUP=historical-writer-group
KAFKA_TOPIC=exports-test-tenant
KAFKA_AUTO_OFFSET_RESET=latest
TIMESCALE_CONNECTION=postgresql://user:password@timescale-host:5432/historical
TIMESCALE_DATABASE_TIMEZONE=Europe/Lisbon
LOG_LEVEL=INFO
```

## Running Locally

```bash
# Install dependencies
uv sync --locked

# Run
uv run main.py
```

## Running with Docker

### Development

```bash
docker build -f dockerfile -t historical-writer:dev .
docker run --env-file .env historical-writer:dev
```

### Production (without dev dependencies)

```bash
docker build -f dockerfile.prod -t historical-writer:prod .
docker run --env-file .env historical-writer:prod
```

The container expects SSL certificates to be mounted at `/certs/` (or the paths defined in the env vars).

## Running on Kubernetes (Helm)

The Kubernetes deployment is managed through the `dt4mob-historical` Helm chart located in the project's infrastructure at `charts/dt4mob-historical/`. This chart is not part of this service's source code — it lives in the parent infrastructure repository.

The Helm chart provisions:

- **Writer Deployment** — runs this service
- **Writer ConfigMap** — maps chart values to environment variables
- **TimescaleDB Cluster** — CloudNativePG cluster with TimescaleDB extension
- **KafkaTopic** — Strimzi topic (optional)
- **API Deployment + Service** — companion read API (separate codebase)

### Configurable Values (`values.yaml`)

```yaml
# Writer image
images:
  writer:
    repository: atnog-harbor.av.it.pt/dt4mob/data-gateway
    tag: latest

# Writer behavior
writer:
  replicas: 1
  config:
    logLevel: INFO
    timescaleDatabaseTimezone: "Europe/Lisbon"
  kafka:
    bootstrapServers: "kafka-cluster-kafka-bootstrap:9092"
    securityProtocol: SSL
    consumerGroup: "consumer-group"
    autoOffsetReset: latest
    # userSecretName/trustSecretName reference Kubernetes secrets
    # containing the Kafka SSL certificates

# TimescaleDB storage
timescale:
  instances: 1
  storage:
    storageClass: "local-path"
    size: 10Gi
```

### Install

```bash
helm upgrade --install dt4mob-historical charts/dt4mob-historical -f my-values.yaml
```

Before installing, ensure the Kafka SSL secrets exist in the namespace. Refer to the chart's `values.yaml` for the full parameter reference.

## Expected Input Format

The service consumes messages in the **Eclipse Ditto protocol** format published to the configured Kafka topic. A typical message:

```json
{
  "topic": "org.dt4mob:vehicle-123/things/live/state/modified",
  "headers": {
    "dt4mob-historic-timestamp-override": "2025-01-15T10:30:00Z"
  },
  "path": "/features/speed/properties/value",
  "value": 42.5,
  "revision": 3,
  "timestamp": "2025-01-15T10:30:05Z"
}
```

- `topic` must follow the pattern `{namespace}:{name}/things/{channel}//{action}`
- `dt4mob-historic-timestamp-override` (optional header) overrides the event timestamp with the actual measurement time

## Database Schema

The service creates a table named `dittoevent` with the following columns:

| Column | Type | Notes |
|---|---|---|
| `time` | `timestamptz` | Primary key (1st part) |
| `index` | `integer` | Primary key (2nd part, auto-increment) |
| `thing_id` | `text` | Indexed |
| `action` | `enum` | `modified`, `created`, `deleted`, `merged` |
| `path` | `text` | Ditto JSON path |
| `revision` | `integer` | Nullable |
| `value` | `jsonb` | Nullable |

TimescaleDB hypertable configuration:

- **Chunk interval:** 1 day
- **Compression:** enabled
- **Compression segment by:** `thing_id`
- **Compression order by:** `time DESC`
- **Compression interval:** compress data older than 7 days

## Monitoring & Troubleshooting

### Logs

Set `LOG_LEVEL=DEBUG` for verbose output showing each consumed message and database write.

### Common Issues

| Problem | Likely Cause |
|---|---|
| Consumer does not connect | Kafka broker unreachable or SSL certificates misconfigured |
| No messages consumed | Wrong topic name or consumer group offset |
| Database writes fail | TimescaleDB connection string incorrect or database unreachable |
| Table not created | Missing `timescaledb` extension on the PostgreSQL instance |

### Health

The service runs an infinite polling loop. If it terminates, check logs for Kafka or database errors. On Kubernetes, the Deployment will restart the pod automatically.
