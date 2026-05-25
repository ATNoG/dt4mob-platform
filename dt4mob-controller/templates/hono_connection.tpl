{
  "name": "[Hono/Kafka] {{ .Tenant }}",
  "connectionType": "kafka",
  "connectionStatus": "open",
  "uri": "ssl://{{ .KafkaHost }}",
  "sources": [
    {
      "addresses": [
        "hono.telemetry.{{ .Tenant }}"
      ],
      "consumerCount": 1,
      "authorizationContext": [
        "pre-authenticated:hono-connection-{{ .Tenant }}"
      ],
      "qos": 0,
      "enforcement": {
        "input": {{ "{{ header:device_id }}" | quote }},
        "filters": [
          {{ "{{ entity:id }}" | quote }}
        ]
      },
      "headerMapping": {},
      "payloadMapping": [],
      "replyTarget": {
        "enabled": true,
        "address": {{ printf "hono.command.%s/{{ thing:id }}" .Tenant | quote }},
        "headerMapping": {
          "device_id": {{ "{{ thing:id }}" | quote }},
          "subject": {{ "{{ header:subject | fn:default(topic:action-subject) | fn:default(topic:criterion) }}-response" | quote }},
          "correlation-id": {{ "{{ header:correlation-id }}" | quote }}
        },
        "expectedResponseTypes": [
          "response",
          "error"
        ]
      },
      "acknowledgementRequests": {
        "includes": [],
        "filter": "fn:delete()"
      },
      "declaredAcks": []
    },
    {
      "addresses": [
        "hono.event.{{ .Tenant }}"
      ],
      "consumerCount": 1,
      "authorizationContext": [
        "pre-authenticated:hono-connection-{{ .Tenant }}"
      ],
      "qos": 1,
      "enforcement": {
        "input": {{ "{{ header:device_id }}" | quote }},
        "filters": [
          {{ "{{ entity:id }}" | quote }}
        ]
      },
      "headerMapping": {},
      "payloadMapping": [],
      "replyTarget": {
        "enabled": true,
        "address": {{ printf "hono.command.%s/{{ thing:id }}" .Tenant | quote }},
        "headerMapping": {
          "device_id": {{ "{{ thing:id }}" | quote }},
          "subject": {{ "{{ header:subject | fn:default(topic:action-subject) | fn:default(topic:criterion) }}-response" | quote }},
          "correlation-id": {{ "{{ header:correlation-id }}" | quote }}
        },
        "expectedResponseTypes": [
          "response",
          "error"
        ]
      },
      "acknowledgementRequests": {
        "includes": []
      },
      "declaredAcks": []
    },
    {
      "addresses": [
        "hono.command_response.{{ .Tenant }}"
      ],
      "consumerCount": 1,
      "authorizationContext": [
        "pre-authenticated:hono-connection-{{ .Tenant }}"
      ],
      "qos": 0,
      "enforcement": {
        "input": {{ "{{ header:device_id }}" | quote }},
        "filters": [
          {{ "{{ entity:id }}" | quote }}
        ]
      },
      "headerMapping": {
        "correlation-id": {{ "{{ header:correlation-id }}" | quote }},
        "status": {{ "{{ header:status }}" | quote }}
      },
      "payloadMapping": [],
      "replyTarget": {
        "enabled": false,
        "expectedResponseTypes": [
          "response",
          "error"
        ]
      },
      "acknowledgementRequests": {
        "includes": [],
        "filter": "fn:delete()"
      },
      "declaredAcks": []
    }
  ],
  "targets": [
    {
      "address": {{ printf "hono.command.%s/{{ thing:id }}" .Tenant | quote }},
      "authorizationContext": [
        "pre-authenticated:hono-connection-{{ .Tenant }}"
      ],
      "headerMapping": {
        "device_id": {{ "{{ thing:id }}" | quote }},
        "subject": {{ "{{ header:subject | fn:default(topic:action-subject) }}" | quote }},
        "correlation-id": {{ "{{ header:correlation-id }}" | quote }},
        "response-required": {{ "{{ header:response-required }}" | quote }}
      },
      "topics": [
        "_/_/things/live/commands",
        "_/_/things/live/messages"
      ]
    },
    {
      "address": {{ printf "hono.command.%s/{{thing:id}}" .Tenant | quote }},
      "authorizationContext": [
        "pre-authenticated:hono-connection-{{ .Tenant }}"
      ],
      "topics": [
        "_/_/things/twin/events",
        "_/_/things/live/events"
      ],
      "headerMapping": {
        "device_id": {{ "{{ thing:id }}" | quote }},
        "subject": {{ "{{ header:subject | fn:default(topic:action-subject) }}" | quote }},
        "correlation-id": {{ "{{ header:correlation-id }}" | quote }}
      }
    }
  ],
  "specificConfig": {
    "saslMechanism": "EXTERNAL",
    "bootstrapServers": "{{ .KafkaHost }}",
    "groupId": {{ printf "%s_{{ connection:id }}" .Tenant | quote }}
  },
  "clientCount": 1,
  "failoverEnabled": true,
  "validateCertificates": true
}
