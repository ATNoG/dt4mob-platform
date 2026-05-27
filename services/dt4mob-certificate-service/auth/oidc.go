package auth

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"net/http"
	"os"
	"slices"
	"strings"

	"github.com/ATNoG/dt4mob/dt4mob-certificate-service/config"
	"github.com/coreos/go-oidc/v3/oidc"
	"github.com/danielgtaylor/huma/v2"
)

var ErrNoBearerToken = errors.New("no bearer token")

type ResourceAccess struct {
	Roles []string `json:"roles"`
}

type Claims struct {
	Issuer         string                    `json:"iss"`
	Subject        string                    `json:"sub"`
	ResourceAccess map[string]ResourceAccess `json:"resource_access"`
}

type claimsContextKey struct{}

func (claims *Claims) HasRole(clientID, role string) bool {
	resource_access, ok := claims.ResourceAccess[clientID]
	if !ok {
		return false
	}
	return slices.Contains(resource_access.Roles, role)
}

func (claims *Claims) IsAdmin(config *config.Config) bool {
	return claims.HasRole(config.OIDCClientID, config.AdminRole)
}

func ClaimsFromContext(ctx context.Context) *Claims {
	claims, _ := ctx.Value(claimsContextKey{}).(*Claims)
	return claims
}

type Verifier struct {
	verifier *oidc.IDTokenVerifier
	config   *config.Config
}

func NewVerifier(parentCtx context.Context, config *config.Config) (*Verifier, error) {
	oidcClient := &http.Client{}

	if config.OIDCCACertificate != "" {
		caCert, err := os.ReadFile(config.OIDCCACertificate)
		if err != nil {
			return nil, fmt.Errorf("failed to read CA certificate: %w", err)
		}

		caCertPool := x509.NewCertPool()
		if !caCertPool.AppendCertsFromPEM(caCert) {
			return nil, fmt.Errorf("failed to append CA certificate to pool: %w", err)
		}

		oidcClient.Transport = &http.Transport{
			TLSClientConfig: &tls.Config{RootCAs: caCertPool},
		}
	}

	ctx := oidc.ClientContext(parentCtx, oidcClient)

	provider, err := oidc.NewProvider(ctx, config.OIDCIssuerURI)
	if err != nil {
		return nil, fmt.Errorf("oidc provider %q: %w", config.OIDCIssuerURI, err)
	}

	verifier := provider.Verifier(&oidc.Config{
		SkipClientIDCheck: true,
		SkipIssuerCheck:   len(config.OIDCTrustedIssuers) > 0,
	})

	return &Verifier{verifier, config}, nil
}

var errAuthorizationScheme = errors.New("invalid authorization scheme")
var errInvalidToken = errors.New("invalid token")
var errInvalidTokenIssuer = errors.New("invalid token issuer")
var errMissingRole = errors.New("missing role")

func (v *Verifier) NewAuthMiddleware(api huma.API) func(ctx huma.Context, next func(huma.Context)) {
	return func(ctx huma.Context, next func(huma.Context)) {
		rawToken, err := extractBearerToken(ctx)
		if err != nil {
			_ = huma.WriteErr(api, ctx, http.StatusUnauthorized, "Unauthorized", errAuthorizationScheme)
			return
		}

		idToken, err := v.verifier.Verify(ctx.Context(), rawToken)
		if err != nil {
			_ = huma.WriteErr(api, ctx, http.StatusUnauthorized, "Unauthorized", errInvalidToken)
			return
		}

		var claims Claims
		if err := idToken.Claims(&claims); err != nil {
			_ = huma.WriteErr(api, ctx, http.StatusUnauthorized, "Unauthorized", errInvalidToken)
			return
		}

		if len(v.config.OIDCTrustedIssuers) > 0 && !slices.Contains(v.config.OIDCTrustedIssuers, claims.Issuer) {
			_ = huma.WriteErr(api, ctx, http.StatusUnauthorized, "Unauthorized", errInvalidTokenIssuer)
			return
		}

		ctx = huma.WithValue(ctx, claimsContextKey{}, &claims)
		next(ctx)
	}
}

func (v *Verifier) NewRoleMiddleware(api huma.API, roles []string) func(ctx huma.Context, next func(huma.Context)) {
	return func(ctx huma.Context, next func(huma.Context)) {
		claims := ctx.Context().Value(claimsContextKey{}).(*Claims)
		if claims == nil {
			_ = huma.WriteErr(api, ctx, http.StatusUnauthorized, "Unauthorized", errAuthorizationScheme)
			return
		}

		resource_access, ok := claims.ResourceAccess[v.config.OIDCClientID]
		if !ok {
			_ = huma.WriteErr(api, ctx, http.StatusForbidden, "Forbidden", errMissingRole)
			return
		}

		if slices.Contains(resource_access.Roles, v.config.AdminRole) {
			next(ctx)
			return
		}

		for _, required := range roles {
			if slices.Contains(resource_access.Roles, required) {
				next(ctx)
				return
			}
		}

		_ = huma.WriteErr(api, ctx, http.StatusForbidden, "Forbidden", errMissingRole)
	}
}

func extractBearerToken(ctx huma.Context) (string, error) {
	auth := ctx.Header("Authorization")
	if !strings.HasPrefix(auth, "Bearer ") {
		return "", ErrNoBearerToken
	}
	return strings.TrimPrefix(auth, "Bearer "), nil
}
