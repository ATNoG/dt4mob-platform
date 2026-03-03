function(name) [
  {
    apiVersion: 'kafka.strimzi.io/v1',
    kind: 'Kafka',
    metadata: {
      name: name,
      namespace: std.extVar('namespace'),
    },
    spec: {
      kafka: {
        version: '4.1.1',
	metadataVersion: '4.1-IV1',
	listeners: [
	  {
	    name: 'plain',
	    port: 9092,
	    type: 'internal',
	    tls: true,
	    authentication: {
	      type: 'tls'
	    },
	  },
	],
	config: {
          'offsets.topic.replication.factor': 3,
          'transaction.state.log.replication.factor': 3,
          'transaction.state.log.min.isr': 2,
          'default.replication.factor': 3,
          'min.insync.replicas': 2,
	},
      },
      entityOperator: {
        topicOperator: {},
        userOperator: {},
      },
    },
  },
  {
    apiVersion: 'kafka.strimzi.io/v1',
    kind: 'KafkaNodePool',
    metadata: {
      name: name + '-controllers',
      namespace: std.extVar('namespace'),
      labels: {
        'strimzi.io/cluster': name,
      },
    },
    spec: {
      replicas: 3,
      roles: ['controller'],
      crVersion: '1.20.1',
      storage: {
        type: 'jbod',
	volumes: [
	  {
	    id: 0,
	    type: 'persistent-claim',
	    size: '10Gi',
	    kraftMetadata: 'shared',
	    deleteClaim: false,
	  }
	],
      },
    },
  },
  {
    apiVersion: 'kafka.strimzi.io/v1',
    kind: 'KafkaNodePool',
    metadata: {
      name: name + '-brokers',
      namespace: std.extVar('namespace'),
      labels: {
        'strimzi.io/cluster': name,
      },
    },
    spec: {
      replicas: 3,
      roles: ['broker'],
      crVersion: '1.20.1',
      storage: {
        type: 'jbod',
	volumes: [
	  {
	    id: 0,
	    type: 'persistent-claim',
	    size: '10Gi',
	    kraftMetadata: 'shared',
	    deleteClaim: false,
	  }
	],
      },
    },
  },
]
