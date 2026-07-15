# Manual do Utilizador — Ditto Events API

## 1. Introdução

A **Ditto Events API** (`dt4mob-historical-api`) é um serviço FastAPI que expõe uma interface REST para consultar, inserir e apagar eventos históricos produzidos pelo **Eclipse Ditto**. Os eventos são armazenados numa **hipertabela TimescaleDB**, permitindo consultas eficientes de séries temporais, projeções JSONPath e agregações temporais.

Este serviço faz parte da plataforma **DT4Mob** e é implantado em conjunto com o `dt4mob-historical-writer`, que ingere eventos do Kafka para a mesma base de dados.

---

## 2. Configuração

Toda a configuração é feita através de variáveis de ambiente. Também é suportado um ficheiro `.env` no diretório de trabalho.

### 2.1 Gerais

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `LOG_LEVEL` | Não | `INFO` | Nível de logging (`CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`) |

### 2.2 Autenticação (Keycloak OIDC)

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `AUTH__CLIENT_ID` | Sim | — | Client ID do Keycloak |
| `AUTH__AUDIENCE` | Não | `account` | Audiência OIDC |
| `AUTH__SERVER_URI` | Sim | — | URI do realm Keycloak (ex: `https://keycloak.example.com/realms/myrealm`) |
| `AUTH__ISSUER` | Sim | — | URL do issuer OIDC (pode ser uma lista: `["url1","url2"]`) |
| `AUTH__SIGNATURE_CACHE_TTL` | Não | `3600` | TTL da cache de assinaturas JWT em segundos |
| `AUTH__READ_ROLE` | Não | `["historical-read"]` | Role(s) Keycloak necessária(s) para endpoints de leitura |
| `AUTH__WRITE_ROLE` | Não | `["historical-write"]` | Role(s) Keycloak necessária(s) para endpoints de escrita |

### 2.3 TimescaleDB

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `TIMESCALE__CONNECTION` | Sim | — | URI de conexão (ex: `postgresql://user:pass@host:5432/db`) |
| `TIMESCALE__DATABASE_TIMEZONE` | Não | `Europe/Lisbon` | Fuso horário da base de dados |

### 2.4 Delimitador de Configuração Aninhada

O separador `__` (duplo underscore) é usado pelo `pydantic-settings` para aninhar variáveis.  
Por exemplo: `AUTH__CLIENT_ID` mapeia para `settings.auth.client_id`.

---

## 3. Execução Local

### 3.1 Pré-requisitos

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv/) gestor de pacotes
- Uma instância TimescaleDB em execução

### 3.2 Setup

```bash
# Clonar o repositório e entrar no diretório do serviço
cd services/dt4mob-historical-api

# Instalar dependências
uv sync

# Criar um ficheiro .env com as variáveis necessárias (ver §2)
# Exemplo:
#   LOG_LEVEL=DEBUG
#   AUTH__CLIENT_ID=my-client
#   AUTH__SERVER_URI=https://keycloak.example.com/realms/myrealm
#   AUTH__ISSUER=https://keycloak.example.com/realms/myrealm
#   TIMESCALE__CONNECTION=postgresql://user:pass@localhost:5432/historical
```

### 3.3 Executar

```bash
# Desenvolvimento (auto-reload)
uv run fastapi dev app/main.py --port 8080

# Produção
uv run fastapi run app/main.py --port 8080 --host 0.0.0.0
```

A API estará disponível em `http://localhost:8080/historic/`.  
O Swagger UI é servido no path raiz.

---

## 4. Execução com Docker

### 4.1 Build

```bash
docker build -t data-lake-api -f dockerfile .
```

### 4.2 Executar

```bash
docker run -p 8080:8080 \
  -e LOG_LEVEL=INFO \
  -e AUTH__CLIENT_ID=my-client \
  -e AUTH__SERVER_URI=https://keycloak.example.com/realms/myrealm \
  -e AUTH__ISSUER=https://keycloak.example.com/realms/myrealm \
  -e TIMESCALE__CONNECTION=postgresql://user:pass@host:5432/db \
  data-lake-api
```

---

## 5. Endpoints da API

Todos os endpoints são montados sob o path base `/historic`.  
Endpoints de leitura requerem a role `historical-read`; endpoints de escrita requerem `historical-write`.

| Método | Path | Descrição | Role |
|---|---|---|---|
| `GET` | `/historic/` | Swagger UI (HTML personalizado) | Nenhuma |
| `GET` | `/historic/things` | Listar IDs de things distintas | `historical-read` |
| `GET` | `/historic/events/{thing_id}/paths` | Listar pares (path, action) distintos | `historical-read` |
| `GET` | `/historic/events` | Consultar eventos com filtros | `historical-read` |
| `GET` | `/historic/events/{thing_id}` | Consultar eventos por thing ID | `historical-read` |
| `POST` | `/historic/events` | Inserir eventos | `historical-write` |
| `DELETE` | `/historic/events/{thing_id}` | Apagar eventos num intervalo temporal | `historical-write` |
| `GET` | `/historic/events/projection/{thing_id}` | Extrair campos via JSONPath | `historical-read` |
| `GET` | `/historic/events/time-buckets/{thing_id}` | Agregações temporais | `historical-read` |

### 5.1 `GET /historic/things`

Devolve todos os `thing_id` distintos, opcionalmente filtrados por prefixo.

**Parâmetros de query:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `thing_id_prefix` | `str` | Não | Filtrar things cujo ID começa com este prefixo |

