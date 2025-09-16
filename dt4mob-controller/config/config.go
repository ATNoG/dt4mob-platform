package config

type Config struct {
	Namespace string `env:"TARGET_NAMESPACE"`

	TLSSecretName        string `env:"TLS_SECRET_NAME,required"`
	TLSSecretKeySelector string `env:"TLS_SECRET_KEY_SELECTOR" envDefault:"tls.key"`
	TLSSecretCrtSelector string `env:"TLS_SECRET_CRT_SELECTOR" envDefault:"tls.crt"`

	CASecretName     string `env:"CA_SECRET_NAME"`
	CASecretSelector string `env:"CA_SECRET_SELECTOR" envDefault:"ca.crt"`

	DevopsSecretName     string `env:"DEVOPS_SECRET_NAME,required"`
	DevopsSecretSelector string `env:"DEVOPS_SECRET_SELECTOR" envDefault:"devops-password"`

	TenantConfigMapName     string `env:"TENANT_CONFIG_MAP_NAME,required"`
	TenantConfigMapSelector string `env:"TENANT_CONFIG_MAP_SELECTOR" envDefault:"tenant"`

	RegistryHost string `env:"REGISTRY_HOST,required"`
	DittoHost    string `env:"DITTO_HOST,required"`
	KafkaHost    string `env:"KAFKA_HOST,required"`
}
