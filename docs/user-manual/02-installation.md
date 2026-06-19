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

The `values.yaml` file is required and should at a minimum have the following structure:

```yaml
global:
  host: dt4mob.av.it.pt

ditto:
  ingress:
    host: dt4mob.av.it.pt
```

The value of `host` in both instances is the domain name where the platform
will be exposed. This can be a public domain, an internal domain, or even a
placeholder domain, but the values must be set.

## Exposing the platform
