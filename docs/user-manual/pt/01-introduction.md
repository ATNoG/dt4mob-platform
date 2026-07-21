# Introdução

Este manual fornece instruções sobre como instalar, operar e manter
a plataforma Digital Twins for Mobility, doravante designada por plataforma
dt4mob ou simplesmente a plataforma.

## Visão geral

A plataforma dt4mob é construída sobre uma arquitetura cloud native para poder
escalar de forma fácil e eficiente para satisfazer a demanda, o que
se traduz num conjunto de micro-serviços independentes que são executados e
escalados num cluster Kubernetes[^kubernetes].

Adicionalmente, a própria plataforma é concebida para ser modular através da
separação de um subconjunto principal de serviços necessários para o
funcionamento básico e de um conjunto de addons que contêm os seus próprios
serviços para fornecer um conjunto alargado de funcionalidades e responder a
casos de usos existentes e emergentes.

Na prática, e para simplificar a operação, isto é conseguido através de um
conjunto de charts Helm[^helm] que formam uma hierarquia.

``` mermaid
%%| fig-cap: Helm dependency graph.
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

O chart raíz `dt4mob` inclui o núcleo completo da plataforma e todos os
addons existentes preparados para fácil instalação. No entanto, se nem todos
os componentes forem necessários ou se for necessário mais controlo sobre o
processo de instalação, os charts também podem ser instalados individualmente.
Mais detalhes sobre todas as opções de instalação disponíveis são fornecidos
na @sec:installation.

[^kubernetes]: <https://kubernetes.io>
[^helm]: <https://helm.sh>

## Implementação de gémeos digitais

Os gémeos digitais são representações virtuais de objetos, estruturas e sistemas
físicos, podendo ser utilizados para um vasto conjunto de finalidades, como
monitorização e simulação. Estes casos de uso dependem de informação precisa e
atualizada do gémeo físico.

A plataforma dt4mob baseia-se nos projetos Eclipse Ditto™ [^ditto] e Eclipse
Hono™ [^hono] para a sua oferta principal de gémeos digitais. O Ditto define
a infraestrutura de backend para armazenar e consultar os gémeos digitais,
ou *Things* na nomeclatura do projeto, e o Hono funciona como a camada de
conectividade entre os dispositivos na periferia e o Ditto.

``` mermaid
%%| fig-cap: Digital twins components architecture.
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

A conectividade com os dispositivos é feita através de um conjunto de
adaptadores fornecidos pelo Hono e colocados na periferia, estes fornecem
interfaces baseadas num conjunto diverso de protocolos como HTTP, AMQP e MQTT.
A comunicação entre o Hono e o Ditto é feita através de uma fila de mensagens
Kafka.

Todos estes são protegidos através da utilização de TLS e autenticação mútua
baseada em certificados (mTLS). Os certificados são provisionados através de
uma Autoridade Certificadora (CA) que reside dentro do cluster, com o seu
ciclo de vida e renovação geridos automaticamente.

Para reconciliar a configuração e os certificados durante a operação normal, um
serviço chamado `dt4mob-controller` monitoriza eventos do cluster e, através das
APIs de administração oferecidas pelo Hono e pelo Ditto, atualiza a configuração
dos componentes para corresponder ao novo estado do cluster.
 
[^ditto]: <https://eclipse.dev/ditto/>
[^hono]: <https://eclipse.dev/hono/>
