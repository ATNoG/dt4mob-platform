# Manual do Desenvolvedor — Ditto Events API

## 1. Visão Geral da Arquitetura

```
┌──────────────┐     ┌─────────────────────────────────┐     ┌────────────┐
│   Cliente    │────▶│  dt4mob-historical-api (FastAPI) │────▶│ TimescaleDB│
│  (REST)      │     │                                  │     │ (Hypertable)│
│              │◀────│  - Router → Service → SQLModel   │◀────│            │
└──────────────┘     │  - Auth: Keycloak OIDC           │     └────────────┘
                     └─────────────────────────────────┘
                                │
                     ┌──────────▼──────────┐
                     │     Keycloak        │
                     │  (Validação JWT)    │
                     └─────────────────────┘
```

A API é uma **camada REST de leitura/escrita** sobre TimescaleDB. Partilha o mesmo esquema de base de dados que o `dt4mob-historical-writer` (o serviço de ingestão Kafka), mas os dois são processos independentes.

---

## 2. Estrutura de Diretórios

```
dt4mob-historical-api/
├── app/
│   ├── __init__.py                     # Vazio
│   ├── main.py                         # Ponto de entrada da aplicação FastAPI
│   ├── dependencies.py                 # Vazio (reservado)
│   │
│   ├── database_engine/
│   │   ├── __init__.py                 # Singleton engine + get_session()
│   │   └── TimeScaleEngineManager.py   # Wrapper SQLAlchemy engine
│   │
│   ├── models/
│   │   ├── __init__.py                 # Vazio
│   │   ├── ditto_events.py            # Tabela SQLModel DittoEvent
│   │   ├── paths_response.py          # Modelo Pydantic PathResponseObject
│   │   └── util.py                    # Enum Action
│   │
│   ├── routers/
│   │   ├── __init__.py                 # Vazio
│   │   └── events.py                  # Todos os endpoints REST
│   │
│   ├── services/
│   │   ├── __init__.py                 # Vazio
│   │   └── events_service.py          # Lógica de negócio / construção de queries
│   │
│   ├── settings/
│   │   ├── __init__.py                 # Settings global (combina auth + timescale)
│   │   ├── auth.py                    # AuthSettings (Keycloak)
│   │   └── timescale.py               # TimeScaleSettings (conexão DB)
│   │
│   └── static/                        # Assets Swagger UI personalizados
│       ├── swagger-ui-bundle.js
│       ├── swagger-ui-standalone-preset.js
│       ├── swagger-ui.css
│       └── swagger-initializer.js
│
├── dockerfile                          # Imagem Docker de produção
├── pyproject.toml                      # Dependências Python
├── uv.lock                             # Ficheiro de lock
├── USER_MANUAL.en.md
├── USER_MANUAL.pt.md
├── DEVELOPER_MANUAL.en.md
└── DEVELOPER_MANUAL.pt.md
```

---

## 3. Fluxo de Dados

```
Pedido HTTP
    │
    ▼
┌─────────────────────┐
│  FastAPI            │
│  app/main.py        │
│  root_path="/historic"│
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Autenticação OIDC  │
│  (fastapi-oidc)     │
│  Validação token    │
│  JWT                │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Router             │
│  app/routers/events.py│
│  - Analisa params   │
│  - Injeta sessão    │
│  - Chama service    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  EventsService      │
│  app/services/      │
│  events_service.py  │
│  - Constrói SQL     │
│  - Executa queries  │
│  - Devolve res.     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  SQLModel /         │
│  SQLAlchemy         │
│  - Session          │
│  - Modelo DittoEvent│
│  - SQL raw para     │
│    TimescaleDB      │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  TimescaleDB        │
│  (Hypertable)       │
└─────────────────────┘
```

---

## 4. Detalhes dos Módulos

### 4.1 `app/main.py` — Ponto de Entrada

Cria a aplicação FastAPI com:
- `root_path="/historic"` — todas as rotas são prefixadas com `/historic`
- `default_response_class=ORJSONResponse` — serialização JSON rápida via `orjson`
- Swagger UI personalizado servido em `/historic/` usando assets estáticos
- Sem docs/redoc URLs automáticos (apenas Swagger personalizado)

```python
app = FastAPI(
    root_path=root_path,
    docs_url=None,
    redoc_url=None,
    default_response_class=ORJSONResponse,
    title="Ditto Events API",
    description="API to manage historical events from Eclipse Ditto",
)
```

### 4.2 `app/routers/events.py` — Endpoints API

Este ficheiro define todos os endpoints REST e as suas dependências.

**Dependências principais:**

