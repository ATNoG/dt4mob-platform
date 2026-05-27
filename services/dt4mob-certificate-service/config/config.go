package config

import "time"

type Config struct {
	LogLevel  string `env:"LOG_LEVEL" envDefault:"info"`
	Namespace string `env:"NAMESPACE"`

	ListenAddr           string `env:"LISTEN_ADDR" envDefault:":8080"`
	ManagementListenAddr string `env:"MGMT_LISTEN_ADDR" envDefault:":9090"`
	PathPrefix           string `env:"PATH_PREFIX"`

	SecretName         string `env:"SECRET_NAME,required"`
	SecretCertSelector string `env:"SECRET_CERT_SELECTOR" envDefault:"tls.crt"`
	SecretKeySelector  string `env:"SECRET_KEY_SELECTOR" envDefault:"tls.key"`

	OIDCCACertificate  string   `env:"OIDC_CA_CERT_FILE"`
	OIDCIssuerURI      string   `env:"OIDC_ISSUER_URI,required"`
	OIDCTrustedIssuers []string `env:"OIDC_TRUSTED_ISSUERS" envSeparator:","`
	OIDCClientID       string   `env:"OIDC_CLIENT_ID,required"`

	RequiredRoles []string `env:"ROLE_REQUIRED" envSeparator:"," envDefault:"certificate-issuer"`

	MaxCertificateTTL time.Duration `env:"MAX_CERTIFICATE_TTL" envDefault:"720h"` // Default: 30 days
}
