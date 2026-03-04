function(name) [
  {
    apiVersion: 'cert-manager.io/v1',
    kind: 'Certificate',
    metadata: {
      name: name + '-' + adapter + '-cert',
      namespace: std.extVar('namespace'),
    },
    spec: {
      commonName: adapter + '-adapter',
      secretName: name + '-' + adapter + '-cert-secret',
      # TODO: Make dnsnames and ipAddresses configurable
      duration: '168h',
      privateKey: {
        algorithm: 'ECDSA',
        size: 256,
	    rotationPolicy: 'Always',
      },
      issuerRef: {
        name: name + '-server-intermediate-ca-issuer',
        kind: 'Issuer',
        group: 'cert-manager.io',
      },
    },
  } for adapter in ['amqp', 'http', 'mqtt']
]
