package main

import (
	"bytes"
	"context"
	"crypto/tls"
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"text/template"
	"time"

	"github.com/caarlos0/env/v11"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"

	"github.com/ATNoG/dt4mob/dt4mob-controller/config"
	"github.com/ATNoG/dt4mob/dt4mob-controller/state"
	"github.com/ATNoG/dt4mob/dt4mob-controller/utils"
)

//go:embed connection.tpl
var rawConnectionTemplate string

const MAX_RETRIES int = 5

func updateHonoTenant(config *config.Config, state *state.State) bool {
	tenantUrl := state.HonoTenantUrl(config)

	body := map[string]any{}
	createReq := state.JsonRequest("POST", tenantUrl, body)
	res, err := state.Client.Do(createReq)

	switch {
	case err != nil:
		slog.Error("Failed to create tenant", "error", err)
	case res.StatusCode == http.StatusCreated:
		slog.Info("Tenant created")
		return false
	case res.StatusCode == http.StatusConflict:
		updateReq := state.JsonRequest("PUT", tenantUrl, body)
		res, err := state.Client.Do(updateReq)

		switch {
		case err != nil:
			slog.Error("Failed to update tenant", "error", err)
		case res.StatusCode == http.StatusNoContent:
			slog.Info("Tenant updated")
			return false
		default:
			utils.LogHttpError("Failed to update tenant", res)
		}
	default:
		utils.LogHttpError("Failed to create tenant", res)
	}

	return true
}

func updateConnection(config *config.Config, state *state.State, connectionUrl string, connection map[string]any) bool {
	pemKey, err := utils.PemPrivateKey(state.KeyPair.PrivateKey)
	if err != nil {
		slog.Error("Failed to marshal private key, skipping update", "error", err)
		return false
	}

	connection["ca"] = state.CaCrt
	connection["credentials"] = map[string]any{
		"type": "client-cert",
		"cert": string(utils.PemCertificateChain(state.KeyPair.Certificate)),
		"key":  string(pemKey),
	}
	connection["uri"] = fmt.Sprintf("ssl://%s", state.KafkaHost)
	connection["validateCertificates"] = true

	updateReq := state.JsonRequest("PUT", connectionUrl, connection)
	updateReq.Header.Set("Authorization", state.AuthHeader())

	res, err := state.Client.Do(updateReq)
	if err != nil {
		slog.Error("Failed to update connection", "error", err)
	} else if res.StatusCode < 200 || res.StatusCode > 299 {
		utils.LogHttpError("Failed to update connection", res)
	} else {
		slog.Info("Connection updated")
		return false
	}

	return true
}

func update(config *config.Config, state *state.State) bool {
	if !state.IsInitialized() {
		slog.Warn("State is not yet initialized, skipping update")
		return false
	}

	retry := updateHonoTenant(config, state)

	connectionUrl := state.DittoConnectionUrl(config)

	getConnectionReq, err := http.NewRequest("GET", connectionUrl, nil)
	if err != nil {
		panic(err.Error())
	}
	getConnectionReq.Header.Set("Authorization", state.AuthHeader())

	res, err := state.Client.Do(getConnectionReq)
	if err != nil {
		slog.Error("Failed to get existing connection, skipping update", "error", err)
		return true
	}
	//nolint:errcheck
	defer res.Body.Close()

	var connectionBytes []byte
	switch res.StatusCode {
	case http.StatusNotFound:
		slog.Info("Connection does not yet exist")

		tmpl, err := template.New("connection").Funcs(template.FuncMap{
			"quote": func(val string) string {
				return fmt.Sprintf("\"%s\"", val)
			},
		}).Parse(rawConnectionTemplate)
		if err != nil {
			panic(err.Error())
		}

		writer := new(bytes.Buffer)
		err = tmpl.Execute(writer, map[string]any{
			"Tenant":    state.Tenant,
			"KafkaHost": state.KafkaHost,
		})
		if err != nil {
			panic(err.Error())
		}
		connectionBytes = writer.Bytes()
	case http.StatusOK:
		connectionBytes, err = io.ReadAll(res.Body)
		if err != nil {
			slog.Error("Failed to get existing connection, skipping update", "error", err)
			return true
		}
	default:
		utils.LogHttpError("Failed to get existing connection, skipping update", res)
		return true
	}

	var connection map[string]any
	err = json.Unmarshal(connectionBytes, &connection)
	if err != nil {
		slog.Error("Failed to unmarshal connection, skipping update", "error", err)
		return true
	}

	retry = retry || updateConnection(config, state, connectionUrl, connection)
	return retry
}

func main() {
	var config config.Config
	err := env.Parse(&config)
	if err != nil {
		panic(err.Error())
	}

	if config.CASecretName == "" {
		config.CASecretName = config.TLSSecretName
	}

	if config.Namespace == "" {
		data, err := os.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
		if err != nil {
			panic(err.Error())
		}
		config.Namespace = string(data)
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

	slog.Info("Configuration loaded", "config", config)

	ctx := context.Background()

	slog.Info("Waiting for device registry to be ready")
	registrySvc := utils.WaitService(ctx, clientset, &config, config.RegistryService)
	if config.RegistryHost == "" {
		config.RegistryHost = fmt.Sprintf("http://%s:%d", config.RegistryService, utils.GetPortByName(registrySvc, "http").Port)
	}

	slog.Info("Waiting for ditto gateway to be ready")
	dittoSvc := utils.WaitService(ctx, clientset, &config, config.DittoService)
	if config.DittoHost == "" {
		config.DittoHost = fmt.Sprintf("http://%s:%d", config.DittoService, utils.GetPortByName(dittoSvc, "http").Port)
	}

	kafkaSvc := utils.WaitService(ctx, clientset, &config, config.KafkaService)
	kafkaHost := fmt.Sprintf("%s:%d", config.KafkaService, utils.GetPortByName(kafkaSvc, "tcp-clients").Port)

	state := state.NewState(&config, kafkaHost)

	tlsWatch := utils.WatchSecret(ctx, clientset, &config, config.TLSSecretName)
	caWatch := utils.WatchSecret(ctx, clientset, &config, config.CASecretName)
	devopsWatch := utils.WatchSecret(ctx, clientset, &config, config.DevopsSecretName)
	tenantWatch := utils.WatchConfigMap(ctx, clientset, &config, config.TenantConfigMapName)

	retries := MAX_RETRIES
	retry := false
	retryTimer := time.NewTicker(5 * time.Second)

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
		case caSecret := <-caWatch:
			caCrt := caSecret.Data[config.CASecretSelector]
			if caCrt == nil {
				slog.Error("CA certificate key not found in secret, skipping update")
				continue
			}
			state.CaCrt = string(caCrt)
		case devopsSecret := <-devopsWatch:
			devopsPassword := devopsSecret.Data[config.DevopsSecretSelector]
			if devopsPassword == nil {
				slog.Error("Devops password key not found in secret, skipping update")
				continue
			}
			state.DevopsPassword = string(devopsPassword)
		case tenantConfigMap := <-tenantWatch:
			tenant, ok := tenantConfigMap.Data[config.TenantConfigMapSelector]
			if !ok {
				slog.Error("Tenant key not found in config map, skipping update")
				continue
			}
			state.Tenant = tenant
		case <-retryTimer.C:
			if retry {
				slog.Info("Retrying update")

				retries--
				retry = update(&config, &state)

				if retries == 0 && retry {
					panic("Too many retries")
				}
			}

			continue
		}

		retries = MAX_RETRIES
		retry = update(&config, &state)
	}
}
