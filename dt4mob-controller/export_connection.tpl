{
  "name": "[Southbound/Kafka] {{ .Tenant }}",
  "connectionType": "kafka",
  "connectionStatus": "open",
  "uri": "ssl://{{ .KafkaHost }}",
  "sources": [],
  "targets": [
    {
      "address": "exports-{{ .Tenant }}",
      "topics": [
        "_/_/things/twin/events"
      ],
      "authorizationContext": [
        "pre-authenticated:kafka-export-connection-{{ .Tenant }}"
      ],
      "headerMapping": {
        "device_id": {{ "{{ thing:id }}" | quote }},
        "response-required": {{ "{{ header:subject | fn:default(topic:action-subject) }}" | quote }},
        "subject": {{ "{{ header:subject | fn:default(topic:action-subject) }}" | quote }},
        "correlation-id": {{ "{{ header:correlation-id }}" | quote }}
      }
    }
  ],
  "specificConfig": {
    "saslMechanism": "EXTERNAL",
    "bootstrapServers": "{{ .KafkaHost }}",
    "groupId": {{ printf "%s_{{ connection:id }}" .Tenant | quote }},
    "acks": "all"
  },
  "clientCount": 1,
  "failoverEnabled": true,
  "validateCertificates": true
}
