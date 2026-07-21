# Introduction

This manual provides instructions on how to install, operate, and maintain
the Digital Twins for Mobility platform, henceforth referred to as the dt4mob
platform or simply the platform.

## High-level overview

The dt4mob platform is built on a cloud native architecture to be able
to efficiently and easily scale to meet demand, this translates into
a set of independent micro-services that are scheduled and scaled in a
Kubernetes[^kubernetes] cluster.

Additionally, the platform itself is made to be modular through a separation
of a core subset of services that are required for basic operation, and a
set of addons containing their own services to provide an enhanced set of
functionalities and respond to existing and emerging use cases.

In practice, and in order to simplify operation, this is achieved through a set
of hierarchical Helm[^helm] charts.

``` mermaid
%%| fig-cap: Grafo de dependências do charts Helm.
graph TD
    A[dt4mob] --> B[hono]
    A --> C[ditto]
    A --> D[reloader]
    A --> E[psmdb-db]
    
    A --> F[dt4mob-controller]
    A --> G[dt4mob-historical/]
    A --> H[dt4mob-garbage-collector]
    A --> I[dt4mob-ingress]
    A --> J[dt4mob-level-ams-loader]
    A --> K[dt4mob-viz]
    
    K --> L[grafana]
    
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#fbb,stroke:#333,stroke-width:2px
    style C fill:#fbb,stroke:#333,stroke-width:2px
    style D fill:#fbb,stroke:#333,stroke-width:2px
    style E fill:#fbb,stroke:#333,stroke-width:2px
    style F fill:#bfb,stroke:#333,stroke-width:2px
    style G fill:#bbf,stroke:#333,stroke-width:2px
    style H fill:#bbf,stroke:#333,stroke-width:2px
    style I fill:#bbf,stroke:#333,stroke-width:2px
    style J fill:#bbf,stroke:#333,stroke-width:2px
    style K fill:#bbf,stroke:#333,stroke-width:2px
    style L fill:#fbb,stroke:#333,stroke-width:2px
```

The top-level `dt4mob` chart includes the full platform core and all existing
addons ready for deployment. However, if not all components are required or more
control over the deployment process is needed, the charts can also be installed
individually. More details on all the available installation options are given
in @sec:installation.

[^kubernetes]: <https://kubernetes.io>
[^helm]: <https://helm.sh>

## Digital twins implementation

Digital twins are virtual representations of physical objects, structures,
and systems, these can be used for a large set of purposes like monitoring and
simulation. These use cases depend on accurate and up to date information from
the physical twin.

The dt4mob platform builds upon the Eclipse Ditto™ [^ditto] and Eclipse
Hono™ [^hono] projects for its core digital twin offering, Ditto defines the
backend infrastructure for storing and querying the digital twins, or *Things*
as they refer to them, and Hono functions as the connectivity layer between the
devices on the edge and Ditto.

``` mermaid
%%| fig-cap: Componentes da arquitetura de gemêo digital.
graph LR
    %% Edge/IO devices
    edge_devices[Edge Devices] --> hono[Hono]
    
    %% Connectivity layer
    hono <--> kafka@{ shape: das, label: "Kafka" }
    
    %% Digital twin backend
    kafka <--> ditto[Ditto]
    
    %% Storage
    ditto --> mongodb@{ shape: cyl, label: "MongoDB" }
    
    %% Styling
    style edge_devices fill:#f9f,stroke:#333,stroke-width:2px
    style hono fill:#fbb,stroke:#333,stroke-width:2px
    style kafka fill:#bbf,stroke:#333,stroke-width:2px
    style ditto fill:#bfb,stroke:#333,stroke-width:2px
    style mongodb fill:#bbf,stroke:#333,stroke-width:2px
```

Connectivity with the devices is done through a set of adapters provided by Hono
and placed at the edge, these provide interfaces based on the HTTP, AMQP, and
MQTT protocols. Communication between Hono and Ditto is done through a Kafka
message queue.

All of these are secured through the use of TLS and certificate based mutual
authentication (mTLS), the certificates are provisioned through a Certificate
Authority (CA) that lives inside the cluster with their lifecycle and renewal
automatically handled.

In order to concile configuration and certificates during normal operation, a
service called the `dt4mob-controller` listens for cluster events and, through
the administration APIs offered by Hono and Ditto, updates the components
configuration to match the new cluster state.
 
[^ditto]: <https://eclipse.dev/ditto/>
[^hono]: <https://eclipse.dev/hono/>
