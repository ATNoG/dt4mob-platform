# Installation {#sec:installation}

## Prerequisites

A Kubernetes cluster running one of the three most recent minor releases is
required. Additionally, due to limitations of Helm chart packaging the following
components need to be installed beforehand in the cluster:

- [Ingress NGINX Controller](https://github.com/kubernetes/ingress-nginx)
- [cert-manager](https://cert-manager.io/)
- [Strimzi Kafka Operator](https://strimzi.io/)
- [Percona Operator for MongoDB](https://docs.percona.com/percona-operator-for-mongodb/)
- [CloudNativePG](https://cloudnative-pg.io/)
- [SeaweedFS Operator](https://github.com/seaweedfs/seaweedfs-operator/)

The minimum size of the cluster necessary to run all the components is 8 vCPUs,
16 GiB of RAM, and 200 GiB of storage. More resources may be required to scale
the cluster to meet the demands. There is no constraint on the minimum number
of nodes in the cluster except for high availability scenariosi where at least 3
nodes are required.

## Deploying

The dt4mob platform can be deployed in one go using the standard `helm install`
command:

```sh
$ helm install dt4mob --values values.yaml ./dt4mob-platform/charts/dt4mob
```

Unfortunately, due to technical limitations, the release should be named
`dt4mob` (It is technically possible to use a different name but it requires a
great amount of reconfiguration and is not supported).

The `values.yaml` file is required and should at a minimum have the following
structure:

```yaml
global:
  host: dt4mob.av.it.pt

ditto:
  ingress:
    host: dt4mob.av.it.pt 

  gateway: 
    config:
      authentication:
        oauth:
          openidConnectIssuers:
            keycloak:
              issuer: "dt4mob.av.it.pt/auth/realms/dt4mob"
```

The value of `host` in both instances is the domain name where the platform
will be exposed. This can be a public domain, an internal domain, or even a
placeholder domain, but the values must be set. The value of `issuer` must
be set manually, due to constraints of Helm packaging, to the same value of
`global.host` with `/auth/realms/dt4mob` appended at the end.

It also might be of interest to change the `global.tenant` value from its
default of `test-tenant` to a more appropriate name. This will change the name
of the tenant created in Hono and also the name of the connections created in
Ditto. This value can be changed later but requires manual work to migrate all
the previous uses of the old tenant name to the new one.

## Exposing the platform

The platform has two parts that can be separately exposed and through different
mechanisms:

- Hono adapters
- Platform APIs

The following sections address each individually.

### Hono adapters

The default installation platform exposes the Hono adapters through the use
of Kubernetes `NodePort` services, the ports are dinamically allocated by
the cluster to ensure they don't conflict with any existing allocations. The
following command can be used to retrieve the allocated ports.

```sh
$ kubectl get svc dt4mob-hono-adapter-http dt4mob-hono-adapter-mqtt dt4mob-hono-adapter-amqp
```

Contacting any of the nodes in the Kubernetes Cluster on these ports will
forward the traffic to the respective Hono adapter. If instead its desirable
to expose these services using a load balancer (either cloud or on-prem), the
following change to the values file must be applied.

```yaml
hono:
  useDynamicNodePorts: false
  useLoadBalancer: true
```

Communication with the adapters must done through TLS for all protocols, this
is required for not only protection of the data sent and received, but also for
the authentication of the edge devices which is done through the use of X.509
certificates. All certificates used for communication with Hono are signed by
a self-signed root certificate whose lifecycle is managed by the cluster and as
such must be added to the trust store of the edge devices. The root certificate
can be obtained using the following command:

```sh
$ kubectl get secrets dt4mob-tenant-ca-secret -o jsonpath="{.data['ca\.crt']}" | base64 -d
```

The adapters' certificates will always include the domain name configured in the
`global.host` option in their Subject Alternative Name (SAN) extension values.
In some cases, however, DNS might not be available, desired, or the domain does
not resolve externally, and as such it might be necessary to connect directly
to the adapters through the nodes' IP address. For such scenarios, the SAN
values can be further extended with arbitrary IP addresses through the following
modification to the values file.

```yaml
dt4mob-ingress:
  addresses:
  - 193.136.93.66
```

Under certain network and especially firewall configurations, accessing services
through non standard ports may be impossible. In order to combat this problem
it is possible to deploy ingresses that route traffic based on the Server Name
Indication (SNI) of the TLS Client Hello. In practice this allows the adapters
to be exposed through the standard HTTPS 443 port through different domains
that are then routed to their respective adapters without the need for any
encapsulation. To enable this, the following snippet should be added to the
values file, each adapter can have its ingress enabled individually and they
must have different domain names for the host that must also be different from
the one configured for the platform in `global.host`.

```yaml
dt4mob-ingress:
  http:
    enabled: true
    host: "dt4mob-ingress.av.it.pt"
  mqtt:
    enabled: true
    host: "mqtt.dt4mob-ingress.av.it.pt"
  amqp:
    enabled: true
    host: "amqp.dt4mob-ingress.av.it.pt"
```

No further changes are required to the adapters' certificates configuration as
they will automatically pick up the values configured for the ingresses in their
SAN values.

### Platform APIs

The platform APIs are exposed through the domain name configured in the
`global.host` option. However, this is done through an ingress using a
self-signed certificate by default. Cert-manager is used for the issuance and
lifecycle of the certificate, as such, to use a certificate issued by a CA,
the issuer must be configured. This can be done in one of two way, by using an
existing issuer present in the Cluster:

```yaml
ingressTLS:
  issuer:
    existingIssuer:
      name: "my-cluster-issuer"
      kind: ClusterIssuer
      group: cert-manager.io
```

Or by modifying the existing issuer to not use self-signed certificates and
instead use, for example, an Automatic Certificate Management Environment
(ACME), like Let's Encrypt:

```yaml
ingressTLS:
  issuer:
    spec:
      selfSigned: null
      acme:
        server: https://acme-v02.api.letsencrypt.org/directory
        privateKeySecretRef:
          name: dt4mob-letsencrypt-issuer-account-key
        solvers:
        - http01:
            ingress:
              ingressClassName: nginx
```

For more details consult the cert-manager documentation for issuers [^cert-manager-issuer]. 

[^cert-manager-issuer]: <https://cert-manager.io/docs/configuration/>

## Backups configuration

The platform state is mainly kept in a MongoDB database that should be backed
up for fault-tolerance, and business continuity reasons. Backups are handled
through the Percona Operator for MongoDB and require extra configuration in the
chart values to configure the backups and their storage location. The following
example shows the configuration for backups to an Network File System (NFS)
server with Point-In-Time recovery (PITR) and zstd compression.

```yaml
psmdb-db:
  replsets:
    rs0:
      sidecarVolumes:
      - name: backup-nfs-vol
        nfs:
          server: "192.168.100.100"
          path: "/var/nfs/export/staging-mongodb-backup"
  backup:
    enabled: true
    volumeMounts:
    - mountPath: /home/mongodb/nfs
      name: backup-nfs-vol
    storages:
      backup-nfs:
        type: filesystem
        filesystem:
          path: /home/mongodb/nfs
    pitr:
      enabled: true
      compressionType: zstd
      compressionLevel: 2
```

This configuration allows for the creation of on-demand backups. For scheduled
backups, the `psmdb-db.backup.tasks` option can be used to define the schedule
for performing the backups and even multiple schedules for different backup
types. The following example shows a configuration for incremental backups daily
with full base backups at the start of every week and retentions configured.

```yaml
psmdb-db:
  backup:
    tasks:
    - name: daily-incremental
      enabled: true
      schedule: "0 1 * * *"
      type: incremental
      retention:
        count: 25
        type: count
        deleteFromStorage: true
      storageName: backup-nfs
      compressionType: zstd
      compressionLevel: 2
    - name: weekly-base
      enabled: true
      schedule: "0 5 * * 0"
      type: incremental-base
      retention:
        count: 5
        type: count
        deleteFromStorage: true
      storageName: backup-nfs
      compressionType: zstd
      compressionLevel: 2
```

For more details consult the Percona Operator for MongoDB documentation about
backups [^mongodb-backups].

[^mongodb-backups]: <https://docs.percona.com/percona-operator-for-mongodb/backups.html>

## S3 Bucket configuration

The default installation expects a `Seaweed` CRD resource in the `seaweedfs`
namespace with the name `seaweed` by default to deploy its bucket. The location
of the `Seaweed` resource can be changed by adding and configuring the following
values in the values file:

```yaml
bucketConfig:
  clusterRef:
    name: seaweed
    namespace: seaweedfs
```

The bucket by default is set to be accessible to the public without
authentication. This can be changed by using the following snippet in the values
file:

```yaml
bucketConfig:
  extraConfig:
    anonymousRead: false
```

## Other configuration

Other expected configuration for an Helm Chart such as number of replicas, pod
resources, affinities, node selectors, and others are also possible using normal
chart conventions. For more details on all the available configuration consult
the chart's `values.yaml` file or by running the following command:

```sh
$ helm show values ./dt4mob-platform/charts/dt4mob
```
