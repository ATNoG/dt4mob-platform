# dt4mob-historical-writer — Manual do Programador

## Estrutura do Projeto

```
dt4mob-historical-writer/
├── main.py                                          # Ponto de entrada
├── pyproject.toml                                   # Dependências (confluent-kafka, sqlmodel, etc.)
├── dockerfile                                       # Imagem Docker de desenvolvimento (Alpine + uv)
├── dockerfile.prod                                  # Imagem Docker de produção (sem dev deps)
├── .python-version                                  # Python 3.12
├── .env                                             # Configuração local (gitignored)
├── uv.lock                                          # Lockfile
├── USER_MANUAL_EN.md
├── USER_MANUAL_PT.md
├── DEVELOPER_MANUAL_EN.md
├── DEVELOPER_MANUAL_PT.md
└── src/
    ├── settings/
    │   ├── __init__.py          # Configurações globais (pydantic-settings), carregadas do .env
    │   ├── kafka.py             # KafkaSettings — broker, SSL, grupo de consumidores, tópico
    │   └── timescale.py         # TimeScale — string de conexão, fuso horário
    ├── models/
    │   ├── __init__.py
    │   └── ditto_events.py      # DittoEvent SQLModel, enum Action, config hipertabela Timescale
    ├── database_engines/
    │   ├── __init__.py          # Singleton engine + criação de tabelas ao importar
    │   └── TimeScaleEngineManager.py  # Engine SQLAlchemy, fábrica de sessões, create_db_tables
    └── services/
        ├── __init__.py
        ├── KafkaConsumer/
        │   ├── __init__.py      # Re-exporta KafkaConsumer
        │   └── kafka_consumer.py  # Loop de poll do Kafka, descodificação JSON, dispatch
        ├── MessageProcessor/
        │   ├── __init__.py
        │   └── message_processor.py  # Interpreta mensagens Ditto para objetos DittoEvent
        └── DittoEventsManager/
            ├── __init__.py      # Cria singleton DittoEventsManager com o engine
            └── ditto_events_manager.py  # write(event) — session.add + commit
```

## Sequência de Inicialização

1. **`main.py:13`** — `if __name__ == "__main__": main()` invoca `main()`
2. **`src/database_engines/__init__.py:4-5`** — ao importar, cria o singleton `TimescaleDBEgineManager()` e chama `create_db_tables()`, que executa `SQLModel.metadata.create_all(self.engine)`, emitindo `CREATE TABLE` e o evento `after_create`
3. **`src/services/DittoEventsManager/__init__.py:2-4`** — ao importar, instancia o singleton `DittoEventsManager(db_engine=timescale_engine)`
4. **`main.py:6`** — `KafkaConsumer()` subscreve o tópico Kafka configurado
5. **`main.py:9`** — `consumer.consume(ditto_event_manager)` entra no loop infinito de polling

## Fluxo de Mensagens (Fim a Fim)

```
Tópico Kafka
    │
    ▼
KafkaConsumer.consume()                         src/services/KafkaConsumer/kafka_consumer.py:15
    ├── consumer.poll(1.0)                       Poll ao Kafka com timeout de 1s
    ├── msg.value().decode('utf-8')              Descodifica bytes para string
    ├── json.loads(message_text)                 Interpreta JSON
    │
    ▼
parse_message(message_data)                      src/services/MessageProcessor/message_processor.py:5
    ├── Divide msg["topic"] por "/"              Extrai namespace, name, channel, action
    ├── Lê headers["dt4mob-historic-timestamp-override"]  Substituição opcional de timestamp
    ├── Usa msg["timestamp"] como fallback       Se override ausente ou inválido
    ├── Constrói DittoEvent(time, thing_id, action, path, revision, value)
    │
    ▼
DittoEventsManager.write(event)                  src/services/DittoEventsManager/ditto_events_manager.py:9
    ├── db_engine.get_session() as session        Abre uma sessão SQLModel
    ├── session.add(event)                       Enfileira o INSERT
    ├── session.commit()                         Faz commit (automático ao sair do context manager)
    └── Em caso de exceção: session.rollback()
    │
    ▼
TimescaleDB (hipertabela dittoevent)
    ├── CREATE TABLE no primeiro import
    ├── create_hypertable() no after_create
    └── Política de compressão aplicada
```

## Detalhamento dos Módulos

### Settings (`src/settings/`)

Usa **pydantic-settings** com `SettingsConfigDict(env_file=".env")`. O singleton `settings` global é construído ao importar (`src/settings/__init__.py:28`).

**`KafkaSettings.as_dict()`** (`src/settings/kafka.py:20`) converte os campos Pydantic para o formato de chaves pontuadas exigido pelo `confluent_kafka.Consumer`:
- `bootstrap.servers`, `security.protocol`, `ssl.ca.location`, `ssl.certificate.location`, `ssl.key.location`, `group.id`, `auto.offset.reset`
- `enable.auto.commit` está definido como `False` — os commits são manuais após cada mensagem processada com sucesso.