- **`auth`**: Instância retornada por `get_auth()` do `fastapi-oidc`. Configura a validação OIDC com as definições.
- **`get_events_service(session)`**: Dependência FastAPI que cria um `EventsService` com uma sessão de base de dados.
- **`check_role(roles)`**: Retorna uma função de dependência que inspeciona o `resource_access` do token Keycloak para verificar as roles necessárias.

**Lógica de verificação de role (`check_role`)**:
```python
def check_role(roles: list[str]):
    def check_role_inner(token: KeycloakToken):
        if settings.auth.client_id not in token.resource_access:
            raise HTTPException(403)
        token_roles = token.resource_access[settings.auth.client_id].roles
        if not any(role in token_roles for role in roles):
            raise HTTPException(403)
    return check_role_inner
```

**Modelo do token** (`KeycloakToken`):
```python
class KeycloakToken(IDToken):
    resource_access: dict[str, ClientResourceAccess] = {}
```

**`ClientResourceAccess`**:
```python
class ClientResourceAccess(BaseModel):
    roles: list[str] = []
```

**Lista de endpoints** (todos sob APIRouter com `dependencies=[Depends(auth)]`):

| Função do Endpoint | Path | Método | Método do Service |
|---|---|---|---|
| `read_available_things` | `/things` | GET | `get_available_things()` |
| `read_event_paths` | `/events/{thing_id}/paths` | GET | `get_event_paths_with_action()` |
| `read_events` | `/events` | GET | `get_events()` |
| `read_events_by_thing` | `/events/{thing_id}` | GET | `get_events_by_thing()` |
| `insert_events` | `/events` | POST | `insert_events()` |
| `delete_events` | `/events/{thing_id}` | DELETE | `delete_events()` |
| `read_jsonpath_projection` | `/events/projection/{thing_id}` | GET | `get_jsonpath_projection()` |
| `read_events_custom_time_buckets` | `/events/time-buckets/{thing_id}` | GET | `get_events_custom_time_buckets()` ou `get_events_custom_time_buckets_with_path()` |

### 4.3 `app/services/events_service.py` — Lógica de Negócio

A classe `EventsService` encapsula todas as operações de base de dados. Recebe uma `Session` do SQLModel por injeção no construtor.

#### Métodos:

**`get_available_things(thing_id_prefix)`**
- SQL: `SELECT DISTINCT thing_id FROM dittoevent [WHERE thing_id LIKE prefix%]`
- Retorna lista de strings `thing_id` distintas.

**`get_event_paths_with_action(thing_id, since, until)`**
- SQL: `SELECT DISTINCT path, action FROM dittoevent WHERE thing_id = :id AND time BETWEEN :since AND :until`
- Retorna `list[PathResponseObject]`.

**`get_events(since, until, thing_id_prefix, path_prefix, action, limit)`**
- SQL: `SELECT * FROM dittoevent WHERE time BETWEEN :since AND :until [AND thing_id LIKE prefix%] [AND action = :action] [AND path LIKE prefix%] ORDER BY time DESC [LIMIT :limit]`
- Retorna `list[DittoEvent]`.

**`get_events_by_thing(thing_id, since, until, path_prefix, action)`**
- Igual a `get_events` mas filtrado por `thing_id` exato.

**`insert_events(events)`**
- Itera sobre os eventos, adiciona cada um à sessão, faz commit.
- Retorna `None`.

**`delete_events(thing_id, since, until)`**
- SQL: `DELETE FROM dittoevent WHERE thing_id = :id AND time BETWEEN :since AND :until`
- Retorna contagem de linhas apagadas.

**`get_jsonpath_projection(json_path, thing_id, since, path_prefix, until)`**
- Usa a função PostgreSQL `jsonb_path_query()` para extrair valores que correspondem a uma expressão JSONPath.
- SQL (simplificado):
  ```sql
  SELECT jsonb_path_query(value, CAST(:json_path AS JSONPATH))
  FROM dittoevent
  WHERE thing_id = :id AND time BETWEEN :since AND :until [AND path LIKE prefix%]
  ```

**`get_events_custom_time_buckets(json_path, since, until, bucket_minutes, agg_type, thing_id)`**
- Agrupa eventos em buckets temporais e aplica uma função de agregação sobre um valor extraído por JSONPath.
- **Modo "all-time"** (`bucket_minutes <= 0 ou None`): Retorna um único bucket com `MIN(time)` como rótulo.
- **Modo bucket**: Usa aritmética `EXTRACT(epoch FROM time) / bucket_seconds` para calcular os limites dos buckets, depois `to_timestamp()` para converter de volta.
- Funções de agregação: `count`, `sum`, `avg`, `min`, `max`.
- Para agregações numéricas (`sum`, `avg`, `min`, `max`), o valor extraído é convertido para `Float`.
- **Tratamento de erros**:
  - `DataError` com "cannot cast jsonb object to double precision" → 400 com mensagem explicativa.
  - `ProgrammingError` (sintaxe JSONPath inválida) → 400.
  - Ambos acionam `session.rollback()`.

