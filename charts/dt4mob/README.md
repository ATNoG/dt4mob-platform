## DT4MOB Helm Chart

Helm chart for deploying the DT4MOB services

### Installation

This chart requires a cluster with the following components:

- [Ingress NGINX Controller](https://github.com/kubernetes/ingress-nginx)
- [cert-manager](https://cert-manager.io/)
- [Strimzi](https://strimzi.io/) Kafka Operator
- [Percona Operator for MongoDB](https://docs.percona.com/percona-operator-for-mongodb/)

These are not included in the chart and must be installed manually before the
chart is installed.

> [!CAUTION]
> Only the ingress nginx controller will work, any other ingress will not work even if the ingress class of the relevant resources is altered.

To install the chart use the following command:

```sh
$ helm install --create-namespace --namespace dt4mob dt4mob oci://atnog-harbor.av.it.pt/dt4mob/dt4mob
```

This will create the `dt4mob` namespace and install a release named `dt4mob`.

> [!IMPORTANT]
> The helm chart is configured to deployed with the `dt4mob` release name, to deploy it under a different release name all values which define secrets beginning with the string `dt4mob` must be renamed. This only applies to the release name and not the namespace, which can be freely changed.

### Ditto ingress

To configure the host under which the ditto UI and API can be accessed, set the
`ditto.ingress.host` when installing/upgrading either by using the `--set`
command line option or a values file.

### MongoDB

By default, a 3 replica mongodb cluster is configured with the `local-path`
storage class. To change the number of replicas set `psmdb-db.replsets.rs0.size`
to the desired number of replicas.

To change the storage class used for the PVCs set
`psmdb-db.replsets.rs0.volumeSpec.pvc.storageClassName` to the desired storage
class. To set the size of the PVCs change
`psmdb-db.replsets.rs0.volumeSpec.pvc.resources.requests.storage` to the desired
size.

For further configuration of the MongoDB cluster see the [documentation for the
MongoDB Operator](https://docs.percona.com/percona-operator-for-mongodb/).

#### Backups

To configure backups see the [Operator documentation on
backups](https://docs.percona.com/percona-operator-for-mongodb/backups.html).
