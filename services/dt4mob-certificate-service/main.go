package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"slices"
	"strings"

	"github.com/caarlos0/env/v11"
	"github.com/danielgtaylor/huma/v2"
	"github.com/danielgtaylor/huma/v2/adapters/humago"
	corev1 "k8s.io/api/core/v1"

	"github.com/ATNoG/dt4mob/dt4mob-certificate-service/auth"
	"github.com/ATNoG/dt4mob/dt4mob-certificate-service/config"
	"github.com/ATNoG/dt4mob/dt4mob-certificate-service/handler"
	"github.com/ATNoG/dt4mob/dt4mob-certificate-service/k8s"
)

func main() {
	var config config.Config
	if err := env.Parse(&config); err != nil {
		slog.Error("failed to parse config", "error", err)
		os.Exit(1)
	}

	var level slog.Level
	err := level.UnmarshalText([]byte(config.LogLevel))
	if err != nil {
		panic(err.Error())
	}

	logger := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
	slog.SetDefault(logger)

	if config.Namespace == "" {
		data, err := os.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
		if err != nil {
			panic(err.Error())
		}
		config.Namespace = string(data)
	}

	filtered := slices.DeleteFunc(config.RequiredRoles, func(s string) bool {
		return strings.TrimSpace(s) == ""
	})
	config.RequiredRoles = filtered
	if len(config.RequiredRoles) == 0 {
		slog.Error("ROLE_REQUIRED must specify at least one role")
		os.Exit(1)
	}

	slog.Info("Configuration loaded", "config", config)

	// creates the clientset
	clientset, err := k8s.NewClient()
	if err != nil {
		panic(err.Error())
	}

	h := handler.New(&config, logger)

	secret, err := k8s.ReadSecret(context.Background(), clientset, config.Namespace, config.SecretName)
	if err != nil {
		logger.Error("failed to read secret", "name", config.SecretName, "error", err)
		os.Exit(1)
	}
	if tlsCert := loadTLSCert(secret, &config, logger); tlsCert != nil {
		h.UpdateTLSCert(tlsCert)
	}
	logger.Info("secret loaded", "name", config.SecretName)

	// Listen in the background for changes
	go func() {
		secretChan, err := k8s.WatchSecret(context.Background(), clientset, config.Namespace, config.SecretName)
		if err != nil {
			logger.Error("failed to watch secret", "name", config.SecretName, "error", err)
			os.Exit(1)
		}

		for secret := range secretChan {
			if tlsCert := loadTLSCert(secret, &config, logger); tlsCert != nil {
				h.UpdateTLSCert(tlsCert)
				logger.Info("secret updated", "name", config.SecretName)
			}
		}
	}()

	mgmtMux := http.NewServeMux()
	mgmtMux.HandleFunc("GET /health", h.HealthHandler)
	mgmtMux.HandleFunc("GET /ready", h.ReadyHandler)

	mgmtSrv := &http.Server{
		Addr:    config.ManagementListenAddr,
		Handler: mgmtMux,
	}

	go func() {
		logger.Info("starting management HTTP server", "addr", mgmtSrv.Addr)
		if err := mgmtSrv.ListenAndServe(); err != nil {
			logger.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	verifier, err := auth.NewVerifier(context.Background(), &config)
	if err != nil {
		logger.Error("failed to initialize OIDC verifier", "error", err)
		os.Exit(1)
	}
	logger.Info("OIDC verifier initialized")

	openApiConfig := huma.DefaultConfig("DT4Mob IoT Certificate Issuance Service", "0.1.0")
	openApiConfig.CreateHooks = nil
	openApiConfig.Components.SecuritySchemes = map[string]*huma.SecurityScheme{
		"openId": {
			Type:             "openIdConnect",
			OpenIDConnectURL: fmt.Sprintf("%s/.well-known/openid-configuration", strings.TrimSuffix(config.OIDCIssuerURI, "/")),
		},
	}

	var root *http.ServeMux
	mux := http.NewServeMux()

	if config.PathPrefix == "" {
		root = mux
	} else {
		strip := strings.TrimSuffix(config.PathPrefix, "/")
		if !strings.HasSuffix(config.PathPrefix, "/") {
			config.PathPrefix += "/"
		}

		openApiConfig.Servers = []*huma.Server{
			{URL: config.PathPrefix},
		}

		root = http.NewServeMux()
		root.Handle(config.PathPrefix, http.StripPrefix(strip, mux))
	}

	api := humago.New(mux, openApiConfig)

	api.UseMiddleware(verifier.NewAuthMiddleware(api))
	api.UseMiddleware(verifier.NewRoleMiddleware(api, config.RequiredRoles))
	huma.Register(api, huma.Operation{
		OperationID: "issue",
		Summary:     "Issue a new certificate for a device",
		Description: `Issues a new certificate that is signed by the tenant's device certificate authority's root certificate.

If a public key is provided, then it will be used for the certificate, otherwise
a new key pair will be generated and the public key used for the certificate and
the private key will also be returned.

Only the following key types are supported:
- RSA (minimum 3072 bits key size)
- ECDSA (P-256, P-384, and P-521 curves only)
- ED25519`,
		Method: http.MethodPost,
		Path:   "/issue",
		Security: []map[string][]string{
			{"openId": {}},
		},
	}, h.IssueHandler)

	srv := &http.Server{
		Addr:    config.ListenAddr,
		Handler: root,
	}

	logger.Info("starting HTTP server", "addr", srv.Addr)
	if err := srv.ListenAndServe(); err != nil {
		logger.Error("server error", "error", err)
		os.Exit(1)
	}
}

func loadTLSCert(secret *corev1.Secret, config *config.Config, logger *slog.Logger) *tls.Certificate {
	certPEM := secret.Data[config.SecretCertSelector]
	keyPEM := secret.Data[config.SecretKeySelector]
	if certPEM == nil || keyPEM == nil {
		logger.Warn("TLS certificate or key not found in secret")
		return nil
	}
	tlsCert, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		logger.Error("failed to parse TLS certificate pair", "error", err)
		return nil
	}
	return &tlsCert
}
