function(name) [
  {
    apiVersion: 'cert-manager.io/v1',
    kind: 'Certificate',
    metadata: {
      name: name + '-' + server + '-cert',
      namespace: std.extVar('namespace'),
    },
    spec: {
      commonName: server,
      secretName: name + '-' + server + '-cert-secret',
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
  } for server in ['auth-server', 'command-router']
]
