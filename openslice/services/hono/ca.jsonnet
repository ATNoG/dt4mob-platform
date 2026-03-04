function(name) [
  {
    apiVersion: 'cert-manager.io/v1',
    kind: 'Issuer',
    metadata: {
      name: name + '-selfsigned-issuer',
      namespace: std.extVar('namespace'),
    },
    spec: {
      selfSigned: {}
    },
  },
  {
    apiVersion: 'cert-manager.io/v1',
    kind: 'Certificate',
    metadata: {
      name: name + '-root-ca',
      namespace: std.extVar('namespace'),
    },
    spec: {
      isCA: true,
      duration: "87660h", # 10 years
      commonName: name + '-root-ca',
      secretName: name + '-root-ca-secret',
      privateKey: {
        algorithm: 'ECDSA',
        size: 256,
        rotationPolicy: 'Always',
      },
      issuerRef: {
        name: name + '-selfsigned-issuer',
        kind: 'Issuer',
        group: 'cert-manager.io'
      },
    },
  },
  {
    apiVersion: 'cert-manager.io/v1',
    kind: 'Issuer',
    metadata: {
      name: name + '-root-ca-issuer',
      namespace: std.extVar('namespace'),
    },
    spec: {
      ca: {
        secretName: name + '-root-ca-secret',
      }
    },
  },
  {
    apiVersion: 'cert-manager.io/v1',
    kind: 'Certificate',
    metadata: {
      name: name + '-server-intermediate-ca',
      namespace: std.extVar('namespace'),
    },
    spec: {
      isCA: true,
      duration: "720h", # 30 days
      commonName: name + '-server-intermediate-ca',
      secretName: name + '-server-intermediate-ca-secret',
      privateKey: {
        algorithm: 'ECDSA',
        size: 256,
        rotationPolicy: 'Always',
      },
      issuerRef: {
        name: name + '-root-ca-issuer',
        kind: 'Issuer',
        group: 'cert-manager.io'
      },
    },
  },
  {
    apiVersion: 'cert-manager.io/v1',
    kind: 'Issuer',
    metadata: {
      name: name + '-server-intermediate-ca-issuer',
      namespace: std.extVar('namespace'),
    },
    spec: {
      ca: {
        secretName: name + '-server-intermediate-ca-secret',
      }
    },
  },
]