**`TimeScale.get_connection()`** (`src/settings/timescale.py:14`) substitui `postgresql://` por `postgresql+psycopg://` para que o SQLAlchemy use o driver psycopg.

### KafkaConsumer (`src/services/KafkaConsumer/kafka_consumer.py`)

- **`__init__`**: Cria um `confluent_kafka.Consumer` com `KafkaSettings.as_dict()` e subscreve o tópico configurado.
- **`consume(manager)`**: Loop infinito que chama `consumer.poll(1.0)`. Em cada mensagem:
  1. Descodifica e interpreta o JSON.
  2. Chama `parse_message()` para construir um `DittoEvent`.
  3. Chama `manager.write(event)` para persistir.
  4. Chama `self.consumer.commit(asynchronous=False)` — **commit síncrono manual** garante entrega pelo menos uma vez. Se o processo falhar entre `write` e `commit`, a mensagem será reentregue, podendo causar duplicados.

### MessageProcessor (`src/services/MessageProcessor/message_processor.py`)

**`parse_message(msg)`** extrai dados estruturados de uma mensagem Ditto:

1. **Interpretação do tópico**: `msg["topic"]` é dividido por `"/"`. Formato esperado: `{namespace}:{name}/things/{channel}//{action}`. O `thing_id` é remontado como `namespace:name`, e a `action` é o 6º elemento (índice 5).
2. **Substituição de timestamp**: Se o cabeçalho `dt4mob-historic-timestamp-override` estiver presente e for uma string ISO-8601 válida, substitui o `timestamp` original da mensagem. Caso contrário, o `msg["timestamp"]` original é usado.
3. **Retorna** um `DittoEvent` com `time`, `thing_id`, `action`, `path`, `revision`, `value`.

### Modelo DittoEvent (`src/models/ditto_events.py`)

**Enum `Action`**: `modified`, `created`, `deleted`, `merged`.

**`DittoEvent`** SQLModel (tabela `dittoevent`):
- **Chave primária composta**: `time` (datetime, 1ª parte) + `index` (auto-incremento Identity, 2ª parte)
- **`thing_id`**: indexado para performance de consultas
- **`action`**: armazenado como enum nativo PostgreSQL (`action_enum`)
- **`value`**: armazenado como `JSONB` para dados aninhados flexíveis

**Configuração da hipertabela Timescale** (`__timescale_config__`):
- `time_column: "time"` — coluna de particionamento
- `chunk_time_interval: "1 days"` — cada chunk cobre 1 dia
- `compress: True` — ativa compressão nativa
- `compress_segmentby: "thing_id"` — linhas comprimidas segmentadas por thing
- `compress_orderby: "time DESC"` — ordenação dentro dos segmentos comprimidos
- `compress_interval: "7 days"` — política de compressão aplicada a dados com mais de 7 dias

O ouvinte do evento `after_create` (`src/models/ditto_events.py:42`) executa automaticamente estas instruções SQL quando a tabela é criada:

```sql
SELECT create_hypertable('dittoevent', 'time', chunk_time_interval => INTERVAL '1 days', if_not_exists => TRUE);

ALTER TABLE dittoevent SET (timescaledb.compress, timescaledb.compress_segmentby = 'thing_id', timescaledb.compress_orderby = 'time DESC');

SELECT add_compression_policy('dittoevent', INTERVAL '7 days', if_not_exists => TRUE);
```

### TimeScaleDBEgineManager (`src/database_engines/TimeScaleEngineManager.py`)

- **`__init__`**: Cria uma `Engine` SQLAlchemy usando a string de conexão das definições. `echo=True` quando `LOG_LEVEL=DEBUG`.
- **`create_db_tables()`**: Chama `SQLModel.metadata.create_all(self.engine)` que emite `CREATE TABLE` e aciona o evento `after_create`.
- **`get_session()`**: Um `@contextmanager` que produz uma `Session`, faz auto-commit em caso de sucesso e auto-rollback em caso de exceção.

### DittoEventsManager (`src/services/DittoEventsManager/ditto_events_manager.py`)

Wrapper leve em torno do motor de base de dados. O método `write(event)` abre uma sessão, adiciona o evento e faz commit. A sessão é obtida através do context manager de `TimeScaleDBEgineManager.get_session()`.

## Dependências

| Pacote | Versão | Propósito |
|---|---|---|
| `confluent-kafka` | >= 2.13.0 | Consumidor Kafka (C-based, alta performance) |
| `psycopg[binary]` | >= 3.3.2 | Adaptador PostgreSQL (compatível com async) |
| `pydantic` | >= 2.12.5 | Validação de dados |
| `pydantic-settings` | >= 2.12.0 | Gestão de definições a partir de variáveis de ambiente |
| `sqlalchemy` | >= 2.0.45 | Núcleo ORM |
| `sqlmodel` | >= 0.0.31 | Integração Pydantic + SQLAlchemy, definição de tabelas |

