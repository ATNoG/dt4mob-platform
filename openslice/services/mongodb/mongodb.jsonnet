function(name, discriminator="") [
  {
    apiVersion: 'psmdb.percona.com/v1',
    kind: 'PerconaServerMongoDB',
    metadata: {
      name: name + '-mongo',
      namespace: std.extVar('namespace'),
    },
    spec: {
      crVersion: '1.20.1',
      image: 'percona/percona-server-mongodb:' + std.extVar('version'),
      tls: {
        mode: 'requireTLS',
        allowInvalidCertificates: false,
      },
      replsets: [
        {
          name: 'rs0',
          size: 3,
          volumeSpec: {
            persistentVolumeClaim: {
              accessModes: [
                'ReadWriteOnce',
              ],
              resources: {
                requests: {
                  storage: '10Gi',
                },
              },
              storageClassName: 'local-path',
            },
          },
        },
      ],
      sharding: {
        enabled: false,
      },
      users: [
        {
          name: 'CN=' + user,
          db: '$external',
          roles: [
            {
              name: 'dbOwner',
              db: user,
            },
          ],
        } for user in std.split(std.extVar('users'), ',')
      ],
    },
  },
]
