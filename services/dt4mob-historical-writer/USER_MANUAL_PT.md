# dt4mob-historical-writer — Manual do Utilizador

## Visão Geral

O **historical-writer** é um serviço que consome mensagens de um tópico **Kafka** (seguindo o protocolo Eclipse Ditto) e persiste os eventos numa **hipertabela TimescaleDB**. Faz parte da extensão de dados históricos da plataforma DT4Mob.

## Requisitos

- **Python** >= 3.12
- **uv** (gestor de pacotes: https://docs.astral.sh/uv/)
- **Kafka** (com certificados SSL)
- **TimescaleDB** (PostgreSQL com extensão Timescale)

## Configuração

Toda a configuração é feita através de variáveis de ambiente ou de um ficheiro `.env` na raiz do serviço.

### Kafka

| Variável | Obrigatório | Descrição |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | Sim | Endereço do broker Kafka (ex: `kafka-cluster-kafka-bootstrap:9092`) |
| `KAFKA_SECURITY_PROTOCOL` | Sim | Protocolo de segurança (ex: `SSL`) |
| `KAFKA_SSL_CA_LOCATION` | Sim | Caminho para o ficheiro do certificado CA |
| `KAFKA_SSL_CERTIFICATE_LOCATION` | Sim | Caminho para o certificado de cliente |
| `KAFKA_SSL_KEY_LOCATION` | Sim | Caminho para a chave privada do cliente |
| `KAFKA_CONSUMER_GROUP` | Sim | ID do grupo de consumidores |
| `KAFKA_TOPIC` | Sim | Tópico a consumir |
| `KAFKA_AUTO_OFFSET_RESET` | Sim | Estratégia de reset de offset (`latest`, `earliest`) |

### TimescaleDB

| Variável | Obrigatório | Padrão | Descrição |
|---|---|---|---|
| `TIMESCALE_CONNECTION` | Sim | — | String de conexão (ex: `postgresql://user:pass@host:5432/db`) |
| `TIMESCALE_DATABASE_TIMEZONE` | Não | `Europe/Lisbon` | Fuso horário para colunas de timestamp |

### Gerais

| Variável | Obrigatório | Padrão | Descrição |
|---|---|---|---|
| `LOG_LEVEL` | Não | `INFO` | Nível de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

### Exemplo de `.env`

```
KAFKA_BOOTSTRAP_SERVERS=kafka-cluster-kafka-bootstrap:9092
KAFKA_SECURITY_PROTOCOL=SSL
KAFKA_SSL_CA_LOCATION=/certs/ca.crt
KAFKA_SSL_CERTIFICATE_LOCATION=/certs/user.crt
KAFKA_SSL_KEY_LOCATION=/certs/user.key
KAFKA_CONSUMER_GROUP=historical-writer-group
KAFKA_TOPIC=exports-test-tenant
KAFKA_AUTO_OFFSET_RESET=latest
TIMESCALE_CONNECTION=postgresql://user:password@timescale-host:5432/historical
TIMESCALE_DATABASE_TIMEZONE=Europe/Lisbon
LOG_LEVEL=INFO
```

## Execução Local

```bash
# Instalar dependências
uv sync --locked

# Executar
uv run main.py
```

## Execução com Docker

### Desenvolvimento

```bash
docker build -f dockerfile -t historical-writer:dev .
docker run --env-file .env historical-writer:dev
```

### Produção (sem dependências de desenvolvimento)

```bash
docker build -f dockerfile.prod -t historical-writer:prod .
docker run --env-file .env historical-writer:prod
```

O contentor espera que os certificados SSL estejam montados em `/certs/` (ou nos caminhos definidos nas variáveis de ambiente).

## Execução no Kubernetes (Helm)

A implantação no Kubernetes é gerida através do Helm chart `dt4mob-historical`, localizado na infraestrutura do projeto em `charts/dt4mob-historical/`. Este chart não faz parte do código fonte deste serviço — reside no repositório de infraestrutura pai.

O Helm chart provê:

- **Writer Deployment** — executa este serviço
- **Writer ConfigMap** — mapeia valores do chart para variáveis de ambiente
- **TimescaleDB Cluster** — cluster CloudNativePG com extensão TimescaleDB
- **KafkaTopic** — tópico Strimzi (opcional)
- **API Deployment + Service** — API de leitura complementar (código separado)

### Valores Configuráveis (`values.yaml`)

```yaml
# Imagem do writer
images:
  writer:
    repository: atnog-harbor.av.it.pt/dt4mob/data-gateway
    tag: latest

# Comportamento do writer
writer:
  replicas: 1
  config:
    logLevel: INFO
    timescaleDatabaseTimezone: "Europe/Lisbon"
  kafka:
    bootstrapServers: "kafka-cluster-kafka-bootstrap:9092"
    securityProtocol: SSL
    consumerGroup: "consumer-group"
    autoOffsetReset: latest
    # userSecretName/trustSecretName referenciam secrets Kubernetes
    # com os certificados SSL do Kafka

# Armazenamento TimescaleDB
timescale:
  instances: 1
  storage:
    storageClass: "local-path"
    size: 10Gi
```

### Instalação

```bash
helm upgrade --install dt4mob-historical charts/dt4mob-historical -f my-values.yaml
```

Antes de instalar, certifique-se de que os secrets Kubernetes com os certificados SSL do Kafka existem no namespace. Consulte o `values.yaml` do chart para a referência completa de parâmetros.

## Formato de Entrada Esperado

O serviço consome mensagens no formato do **protocolo Eclipse Ditto**, publicadas no tópico Kafka configurado. Exemplo de mensagem:

```json
{
  "topic": "org.dt4mob:vehicle-123/things/live/state/modified",
  "headers": {
    "dt4mob-historic-timestamp-override": "2025-01-15T10:30:00Z"
  },
  "path": "/features/speed/properties/value",
  "value": 42.5,
  "revision": 3,
  "timestamp": "2025-01-15T10:30:05Z"
}
```

- `topic` deve seguir o padrão `{namespace}:{name}/things/{channel}//{action}`
- `dt4mob-historic-timestamp-override` (cabeçalho opcional) substitui o timestamp do evento pela hora real da medição

## Esquema da Base de Dados

O serviço cria a tabela `dittoevent` com as seguintes colunas:

| Coluna | Tipo | Notas |
|---|---|---|
| `time` | `timestamptz` | Chave primária (1ª parte) |
| `index` | `integer` | Chave primária (2ª parte, auto-incremento) |
| `thing_id` | `text` | Indexado |
| `action` | `enum` | `modified`, `created`, `deleted`, `merged` |
| `path` | `text` | Caminho JSON do Ditto |
| `revision` | `integer` | Anulável |
| `value` | `jsonb` | Anulável |

Configuração da hipertabela TimescaleDB:

- **Intervalo de chunk:** 1 dia
- **Compressão:** ativada
- **Segmento de compressão:** `thing_id`
- **Ordenação de compressão:** `time DESC`
- **Intervalo de compressão:** dados com mais de 7 dias são comprimidos

## Monitorização e Resolução de Problemas

### Logs

Defina `LOG_LEVEL=DEBUG` para obter saída detalhada mostrando cada mensagem consumida e escrita na base de dados.

### Problemas Comuns

| Problema | Causa Provável |
|---|---|
| O consumidor não liga | Broker Kafka inacessível ou certificados SSL mal configurados |
| Nenhuma mensagem consumida | Nome do tópico errado ou offset do grupo de consumidores |
| Falha ao escrever na BD | String de conexão TimescaleDB incorreta ou base de dados inacessível |
| Tabela não criada | Extensão `timescaledb` ausente na instância PostgreSQL |

### Saúde

O serviço executa um loop infinito de polling. Se terminar, verifique os logs para erros de Kafka ou base de dados. No Kubernetes, o Deployment reiniciará o pod automaticamente.
