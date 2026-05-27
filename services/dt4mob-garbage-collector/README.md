
# DT4MOB Garbage Collector

A specialized microservice designed to handle data cleanup and resource
management within the **DT4MOB** digital twin. It interacts with the Ditto API
to monitor and remove unused entities.

## 🚀 Getting Started

### Prerequisites
* **Docker**

---

## 📦 Building the Image

To build the Docker image locally, navigate to the root directory and run:

```bash
# Build the image
docker build -t dt4mob-garbage-collector:latest .

# Tag for your registry (example)
docker tag dt4mob-garbage-collector:latest your-registry.com/dt4mob-garbage-collector:v1.0.0
```

---

## ⚙️ Configuration (Environment Variables)

The service is configured via environment variables.

| Variable | Description |
| :--- | :--- |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARN`, `ERROR`) |
| `DITTO__API_URL` | The full URL for the Ditto API |
| `DITTO__BASE_API_PATH` | Base path for REST API calls |
| `DITTO__BASE_WS_PATH` | Base path for WebSocket connections |
| `AUTH__TOKEN_ENDPOINT` | OIDC token endpoint | 
| `AUTH__USERNAME` or `AUTH_USERNAME_FILE` | Authentication username | 
| `AUTH__PASSWORD` or `AUTH_PASSWORD_FILE` | Authentication password | 
| `AUTH__CLIENT_ID` | OIDC Client ID | 
| `AUTH__CA_CRT_FILE` | CA certificate of the OIDC server | 

### Running Locally with Docker
You can test the container locally by passing an `.env` file or individual flags:

```bash
docker run --env-file .env dt4mob-garbage-collector:latest
```

---
