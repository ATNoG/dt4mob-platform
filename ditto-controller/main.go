package main

import (
	"bytes"
	"context"
	"crypto"
	"crypto/tls"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"log/slog"
	"net/http"

	"github.com/caarlos0/env/v11"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	watchv1 "k8s.io/apimachinery/pkg/watch"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

type Config struct {
	Namespace string `env:"POD_NAMESPACE,required"`
	Tenant    string `env:"TENANT,required"`

	TLSSecretName        string `env:"TLS_SECRET_NAME,required"`
	TLSSecretKeySelector string `env:"TLS_SECRET_KEY_SELECTOR" envDefault:"tls.key"`
	TLSSecretCrtSelector string `env:"TLS_SECRET_CRT_SELECTOR" envDefault:"tls.crt"`

	CASecretName     string `env:"CA_SECRET_NAME"`
	CASecretSelector string `env:"CA_SECRET_SELECTOR" envDefault:"ca.crt"`

	DittoHost      string `env:"DITTO_HOST,required"`
	DevopsPassword string `env:"DITTO_DEVOPS_PASSWORD,required"`
}

type State struct {
	Client        http.Client
	ConnectionUrl string
	AuthHeader    string

	KeyPair *tls.Certificate
	CaCrt   string

	// Cached request
	GetConnectionRequest http.Request
}

func NewState(config *Config) State {
	authHeader := "Basic " + basicAuth("devops", config.DevopsPassword)
	// connectionUrl := fmt.Sprintf("%s/api/2/connections/hono-kafka-connection-for-%s", config.DittoHost, config.Tenant)
	// TODO
	connectionUrl := fmt.Sprintf("%s/api/2/connections/2afcee56-4a53-46d3-8ec9-23ec5b118311", config.DittoHost)

	getConnectionReq, err := http.NewRequest("GET", connectionUrl, nil)
	if err != nil {
		panic(err.Error())
	}
	getConnectionReq.Header.Add("Authorization", authHeader)

	return State{
		Client:               http.Client{},
		ConnectionUrl:        connectionUrl,
		AuthHeader:           authHeader,
		GetConnectionRequest: *getConnectionReq,
	}
}

func basicAuth(username, password string) string {
	auth := fmt.Sprintf("%s:%s", username, password)
	return base64.StdEncoding.EncodeToString([]byte(auth))
}

func watchSecret(ctx context.Context, clientset *kubernetes.Clientset, config *Config, secretName string) <-chan *corev1.Secret {
	watch, err := clientset.CoreV1().Secrets(config.Namespace).Watch(ctx, metav1.ListOptions{
		FieldSelector: fmt.Sprintf("metadata.name=%s", secretName),
	})

	if err != nil {
		panic(err.Error())
	}

	secretChan := make(chan *corev1.Secret)
	go func(in <-chan watchv1.Event, out chan<- *corev1.Secret) {
		for event := range in {
			if event.Type != watchv1.Added && event.Type != watchv1.Modified {
				continue
			}

			secret := event.Object.(*corev1.Secret)
			out <- secret
		}
	}(watch.ResultChan(), secretChan)

	return secretChan
}

func pemPrivateKey(key crypto.PrivateKey) ([]byte, error) {
	pkcs8Key, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return nil, err
	}

	keyPem := pem.EncodeToMemory(&pem.Block{
		Type:  "PRIVATE KEY",
		Bytes: pkcs8Key,
	})
	return keyPem, nil
}

func pemCertificateChain(chain [][]byte) []byte {
	chainPem := new(bytes.Buffer)
	for _, cert := range chain {
		pem.Encode(chainPem, &pem.Block{
			Type:  "CERTIFICATE",
			Bytes: cert,
		})
	}
	return chainPem.Bytes()
}

