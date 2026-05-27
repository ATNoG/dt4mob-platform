# dt4mob-certificate-service

Certificate issuance service for DT4Mob. Generates signed certifcates based on
the tenant's device CA root certificate for use by partners when adding things
to the platform.

## Documentation

Documentation is available on the running service under `/docs`.

## Commands

```sh
# Lint
go vet ./...

# Test
go test -v ./...

# Build
go build -o bin/app .
```

## Configuration

All configuration is done through environment variables.

| Name | Required | Default | Description |
|---|---|---|---|
| `LOG_LEVEL` | no | `info` | Log level (`debug`, `info`, `warn`, `error`) |
| `LISTEN_ADDR` | no | `:8080` | Main HTTP server listen address (serves `POST /issue`) |
| `MGMT_LISTEN_ADDR` | no | `:9090` | Management HTTP server listen address (serves `/health`, `/ready`) |
| `NAMESPACE` | no | auto-detect | Kubernetes namespace (reads from service account file when empty) |
| `SECRET_NAME` | **yes** | — | Name of the Kubernetes Secret holding the CA certificate and key |
| `SECRET_CERT_SELECTOR` | no | `tls.crt` | Key within the Secret holding the PEM-encoded CA certificate |
| `SECRET_KEY_SELECTOR` | no | `tls.key` | Key within the Secret holding the PEM-encoded CA private key |
| `OIDC_CA_CERT_FILE` | no | — | Path to a custom CA certificate file for connecting to the OIDC provider |
| `OIDC_ISSUER_URI` | **yes** | — | OIDC provider URL for discovery (well-known configuration) |
| `OIDC_TRUSTED_ISSUERS` | no | — | Comma-separated list of trusted `iss` claim values; when set, token `iss` is validated against this list instead of the provider's issuer |
| `OIDC_CLIENT_ID` | **yes** | — | Expected `aud` claim and the client whose roles are verified |
| `ROLE_REQUIRED` | no | `certificate-issuer` | Client role that must be present in the token |
| `MAX_CERTIFICATE_TTL` | no | `720h` | Maximum validity duration of issued certificates (Go duration format, e.g. `48h`, `8760h`) |
