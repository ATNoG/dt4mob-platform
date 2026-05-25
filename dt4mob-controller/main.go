package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"errors"
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

const MAX_RETRIES int = 5

func updateHonoTenant(config *config.Config, state *state.State) bool {
	tenantUrl := state.HonoTenantUrl(config)

	body := map[string]any{
		"trusted-ca": []any{
			map[string]any{
				"id":                                   "operator-managed-ca",
				"cert":                                 base64.StdEncoding.EncodeToString([]byte(state.TrustCrt)),
				"auto-provisioning-enabled":            true,
				"auto-provisioning-device-id-template": "{{subject-cn}}",
			},
		},
	}
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

func getConnection(config *config.Config, state *state.State, connectionUrl string, templateFallback *template.Template) (map[string]any, error) {
	getConnectionReq, err := http.NewRequest("GET", connectionUrl, nil)
	if err != nil {
		panic(err.Error())
	}
	getConnectionReq.Header.Set("Authorization", state.AuthHeader())

	res, err := state.Client.Do(getConnectionReq)
	if err != nil {
		return nil, err
	}
	//nolint:errcheck
	defer res.Body.Close()

	var connectionBytes []byte
	switch res.StatusCode {
	case http.StatusNotFound:
		writer := new(bytes.Buffer)
		err = templateFallback.Execute(writer, map[string]any{
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
			return nil, err
		}
	default:
		utils.LogHttpError("Unexpected response to get connection request", res)
		return nil, errors.New("bad status code")
	}

	var connection map[string]any
	err = json.Unmarshal(connectionBytes, &connection)
	if err != nil {
		return nil, err
	}

	return connection, nil
}

func updateConnection(config *config.Config, state *state.State, connectionUrl string, connection map[string]any) error {
	pemKey, err := utils.PemPrivateKey(state.KeyPair.PrivateKey)
	if err != nil {
		return err
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
		return err
	} else if res.StatusCode < 200 || res.StatusCode > 299 {
		utils.LogHttpError("Error when updating connection", res)
		return errors.New("bad status code")
	}

	slog.Info("Connection updated", "connection", connectionUrl)
	return nil
}

func updatePolicy(config *config.Config, state *state.State, policyId string, policy map[string]any) error {
	updateReq := state.JsonRequest("POST", state.DittoPiggyBackUrl(config, "policies"), map[string]any{
		"targetActorSelection": "/system/sharding/policy",
		"headers": map[string]any{
			"aggregate":      false,
			"is-group-topic": true,
			"ditto-sudo":     true,
		},
		"piggybackCommand": map[string]any{
			"type": "policies.commands:modifyPolicy",
			"policy": map[string]any{
				"policyId": policyId,
				"entries":  policy,
			},
		},
	})
	updateReq.Header.Set("Authorization", state.AuthHeader())

	res, err := state.Client.Do(updateReq)
	if err != nil {
		return err
	} else if res.StatusCode < 200 || res.StatusCode > 299 {
		utils.LogHttpError("Error when updating policy", res)
		return errors.New("bad status code")
	}

	slog.Info("Policy updated", "policy", policyId)
	return nil
}

func update(config *config.Config, state *state.State) bool {
	missing := state.MissingInitialization()
	if missing != "" {
		slog.Warn("State is not yet initialized, skipping update", "missing", missing)
		return false
	}

	shouldRetry := updateHonoTenant(config, state)

	honoConnectionUrl := state.DittoHonoConnectionUrl(config)
	honoConnection, err := getConnection(config, state, honoConnectionUrl, state.HonoConnectionTemplate)
	if err != nil {
		slog.Error("Failed to get hono connection", "error", err)
		shouldRetry = true
	} else {
		err = updateConnection(config, state, honoConnectionUrl, honoConnection)
		if err != nil {
			slog.Error("Failed to update hono connection", "error", err)
			shouldRetry = true
		}
	}

	exportConnectionUrl := state.DittoExportConnectionUrl(config)
	exportConnection, err := getConnection(config, state, exportConnectionUrl, state.ExportConnectionTemplate)
	if err != nil {
		slog.Error("Failed to get export connection", "error", err)
		shouldRetry = true
	} else {
		err = updateConnection(config, state, exportConnectionUrl, exportConnection)
		if err != nil {
			slog.Error("Failed to update export connection", "error", err)
			shouldRetry = true
		}
	}

	err = updatePolicy(config, state, config.SystemServicePolicy, state.SystemServicePolicy)
	if err != nil {
		slog.Error("Failed to update system service policy", "error", err)
		shouldRetry = true
	}

	if shouldRetry {
		slog.Error("The update didn't complete and will be retried")
	}

	return shouldRetry
}

func main() {
	var config config.Config
	err := env.Parse(&config)
	if err != nil {
		panic(err.Error())
	}

	var level slog.Level
	err = level.UnmarshalText([]byte(config.LogLevel))
	if err != nil {
		panic(err.Error())
	}

	handler := slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: level,
	})
	logger := slog.New(handler)
	slog.SetDefault(logger)

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
	tenantTrustWatch := utils.WatchSecret(ctx, clientset, &config, config.TenantTLSTrustSecretName)
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
			slog.Debug("Loaded TLS key pair")
		case caSecret := <-caWatch:
			caCrt := caSecret.Data[config.CASecretSelector]
			if caCrt == nil {
				slog.Error("CA certificate key not found in secret, skipping update")
				continue
			}
			state.CaCrt = string(caCrt)
			slog.Debug("Loaded CA certificate")
		case tenantTrustSecret := <-tenantTrustWatch:
			caCrt := tenantTrustSecret.Data[config.TenantTLSTrustSecretSelector]
			if caCrt == nil {
				slog.Error("CA certificate key not found in secret, skipping update")
				continue
			}
			state.TrustCrt = string(caCrt)
			slog.Debug("Loaded Tenant trust certificate")
		case devopsSecret := <-devopsWatch:
			devopsPassword := devopsSecret.Data[config.DevopsSecretSelector]
			if devopsPassword == nil {
				slog.Error("Devops password key not found in secret, skipping update")
				continue
			}
			state.DevopsPassword = string(devopsPassword)
			slog.Debug("Loaded Devops password")
		case tenantConfigMap := <-tenantWatch:
			tenant, ok := tenantConfigMap.Data[config.TenantConfigMapSelector]
			if !ok {
				slog.Error("Tenant key not found in config map, skipping update")
				continue
			}
			state.Tenant = tenant
			slog.Debug("Loaded Tenant config name")
		case <-retryTimer.C:
			if retry {
				slog.Info("Retrying update")
				retries--
				if update(&config, &state) && retries == 0 {
					panic("Too many retries")
				}
			}

			continue
		}

		retries = MAX_RETRIES
		retry = update(&config, &state)
	}
}
