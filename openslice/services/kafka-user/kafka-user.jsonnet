function(name) [
  {
    apiVersion: 'kafka.strimzi.io/v1',
    kind: 'KafkaUser',
    metadata: {
      name: name + "-kafka-user-" + std.extVar('user'),
      namespace: std.extVar('namespace'),
      labels: {
        'strimzi.io/cluster': std.extVar('cluster'),
      },
    },
    spec: {
      authentication: {
        type: 'tls',
      },
    },
  },
]