### 5.2 `GET /historic/events/{thing_id}/paths`

Devolve pares (path, action) distintos para uma thing num intervalo temporal.

**Parâmetros de query:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `since` | `datetime` (ISO 8601) | Sim | Início do intervalo |
| `until` | `datetime` (ISO 8601) | Não | Fim do intervalo (padrão: agora) |

### 5.3 `GET /historic/events`

Consulta eventos em todas as things com múltiplos filtros.

**Parâmetros de query:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `since` | `datetime` | Sim | Início do intervalo |
| `until` | `datetime` | Não | Fim do intervalo (padrão: agora) |
| `thing_id_prefix` | `str` | Não | Filtrar por prefixo do thing ID |
| `path_prefix` | `str` | Não | Filtrar por prefixo do path |
| `action` | `enum` | Não | Filtrar por ação (`created`, `modified`, `deleted`, `merged`) |

### 5.4 `GET /historic/events/{thing_id}`

Consulta eventos para uma thing específica.

**Parâmetros de query:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `since` | `datetime` | Sim | Início do intervalo |
| `until` | `datetime` | Não | Fim do intervalo (padrão: agora) |
| `path_prefix` | `str` | Não | Filtrar por prefixo do path |
| `action` | `enum` | Não | Filtrar por ação |

### 5.5 `POST /historic/events`

Insere um ou mais eventos diretamente (alternativa à ingestão por Kafka).

**Corpo do pedido:** Objeto JSON com um array `events`:

```json
{
  "events": [
    {
      "time": "2024-01-01T00:00:00Z",
      "thing_id": "org.eclipse.ditto:my-thing",
      "action": "modified",
      "path": "/features/temperature/properties/value",
      "revision": 1,
      "value": 25.5
    }
  ]
}
```

### 5.6 `DELETE /historic/events/{thing_id}`

Apaga eventos para uma thing num intervalo temporal.

**Parâmetros de query:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `since` | `datetime` | Sim | Início do intervalo |
| `until` | `datetime` | Sim | Fim do intervalo |

### 5.7 `GET /historic/events/projection/{thing_id}`

Extrai campos específicos do `value` JSON dos eventos usando uma expressão JSONPath.

**Parâmetros de query:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `json_path` | `str` | Sim | Expressão JSONPath (ex: `$.temperature`) |
| `since` | `datetime` | Sim | Início do intervalo |
| `until` | `datetime` | Não | Fim do intervalo (padrão: agora) |
| `path_prefix` | `str` | Não | Filtrar por prefixo do path |

### 5.8 `GET /historic/events/time-buckets/{thing_id}`

Agrupa eventos em buckets temporais e executa agregações sobre um valor JSONPath.

**Parâmetros de query:**

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `json_path` | `str` | Sim | JSONPath para o valor a agregar |
| `since` | `datetime` | Sim | Início do intervalo |
| `until` | `datetime` | Sim | Fim do intervalo |
| `bucket_minutes` | `int` | Não | Largura do bucket em minutos (omitir ou `<=0` para bucket único) |
| `agg_type` | `enum` | Não | Função de agregação: `count`, `sum`, `avg`, `min`, `max` (padrão: `count`) |
| `path_prefix` | `str` | Não | Prefixos de path separados por vírgula para segmentar resultados |

**Nota:** Quando `path_prefix` contém múltiplos valores separados por vírgula, o endpoint usa `get_events_custom_time_buckets_with_path` que agrupa resultados também por path.

---

## 6. Autenticação

A API usa **Keycloak OIDC** (OpenID Connect) para autenticação. O middleware `fastapi-oidc` valida tokens JWT em todos os pedidos.

- Endpoints de leitura requerem a role `historical-read` (configurável via `AUTH__READ_ROLE`).
- Endpoints de escrita requerem a role `historical-write` (configurável via `AUTH__WRITE_ROLE`).

Para aceder à API, inclua um token Bearer no cabeçalho `Authorization`:

```
Authorization: Bearer <seu-token-jwt-do-keycloak>
```

---

## 7. Implantação (Deploy)

### 7.1 Kubernetes (Helm)

Os serviços API e writer são implantados em conjunto através de um único Helm chart localizado em `charts/dt4mob-historical/`.

**Recursos principais criados pelo chart:**

| Recurso | Kind | Descrição |
|---|---|---|
| `api-deployment.yaml` | `Deployment` | Executa o contentor da API na porta 8080 |
| `api-service.yaml` | `Service` | Expõe a API na porta 8080 |
| `writer-deployment.yaml` | `Deployment` | Executa o writer (consumidor Kafka) |
| `writer-config.yaml` | `ConfigMap` | Configuração Kafka e TimescaleDB para o writer |
| `kafka-topic.yaml` | `KafkaTopic` (Strimzi) | Tópico para eventos Ditto |
| `timescale-cluster.yaml` | `Cluster` (CNPG) | Cluster PostgreSQL + TimescaleDB |

**Imagens dos contentores** (publicadas em `atnog-harbor.av.it.pt/dt4mob/`):
- API: `data-lake-api`
- Writer: `data-gateway`

A API é exposta através de um ingress que encaminha `/historic` para o serviço da API.

### 7.2 Variáveis de Ambiente para Deploy

No Helm chart, as variáveis de autenticação são definidas diretamente no deployment, enquanto `TIMESCALE__CONNECTION` é injetada através de um Kubernetes Secret por segurança.