**`get_events_custom_time_buckets_with_path(json_path, since, until, path_prefixes, bucket_minutes, agg_type, thing_id)`**
- Igual ao anterior mas também agrupa por `DittoEvent.path`.
- `path_prefixes` é uma string separada por vírgulas que é dividida num array e usada numa condição OR via `sqlalchemy.or_()`.
- Retorna resultados segmentados por path.

### 4.4 `app/models/ditto_events.py` — Modelo de Base de Dados

```python
class DittoEvent(SQLModel, table=True):
    time: datetime = Field(primary_key=True)           # Coluna de partição (hypertable)
    index: Optional[int] = Field(..., Identity(...))   # Auto-incremento, também PK
    thing_id: str = Field(index=True)                  # Indexado para filtragem
    action: Action = Field(sa_column=Column(SAEnum))   # created/modified/deleted/merged
    revision: PositiveInt | None
    path: str                                          # Caminho da feature Ditto
    value: dict = Field(sa_type=JSONB)                 # Payload JSON
```

**Configuração TimescaleDB** (definida via `__timescale_config__` e um listener de evento `after_create`):

| Propriedade | Valor |
|---|---|
| `time_column` | `time` |
| `chunk_time_interval` | 1 dia |
| `compress` | Sim |
| `compress_segmentby` | `thing_id` |
| `compress_orderby` | `time DESC` |
| `compress_interval` | 7 dias (política de compressão) |

A função `create_timescale_features()` (registada via `@event.listens_for(..., "after_create")`) executa três comandos SQL quando a tabela é criada:
1. `SELECT create_hypertable(...)` — converte a tabela numa hipertabela
2. `ALTER TABLE ... SET (timescaledb.compress, ...)` — ativa compressão nativa
3. `SELECT add_compression_policy(...)` — define a agenda de compressão automática

Este modelo está duplicado no `dt4mob-historical-writer` para manter os serviços independentes.

### 4.5 `app/models/paths_response.py` — Modelo de Resposta

```python
class PathResponseObject(BaseModel):
    path: str
    action: Action
    model_config = {"from_attributes": True}
```

Usado pelo endpoint `/events/{thing_id}/paths`.

### 4.6 `app/models/util.py` — Enum Action

```python
class Action(str, Enum):
    MODIFIED = "modified"
    CREATE = "created"
    DELETE = "deleted"
    MERGED = "merged"
```

Usado como tipo de coluna e como parâmetro de filtro em queries.

### 4.7 `app/database_engine/__init__.py` — Singleton Engine

```python
timescale_engine = TimescaleDBEgineManager()
timescale_engine.create_db_tables()
```

- Cria o engine SQLAlchemy **uma vez** no momento da importação do módulo.
- Chama `SQLModel.metadata.create_all(engine)` — isto cria a tabela `dittoevent` e aciona o evento `after_create` que configura a hipertabela TimescaleDB.
- **Importante**: Importa o modelo `DittoEvent` antes de `create_db_tables()` para garantir que o modelo está registado em `SQLModel.metadata`.
- `get_session()` é um generator que produz uma `Session`, faz rollback em caso de exceção, e fecha no `finally`.

### 4.8 `app/database_engine/TimeScaleEngineManager.py` — Wrapper do Engine

```python
class TimescaleDBEgineManager:
    def __init__(self):
        self.engine = create_engine(
            url=settings.timescale.get_connection(),
            echo= (settings.log_level == "DEBUG"),
        )

    def create_db_tables(self):
        SQLModel.metadata.create_all(self.engine)
```

- `get_connection()` substitui `postgresql://` por `postgresql+psycopg://` para usar o driver `psycopg`.
- Engine `echo` ativado apenas quando `LOG_LEVEL=DEBUG`.

### 4.9 `app/settings/__init__.py` — Configuração Global

```python
class Settings(BaseSettings):
    log_level: LogLevel = Field(validation_alias="LOG_LEVEL", default="INFO")
    auth: AuthSettings
    timescale: TimeScaleSettings

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # Permite sintaxe AUTH__CLIENT_ID
        extra="ignore",
    )
```

