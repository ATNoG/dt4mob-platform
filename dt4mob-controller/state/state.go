package state

import (
	"bytes"
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"text/template"

	"github.com/ATNoG/dt4mob/dt4mob-controller/config"
	"github.com/ATNoG/dt4mob/dt4mob-controller/templates"
)

type State struct {
	Client http.Client

	KafkaHost string

	Tenant   string
	KeyPair  *tls.Certificate
	CaCrt    string
	TrustCrt string

	DevopsPassword string

	HonoConnectionTemplate   *template.Template
	ExportConnectionTemplate *template.Template
	SystemServicePolicy      map[string]any
}

func NewState(config *config.Config, kafkaHost string) State {
	tlsConfig := &tls.Config{InsecureSkipVerify: true}
	tr := &http.Transport{TLSClientConfig: tlsConfig}

	honoConnTemplate, err := templates.CreateTemplate("Hono connection", templates.HonoConnectionTemplate)
	if err != nil {
		panic(err.Error())
	}
	exportConnTemplate, err := templates.CreateTemplate("Export connection", templates.HonoConnectionTemplate)
	if err != nil {
		panic(err.Error())
	}

	var systemServicePolicy map[string]any
	err = json.Unmarshal([]byte(templates.SystemServicePolicy), &systemServicePolicy)
	if err != nil {
		panic(err.Error())
	}

	return State{
		Client:                   http.Client{Transport: tr},
		KafkaHost:                kafkaHost,
		HonoConnectionTemplate:   honoConnTemplate,
		ExportConnectionTemplate: exportConnTemplate,
		SystemServicePolicy:      systemServicePolicy,
	}
}

type predicate struct {
	Condition bool
	Name      string
}

func pred(Condition bool, Name string) predicate {
	return predicate{Condition, Name}
}

// Returns either an empty string or the name of the component that is not
// yet initialized.
func (state *State) MissingInitialization() string {
	preds := []predicate{
		pred(state.Tenant != "", "Tenant"),
		pred(state.KeyPair != nil, "Key pair"),
		pred(state.CaCrt != "", "CA certificate"),
		pred(state.TrustCrt != "", "Trust certificate"),
		pred(state.DevopsPassword != "", "Devops password"),
	}
	for _, p := range preds {
		if !p.Condition {
			return p.Name
		}
	}

	return ""
}

func (state *State) AuthHeader() string {
	auth := fmt.Sprintf("devops:%s", state.DevopsPassword)
	return "Basic " + base64.StdEncoding.EncodeToString([]byte(auth))
}

func (state *State) DittoHonoConnectionUrl(config *config.Config) string {
	return fmt.Sprintf("%s/api/2/connections/hono-kafka-connection-for-%s", config.DittoHost, state.Tenant)
}

func (state *State) DittoExportConnectionUrl(config *config.Config) string {
	return fmt.Sprintf("%s/api/2/connections/export-kafka-connection-for-%s", config.DittoHost, state.Tenant)
}

func (state *State) DittoPiggyBackUrl(config *config.Config, service string) string {
	return fmt.Sprintf("%s/devops/piggyback/%s?timeout=%d", config.DittoHost, service, config.PiggyBackTimeout)
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