## Docker Build

Dois Dockerfiles usando **Alpine Edge** + **uv**:

- **`dockerfile`** (dev): executa `uv sync --locked` (instala todas as dependências, incluindo dev).
- **`dockerfile.prod`** (prod): define `ENV UV_NO_DEV=1` antes de `uv sync --locked` para excluir dependências de desenvolvimento.

Ambos instalam `build-base`, `python3-dev`, `librdkafka-dev` (para a extensão C do confluent-kafka). O CMD é `uv run main.py`.

O contentor espera que os certificados SSL estejam montados em `/certs/` (ou caminhos personalizados).

## Implantação no Kubernetes

Os recursos Kubernetes estão definidos no Helm chart **`dt4mob-historical`** em `charts/dt4mob-historical/` na infraestrutura do projeto.

### Estrutura do Chart

```
charts/dt4mob-historical/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl              # Helpers de nomenclatura de templates
    ├── writer-deployment.yaml     # Deployment para este serviço
    ├── writer-config.yaml         # ConfigMap (variáveis de ambiente para o writer)
    ├── kafka-topic.yaml           # Strimzi KafkaTopic (opcional)
    ├── timescale-cluster.yaml     # Cluster CloudNativePG com TimescaleDB
    ├── timescale-image-catalog.yaml  # ImageCatalog CNPG
    ├── api-deployment.yaml        # API de leitura complementar (código separado)
    └── api-service.yaml           # Service da API complementar
```

### Writer Deployment (`writer-deployment.yaml`)

Aspetos principais:

- **Imagem**: de `values.images.writer` (padrão: `atnog-harbor.av.it.pt/dt4mob/data-gateway`).
- **Variáveis de ambiente** de duas fontes:
  - **ConfigMap** (`writer-config.yaml`): `LOG_LEVEL`, `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SSL_CA_LOCATION`, `KAFKA_SSL_CERTIFICATE_LOCATION`, `KAFKA_SSL_KEY_LOCATION`, `KAFKA_CONSUMER_GROUP`, `KAFKA_TOPIC`, `KAFKA_AUTO_OFFSET_RESET`, `TIMESCALE_DATABASE_TIMEZONE`.
  - **Referência a secret**: `TIMESCALE_CONNECTION` é lida do secret do cluster CNPG (`{release}-cluster-app`, chave `uri`).
- **Montagens de volume**: Dois volumes montam os secrets SSL do Kafka:
  - `/certs` (certificado + chave do utilizador) — de `writer.kafka.userSecretName`
  - `/cluster-ca` (certificado CA) — de `writer.kafka.trustSecretName`

### Writer ConfigMap (`writer-config.yaml`)

Mapeia os campos de `values.yaml` para nomes de variáveis de ambiente, construindo os caminhos dos certificados SSL a partir de pontos de montagem conhecidos:

```yaml
KAFKA_SSL_CA_LOCATION: "/cluster-ca/ca.crt"
KAFKA_SSL_CERTIFICATE_LOCATION: "/certs/user.crt"
KAFKA_SSL_KEY_LOCATION: "/certs/user.key"
KAFKA_TOPIC: {{ .Values.kafkaTopic.name }}
```

### TimescaleDB Cluster (`timescale-cluster.yaml`)

Usa o operador **CloudNativePG** (`postgresql.cnpg.io/v1`) para provisionar um cluster PostgreSQL com TimescaleDB:

- **Imagem**: `timescale/timescaledb-ha:pg18.0-ts2.23.0` (via ImageCatalog)
- **Biblioteca pré-carregada**: `timescaledb` adicionada a `shared_preload_libraries`
- **SQL pós-inicialização**: `CREATE EXTENSION IF NOT EXISTS timescaledb` — garante que a extensão existe antes do evento `after_create` do writer tentar chamar `create_hypertable()`
- **Armazenamento**: `storageClass` e `size` configuráveis (padrão: `local-path`, `10Gi`)

### KafkaTopic (`kafka-topic.yaml`)

Cria opcionalmente um recurso personalizado `KafkaTopic` (Strimzi) definido por `kafkaTopic.name`. Controlado pelo booleano `kafkaTopic.create`.

### Como Tudo se Liga

1. O Helm cria o cluster TimescaleDB (CNPG) e o KafkaTopic.
2. O operador CNPG gera um secret com o URI da base de dados.
3. O Deployment do writer lê:
   - O URI do TimescaleDB a partir do secret CNPG
   - As restantes configurações a partir do ConfigMap
4. O writer inicia, cria a tabela `dittoevent` + hipertabela, subscreve o tópico Kafka e começa a consumir.