- Singleton: `settings = Settings()` criado ao nível do módulo.
- Lê de variáveis de ambiente ou ficheiro `.env`.
- O delimitador `__` permite aninhamento: `AUTH__CLIENT_ID` → `settings.auth.client_id`.

### 4.10 `app/settings/auth.py` — Configuração de Autenticação

```python
class AuthSettings(BaseModel):
    client_id: str
    audience: str = "account"
    server_uri: str
    issuer: str | list[str]
    signature_cache_ttl: PositiveInt = 3600
    read_role: list[str] = ["historical-read"]
    write_role: list[str] = ["historical-write"]
```

### 4.11 `app/settings/timescale.py` — Configuração Timescale

```python
class TimeScaleSettings(BaseModel):
    database_timezone: str = "Europe/Lisbon"
    connection: str

    def get_connection(self):
        return self.connection.replace("postgresql", "postgresql+psycopg")
```

---

## 5. Fluxo de Autenticação

```
Pedido do Cliente (com Bearer JWT)
    │
    ▼
Middleware fastapi-oidc
    │
    ├── Valida assinatura JWT (cache por signature_cache_ttl segundos)
    ├── Verifica issuer contra AUTH__ISSUER
    └── Descodifica token para modelo KeycloakToken
    │
    ▼
check_role(["historical-read"]) ou check_role(["historical-write"])
    │
    ├── Extrai resource_access[client_id].roles do token
    ├── Verifica se alguma das roles necessárias está presente
    └── Levanta 403 se faltar
    │
    ▼
Função do endpoint executa
```

A biblioteca `fastapi-oidc` é configurada com `token_type=KeycloakToken` para que o token descodificado esteja disponível como um modelo Pydantic tipado. A dependência personalizada `check_role()` é usada por endpoint via `Depends()`.

---

## 6. Estratégia de Tratamento de Erros

| Cenário | Handler | HTTP Status | Detalhe da Resposta |
|---|---|---|---|
| JWT ausente/inválido | `fastapi-oidc` | 401/403 | Automático |
| Role em falta no token | `check_role()` | 403 | `"Missing role"` |
| Erro de cast JSONB→Float (time-buckets) | `events_service.py` | 400 | Sugere usar `count` ou corrigir o JSONPath |
| Sintaxe JSONPath inválida | `events_service.py` | 400 | Devolve a mensagem de erro do PostgreSQL |
| Erro genérico de BD | SQLAlchemy | 500 | Propagado |

Na camada de serviço, erros que ocorrem durante a execução de queries acionam `session.rollback()` para reverter quaisquer alterações não confirmadas antes de levantar a exceção HTTP.

---

## 7. Dependências

### Pacotes Python (de `pyproject.toml`)

| Pacote | Versão | Propósito |
|---|---|---|
| `fastapi[standard]` | ≥0.128.0 | Framework web |
| `fastapi-oidc` | ≥0.0.11 | Middleware de autenticação Keycloak OIDC |
| `orjson` | ≥3.11.7 | Serialização JSON rápida |
| `psycopg[binary]` | ≥3.3.2 | Adaptador PostgreSQL |
| `pydantic-settings` | ≥2.12.0 | Configuração baseada em ambiente |
| `sqlmodel` | ≥0.0.31 | Integração Pydantic + SQLAlchemy ORM |

### Serviços Externos

| Serviço | Protocolo | Propósito |
|---|---|---|
| **TimescaleDB** | PostgreSQL (psycopg) | Persistência de dados (hipertabela) |
| **Keycloak** | HTTPS (OIDC) | Validação de tokens JWT |

---

## 8. Implantação (Deploy)

### Dockerfile

- **Imagem base**: `python:3.14-slim`
- **Gestor de pacotes**: `uv` 0.9.27 (copiado de `ghcr.io/astral-sh/uv:0.9.27`)
- **Ficheiros estáticos**: Copiados explicitamente de `./app/static`
- **Comando**: `fastapi run app/main.py --port 8080 --host 0.0.0.0`

### Helm Chart

O chart em `charts/dt4mob-historical/` implanta a API e o writer em conjunto:

- **API Deployment**: Executa a imagem `data-lake-api` na porta 8080.
- **Writer Deployment**: Executa a imagem `data-gateway`, conecta-se ao Kafka via mTLS.
- **TimescaleDB Cluster**: Gerido pelo operator Cloud Native PostgreSQL (CNPG) com extensão TimescaleDB.
- **Kafka Topic**: Gerido pelo operator Strimzi.

### Imagens dos Contentores

Registry: `atnog-harbor.av.it.pt/dt4mob/`
- API: `data-lake-api`
- Writer: `data-gateway`