func updateConnection(config *Config, state *State) {
	if state.KeyPair == nil || state.CaCrt == "" {
		slog.Warn("State is not yet initialized, skipping update")
		return
	}

	res, err := state.Client.Do(&state.GetConnectionRequest)
	if err != nil {
		slog.Error("Failed to get existing connection, skipping update", "error", err)
		return
	}
	defer res.Body.Close()

	switch res.StatusCode {
	case http.StatusNotFound:
		slog.Info("Connection does not yet exist")
		// TODO: Do the creating thing here
	case http.StatusOK:
		bodyBytes, err := io.ReadAll(res.Body)
		if err != nil {
			slog.Error("Failed to get existing connection, skipping update", "error", err)
			return
		}

		var connection map[string]any
		err = json.Unmarshal(bodyBytes, &connection)
		if err != nil {
			slog.Error("Failed to unmarshal connection, skipping update", "error", err)
			return
		}

		pemKey, err := pemPrivateKey(state.KeyPair.PrivateKey)
		if err != nil {
			slog.Error("Failed to marshal private key, skipping update", "error", err)
			return
		}

		connection["ca"] = state.CaCrt
		connection["credentials"] = map[string]any{
			"type": "client-cert",
			"cert": string(pemCertificateChain(state.KeyPair.Certificate)),
			"key":  string(pemKey),
		}
		// TODO: Parse url, remove userinfo, ensure ssl scheme
		// connection["uri"] = "amqps://c2e-hono-dispatch-router-ext:15671"
		connection["validateCertificates"] = true

		serializedConnection, err := json.MarshalIndent(connection, "", "\t")
		if err != nil {
			panic(err.Error())
		}
		reqBody := bytes.NewReader(serializedConnection)

		updateReq, err := http.NewRequest("PUT", state.ConnectionUrl, reqBody)
		if err != nil {
			panic(err.Error())
		}
		updateReq.Header.Add("Authorization", state.AuthHeader)

		res, err := state.Client.Do(updateReq)
		if err != nil {
			slog.Error("Failed to update connection", "error", err)
		} else if res.StatusCode != http.StatusOK && res.StatusCode != http.StatusNoContent {
			bodyBytes, err := io.ReadAll(res.Body)
			if err == nil {
				slog.Error("Failed to update connection", "status", res.Status, "body", string(bodyBytes))
			} else {
				slog.Error("Failed to update connection", "status", res.Status)
			}
		} else {
			slog.Info("Connection updated")
		}
	default:
		bodyBytes, err := io.ReadAll(res.Body)
		if err == nil {
			slog.Error("Failed to get existing connection, skipping update", "status", res.Status, "body", string(bodyBytes))
		} else {
			slog.Error("Failed to get existing connection, skipping update", "status", res.Status)
		}
	}
}

func main() {
	var config Config
	err := env.Parse(&config)
	if err != nil {
		panic(err.Error())
	}

	if config.CASecretName == "" {
		config.CASecretName = config.TLSSecretName
	}

	loadingRules := clientcmd.NewDefaultClientConfigLoadingRules()
	configOverrides := &clientcmd.ConfigOverrides{}

	kubeConfig := clientcmd.NewNonInteractiveDeferredLoadingClientConfig(loadingRules, configOverrides)
	kubeClientConfig, err := kubeConfig.ClientConfig()
	if err != nil {
		// No kubeconfig, try using in cluster config
		kubeClientConfig, err = rest.InClusterConfig()
		if err != nil {
			panic(err.Error())
		}
	}

	// creates the clientset
	clientset, err := kubernetes.NewForConfig(kubeClientConfig)
	if err != nil {
		panic(err.Error())
	}

	redactedConfig := config
	redactedConfig.DevopsPassword = "********"
	slog.Info("Configuration loaded", "config", redactedConfig)

	state := NewState(&config)

	ctx := context.Background()
	tlsWatch := watchSecret(ctx, clientset, &config, config.TLSSecretName)
	caWatch := watchSecret(ctx, clientset, &config, config.CASecretName)

	for {
		select {
		case tlsSecret := <-tlsWatch:
			tlsKey := tlsSecret.Data[config.TLSSecretKeySelector]
			if tlsKey == nil {
				slog.Error("TLS key not found in secret, skipping update")
				continue
			}

			tlsCrt := tlsSecret.Data[config.TLSSecretCrtSelector]
			if tlsCrt == nil {
				slog.Error("TLS certificate not found in secret, skipping update")
				continue
			}

			keypair, err := tls.X509KeyPair(tlsCrt, tlsKey)
			if err != nil {
				slog.Error("Error while creating TLS keypair, skipping update")
				continue
			}
			state.KeyPair = &keypair

			updateConnection(&config, &state)
		case caSecret := <-caWatch:
			caCrt := caSecret.Data[config.CASecretSelector]
			if caCrt == nil {
				slog.Error("CA certificate key not found in secret, skipping update")
				continue
			}

			state.CaCrt = string(caCrt)
			updateConnection(&config, &state)
		}
	}
}
