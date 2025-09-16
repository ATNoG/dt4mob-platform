package state

import (
	"bytes"
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/ATNoG/dt4mob/dt4mob-controller/config"
)

type State struct {
	Client http.Client

	Tenant  string
	KeyPair *tls.Certificate
	CaCrt   string

	DevopsPassword string
}

func NewState(config *config.Config) State {
	tlsConfig := &tls.Config{InsecureSkipVerify: true}
	tr := &http.Transport{TLSClientConfig: tlsConfig}
	return State{
		Client: http.Client{Transport: tr},
	}
}

func (state *State) IsInitialized() bool {
	return state.Tenant != "" && state.KeyPair != nil && state.CaCrt != "" && state.DevopsPassword != ""
}

func (state *State) AuthHeader() string {
	auth := fmt.Sprintf("devops:%s", state.DevopsPassword)
	return "Basic " + base64.StdEncoding.EncodeToString([]byte(auth))
}

func (state *State) DittoConnectionUrl(config *config.Config) string {
	return fmt.Sprintf("%s/api/2/connections/hono-kafka-connection-for-%s", config.DittoHost, state.Tenant)
}

func (state *State) HonoTenantUrl(config *config.Config) string {
	return fmt.Sprintf("%s/v1/tenants/%s", config.RegistryHost, state.Tenant)
}

func (state *State) JsonRequest(method string, connectionUrl string, body any) *http.Request {
	serialized, err := json.Marshal(body)
	if err != nil {
		panic(err.Error())
	}

	reqBody := bytes.NewReader(serialized)
	updateReq, err := http.NewRequest(method, connectionUrl, reqBody)
	if err != nil {
		panic(err.Error())
	}
	updateReq.Header.Set("Content-Type", "application/json")
	return updateReq
}
