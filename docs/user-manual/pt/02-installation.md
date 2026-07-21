# Instalação {#sec:installation}

## Pré-requisitos

É necessário um cluster Kubernetes a executar uma das três versões menores mais
recentes. Além disso, devido a limitações do empacotamento em charts Helm, os
seguintes componentes precisam de ser instalados previamente no cluster:

- [Ingress NGINX Controller](https://github.com/kubernetes/ingress-nginx)
- [cert-manager](https://cert-manager.io/)
- [Strimzi Kafka Operator](https://strimzi.io/)
- [Percona Operator for MongoDB](https://docs.percona.com/percona-operator-for-mongodb/)
- [CloudNativePG](https://cloudnative-pg.io/)
- [SeaweedFS Operator](https://github.com/seaweedfs/seaweedfs-operator/)

O tamanho mínimo do cluster necessário para executar todos os componentes
essenciais é de 8 vCPUs, 16 GiB de RAM e 200 GiB de armazenamento. Podem ser
necessários mais recursos para escalar o cluster de modo a satisfazer a procura
e para instalar os addons. Não existe restrição quanto ao número mínimo de nós
no cluster, exceto em cenários de alta disponibilidade, onde são necessários
pelo menos 3 nós.

## Instalação do release

A plataforma dt4mob pode ser implantada de uma só vez utilizando o comando
padrão `helm install`:

```sh
$ helm install dt4mob --values values.yaml ./dt4mob-platform/charts/dt4mob
```

Infelizmente, devido a limitações técnicas, a release deve ser nomeada
`dt4mob` (É tecnicamente possível usar um nome diferente, mas requer uma
grande quantidade de reconfiguração e não é suportado).

O ficheiro `values.yaml` é obrigatório e deve, no mínimo, ter a seguinte
estrutura:

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

O valor de `host` em ambas as instâncias é o nome de domínio onde a plataforma
será exposta. Pode ser um domínio público, um domínio interno ou até mesmo um
domínio temporário, mas os valores tem de ser definidos. O valor de `issuer`
deve ser definido manualmente, devido a limitações do empacotamento Helm, para o
mesmo valor de `global.host` com `/auth/realms/dt4mob` acrescentado no final.

Poderá também ser relevante alterar o valor de `global.tenant` do seu valor
predefinido `test-tenant` para um nome mais apropriado. Isto alterará o nome do
tenant criado no Hono e também o nome das conexões criadas no Ditto. Este valor
pode ser alterado posteriormente, mas requer trabalho manual para migrar todas
as utilizações anteriores do nome do tenant antigo para o novo.

## Abertura da plataforma ao exterior

A plataforma tem duas partes que podem ser expostas separadamente e através de
mecanismos diferentes:

- Adaptadores do Hono 
- APIs da plataforma

As seguintes secções abordam cada parte individualmente.

### Adaptadores Hono

A instalação padrão da plataforma expõe os adaptadores Hono através da
utilização de serviços Kubernetes `NodePort`; as portas são alocadas
dinamicamente pelo cluster para garantir que não entram em conflito com
alocações existentes. O seguinte comando pode ser utilizado para obter as
portas alocadas.

```sh
$ kubectl get svc dt4mob-hono-adapter-http dt4mob-hono-adapter-mqtt dt4mob-hono-adapter-amqp
```

Contactar qualquer um dos nós do Cluster Kubernetes nestas portas encaminhará o
tráfego para o respetivo adaptador Hono. Se, em alternativa, for desejável
expor estes serviços utilizando um balanceador de carga (cloud ou on-prem), a
seguinte alteração ao ficheiro de valores deve ser aplicada.

```yaml
hono:
  useDynamicNodePorts: false
  useLoadBalancer: true
```

A comunicação com os adaptadores deve é feita através de TLS para todos os
protocolos, isto é necessário não só para a proteção dos dados enviados e
recebidos, mas também para a autenticação dos dispositivos que é feita através
da utilização de certificados X.509. Todos os certificados utilizados para
comunicação com o Hono são assinados por um certificado raiz autoassinado
cujo ciclo de vida é gerido pelo cluster e, como tal, deve ser adicionado ao
trust store dos dispositivos de perímetro. O certificado raiz pode ser obtido
utilizando o seguinte comando:

```sh
$ kubectl get secrets dt4mob-tenant-ca-secret -o jsonpath="{.data['ca\.crt']}" | base64 -d
```

Os certificados dos adaptadores incluirão sempre o nome de domínio configurado
na opção `global.host` nos valores da extensão Subject Alternative Name
(SAN). No entanto e em alguns casos, o DNS pode não estar disponível, não ser
desejado, ou o domínio pode não resolver externamente, e como tal pode ser
necessário conexão direta aos adaptadores através do endereço IP dos nós ou dos
balanceadores de carga. Para tais cenários, os valores SAN podem ser estendidos
com endereços IP arbitrários através da seguinte modificação ao ficheiro `values.yaml`.

```yaml
dt4mob-ingress:
  addresses:
  - 193.136.93.66
```

Em certas configurações de rede e especialmente de firewall, o acesso a serviços
através de portas não padrão pode ser impossível. Para combater este problema,
é possível implementar ingressos que encaminham o tráfego com base no Server
Name Indication (SNI) do TLS Client Hello. Na prática, isto permite que os
adaptadores sejam expostos através da porta HTTPS padrão 443 em diferentes
domínios que são então encaminhados para os seus respetivos adaptadores sem
necessidade de qualquer encapsulamento. Para ativar isto, o seguinte excerto
deve ser adicionado ao ficheiro de valores. Cada adaptador pode ter o seu
ingresso ativado individualmente. Estes tem necessarimate de ter nomes de
domínio diferentes para o host, que também tem ser diferentes do configurado
para a plataforma em `global.host`.

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

Não são necessárias mais alterações à configuração dos certificados dos
adaptadores, pois estes irão automaticamente recolher os valores configurados
para os ingressos nos seus valores SAN.

### APIs da plataforma

As APIs da plataforma são expostas através do nome de domínio configurado na
opção `global.host`. No entanto, isto, por predefinição,  é feito através de um
ingresso utilizando um certificado autoassinado. O cert-manager é utilizado para
a emissão e ciclo de vida do certificado. Assim, para utilizar um certificado
emitido por uma CA, o emissor tem de ser configurado. Isto pode ser feito de
duas formas, utilizando um emissor presente no cluster:

```yaml
ingressTLS:
  issuer:
    existingIssuer:
      name: "my-cluster-issuer"
      kind: ClusterIssuer
      group: cert-manager.io
```

Ou modificando o emissor existente para não utilizar certificados autoassinados
e, em vez disso, utilizar, por exemplo, um Automatic Certificate Management
Environment (ACME), como o Let's Encrypt:

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

Para mais detalhes, consulte a documentação do cert-manager para emissores
[^cert-manager-issuer]. 

[^cert-manager-issuer]: <https://cert-manager.io/docs/configuration/>

## Configuração de backups

O estado da plataforma é mantido principalmente numa base de dados MongoDB.
Várias cópias de segurança devem ser feitas periodicamente para garantir
tolerância a falhas e continuidade de negócio. As cópias de segurança são
geridas através do Percona Operator for MongoDB e requerem configuração
adicional nos valores do chart para configurar as cópias de segurança e a onde
estas vão ser armazenadas. O exemplo seguinte mostra a configuração para cópias
de segurança guardadas num servidor Network File System (NFS) com recuperação
Point-In-Time (PITR) e compressão zstd.

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

Esta configuração permite a criação de cópias de segurança a pedido. Para cópias
de segurança periódicas, a opção `psmdb-db.backup.tasks` pode ser utilizada
para definirum agendamento periódico das cópias de segurança e até múltiplos
agendamentos para diferentes tipos de cópia de segurança. O exemplo seguinte
mostra uma configuração para cópias de segurança incrementais diárias com
cópias de base completas no início de cada semana e com períodos de retenção
configurados.

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

Para mais detalhes, consulte a documentação do Percona Operator for MongoDB
sobre cópias de segurança [^mongodb-backups].

[^mongodb-backups]: <https://docs.percona.com/percona-operator-for-mongodb/backups.html>

## Configuração do bucket S3

A instalação padrão, por predefinição, espera um recurso CRD `Seaweed`
no namespace `seaweedfs` com o nome `seaweed` para criar o seu bucket. A
localização do recurso `Seaweed` pode ser alterada adicionando e configurando os
seguintes valores no ficheiro `values.yaml`:

```yaml
bucketConfig:
  clusterRef:
    name: seaweed
    namespace: seaweedfs
```

O bucket, por predefinição, está configurado para ser acessível ao público sem
autenticação. Isto pode ser alterado utilizando o seguinte excerto no ficheiro
de valores:

```yaml
bucketConfig:
  extraConfig:
    anonymousRead: false
```

## Outras configurações

Outras configurações tipicamente esperadas de um Helm Chart, como o número de
réplicas, recursos do pod, afinidades, seletores de nós, entre outros, também
são possíveis utilizando as convenções normais do Helm. Para mais detalhes sobre
todas as configurações disponíveis, consulte o ficheiro `values.yaml` do chart
ou obtenha-as executando o seguinte comando:

```sh
$ helm show values ./dt4mob-platform/charts/dt4mob
```
