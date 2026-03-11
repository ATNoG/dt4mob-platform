function(name) [
  {
    apiVersion: 'v1',
    kind: 'ConfigMap',
    metadata: {
      name: name + '-config',
      namespace: std.extVar('namespace'),
    },
    data: {
      'tenant': std.extVar('tenant'),
    },
  },
]
