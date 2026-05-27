package handler

import (
	"context"
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/ATNoG/dt4mob/dt4mob-certificate-service/auth"
	"github.com/ATNoG/dt4mob/dt4mob-certificate-service/config"
	"github.com/danielgtaylor/huma/v2"
)

var errInvalidPem = errors.New("invalid PEM block")
var errInvalidPublicKey = errors.New("invalid public key")
var errUnsupportedPublicKey = errors.New("unsupported public key type")
var errCertTTLExceedsMax = errors.New("certificate time to live exceeds the maximum allowed duration")
var errSubjectForbidden = errors.New("not enough permissions to set the certificate subject")

type Handler struct {
	config *config.Config
	logger *slog.Logger

	mu      sync.RWMutex
	tlsCert *tls.Certificate
}

func New(config *config.Config, logger *slog.Logger) *Handler {
	return &Handler{config: config, logger: logger}
}

func (h *Handler) UpdateTLSCert(cert *tls.Certificate) {
	h.mu.Lock()
	h.tlsCert = cert
	h.mu.Unlock()
}

func (h *Handler) GetTLSCert() *tls.Certificate {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.tlsCert
}

func (h *Handler) internalServerError(msg string, err error) error {
	h.logger.Error(msg, "err", err)
	return huma.Error500InternalServerError("internal server error")
}

func (h *Handler) HealthHandler(res http.ResponseWriter, req *http.Request) {
	res.WriteHeader(http.StatusNoContent)
}

func (h *Handler) ReadyHandler(res http.ResponseWriter, req *http.Request) {
	caCrt := h.GetTLSCert()
	if caCrt == nil {
		res.WriteHeader(http.StatusServiceUnavailable)
		_, _ = fmt.Fprintf(res, "service is still initializing")
	} else {
		res.WriteHeader(http.StatusNoContent)
	}
}

type IssueInput struct {
	Body struct {
		PublicKey  string  `json:"pub" required:"false" example:"-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----" doc:"A public key to certify.\n\nGenerated automatically if not present."`
		TimeToLive *uint   `json:"ttl" required:"false" minimum:"1" doc:"The number of hours until the certificate expires."`
		Subject    *string `json:"subject" required:"false" example:"CompanyA" doc:"A custom subject to generate the certificate with.\n\nOnly administrators can use this option."`
	}
}

type IssueOutput struct {
	Body struct {
		Certificate string `json:"cert" example:"-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"`
		PrivateKey  string `json:"priv" required:"false" example:"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"`
	}
}

func (h *Handler) IssueHandler(ctx context.Context, input *IssueInput) (*IssueOutput, error) {
	claims := auth.ClaimsFromContext(ctx)
	caCrt := h.GetTLSCert()

	if caCrt == nil {
		return nil, huma.Error503ServiceUnavailable("service is still initializing")
	}

	resp := &IssueOutput{}

	var pub any
	var err error
	if input.Body.PublicKey != "" {
		pub, err = validatePEMPublicKey(input.Body.PublicKey)
		if err != nil {
			return nil, huma.Error400BadRequest(err.Error())
		}
	} else {
		privateKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		if err != nil {
			return nil, h.internalServerError("Error while generating private key", err)
		}

		pub = privateKey.Public()

		privDer, err := x509.MarshalPKCS8PrivateKey(privateKey)
		if err != nil {
			return nil, h.internalServerError("Error while enconding private key", err)
		}

		resp.Body.PrivateKey = string(pem.EncodeToMemory(&pem.Block{
			Type:  "PRIVATE KEY",
			Bytes: privDer,
		}))
	}

	ttl := h.config.DefaultCertificateTTL
	if input.Body.TimeToLive != nil {
		ttl = time.Duration(*input.Body.TimeToLive) * time.Hour
		if !claims.IsAdmin(h.config) && ttl > h.config.MaxCertificateTTL {
			return nil, huma.Error400BadRequest(errCertTTLExceedsMax.Error())
		}
	}

	subject := claims.Subject
	if input.Body.Subject != nil {
		if !claims.IsAdmin(h.config) {
			return nil, huma.Error403Forbidden(errSubjectForbidden.Error())
		}
		subject = *input.Body.Subject
	}

	notBefore := time.Now()
	notAfter := notBefore.Add(ttl)

	template := x509.Certificate{
		Subject: pkix.Name{
			CommonName: subject,
		},
		IPAddresses:           []net.IP{},
		DNSNames:              []string{},
		NotBefore:             notBefore,
		NotAfter:              notAfter,
		KeyUsage:              x509.KeyUsageDigitalSignature | x509.KeyUsageKeyAgreement,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
		BasicConstraintsValid: true,
	}

	derBytes, err := x509.CreateCertificate(rand.Reader, &template, caCrt.Leaf, pub, caCrt.PrivateKey)
	if err != nil {
		return nil, h.internalServerError("Error while creating certificate", err)
	}

	resp.Body.Certificate = string(pem.EncodeToMemory(&pem.Block{
		Type:  "CERTIFICATE",
		Bytes: derBytes,
	}))
	return resp, nil
}

func validatePEMPublicKey(pemData string) (any, error) {
	block, _ := pem.Decode([]byte(pemData))
	if block == nil {
		return nil, errInvalidPem
	}

	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, errInvalidPublicKey
	}

	switch pub := pub.(type) {
	case *rsa.PublicKey:
		if pub.Size() < 3072/8 {
			return nil, errUnsupportedPublicKey
		}
	case *ecdsa.PublicKey:
		switch pub.Curve.Params().Name {
		case "P-256":
		case "P-384":
		case "P-521":
		default:
			return nil, errUnsupportedPublicKey
		}
	case ed25519.PublicKey:
	default:
		return nil, errUnsupportedPublicKey
	}

	return pub, nil
}
