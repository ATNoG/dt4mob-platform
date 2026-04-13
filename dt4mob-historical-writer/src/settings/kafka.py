from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class KafkaSettings(BaseSettings):
    bootstrap_servers: str = Field(validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    security_protocol: str = Field(validation_alias="KAFKA_SECURITY_PROTOCOL")
    ssl_ca_location: str = Field(validation_alias="KAFKA_SSL_CA_LOCATION")
    ssl_certificate_location: str = Field(validation_alias="KAFKA_SSL_CERTIFICATE_LOCATION")
    ssl_key_location: str = Field(validation_alias="KAFKA_SSL_KEY_LOCATION")
    consumer_group: str = Field(validation_alias="KAFKA_CONSUMER_GROUP")
    topic: str = Field(validation_alias="KAFKA_TOPIC")
    auto_offset_reset: str = Field(validation_alias="KAFKA_AUTO_OFFSET_RESET")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def as_dict(self):
        return {
            'bootstrap.servers': self.bootstrap_servers,
            'security.protocol': self.security_protocol,
            'ssl.ca.location': self.ssl_ca_location,
            'ssl.certificate.location': self.ssl_certificate_location,
            'ssl.key.location': self.ssl_key_location,
            'group.id': self.consumer_group,
            'auto.offset.reset': self.auto_offset_reset,
            'enable.auto.commit': False
        }