function(name) [
  {
    apiVersion: 'kafka.strimzi.io/v1',
    kind: 'KafkaUser',
    metadata: {
      name: name + "-kafka-user-" + user,
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
  } for user in std.split(std.extVar('users'), ',')
]
