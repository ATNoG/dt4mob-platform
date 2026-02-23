function(name, discriminator="") [
  {
    apiVersion: 'cert-manager.io/v1',
    kind: 'Certificate',
    metadata: {
      name: name + '-mongo-cert-' + user,
      namespace: std.extVar('namespace'),
    },
    spec: {
      commonName: user,
      secretName: name + '-mongo-secret-' + user,
      privateKey: {
        algorithm: 'ECDSA',
        size: 256,
	encoding: 'PKCS8',
      },
      usages: [
        'digital signature',
        'client auth'
      ],
      issuerRef: {
        name: name + '-mongo-psmdb-issuer',
        kind: 'Issuer',
        group: 'cert-manager.io',
      },
    },
  } for user in std.split(std.extVar('users'), ',')
]
