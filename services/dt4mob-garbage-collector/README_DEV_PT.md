# dt4mob-garbage-collector — Documentação para Developers

## Visão Geral

`dt4mob-garbage-collector` é um job batch Python independente que se conecta ao [Eclipse Ditto](https://www.eclipse.org/ditto/) via WebSocket e REST API, pesquisa por twins digitais cujo `attributes/expiry_ts` expirou e elimina-os enviando comandos `delete` do protocolo Ditto.

O script executa até ao fim e termina, sendo desenhado para ser executado como um **Kubernetes CronJob** (ou qualquer scheduler periódico).

---

## Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.13 |
| Gestor de pacotes | [uv](https://docs.astral.sh/uv/) (Astral) |
| Runtime assíncrono | `asyncio` (stdlib) |
| Cliente WebSocket | `websockets` 16.0 |
| Cliente HTTP | `httpx` 0.28.1 (async) |
| Configuração | `pydantic-settings` 2.13.0 |
| Validação de dados | `pydantic` 2.12.5 |
| Deploy | Docker (Alpine) + Helm (Kubernetes CronJob) |

---

## Estrutura do Projeto

```
dt4mob-garbage-collector/
├── main.py                                  # Ponto de entrada
├── pyproject.toml                           # Metadados do projeto e dependências
├── uv.lock                                  # Versões bloqueadas das dependências
├── Dockerfile                               # Build do contentor
├── .python-version                          # Versão do Python
├── README_DEV.md
├── README_DEV_PT.md
├── README_USER.md
├── README_USER_PT.md
└── src/
    ├── models/
    │   ├── __init__.py
    │   └── ditto.py                         # Modelos Pydantic (SearchResponse, DittoProtocolEnvelope, etc.)
    ├── services/
    │   ├── auth/
    │   │   └── __init__.py                 # AuthenticationService (OIDC password grant)
    │   ├── ditto_api/
    │   │   ├── __init__.py                 # Fábrica do singleton DittoClient
    │   │   └── ditto_api.py                # DittoClient (WebSocket + REST)
    │   ├── envelope_formatter/
    │   │   └── ditto_thing/
    │   │       ├── __init__.py             # Fábrica do singleton DittoThingEnvelopeFormatter
    │   │       └── DittoProtocol.py        # Construtor de DittoProtocolEnvelope
    │   └── garbage_collector/
    │       ├── __init__.py                 # Fábrica do singleton GarbageCollector
    │       └── garbage_collector.py        # Orquestração do GarbageCollector
    └── settings/
        ├── __init__.py                     # Settings (raiz pydantic-settings)
        ├── auth.py                         # AuthSettings
        └── ditto.py                        # DittoSettings
```

Externo a este diretório:

```
charts/dt4mob-garbage-collector/             # Helm chart
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl
    ├── garbage-collector-job.yaml           # Definição do CronJob
    └── garbage-collector-secret.yaml        # Secret para credenciais
```

---

## Arquitetura & Fluxo de Dados

```
main.py
  │
  ├── ditto_client.connect()                 # Handshake WebSocket + auth JWT
  │     └── tarefas em background:
  │           ├── _listen_loop()             # lê mensagens WS, resolve futures
  │           └── _token_refresh_loop()      # renova JWT antes de expirar
  │
  ├── garbage_collector.get_expired_envelops()
  │     │
  │     ├── ditto_client.get_things_expired_lt(now)
  │     │     └── REST GET /api/2/search/things?filter=lt(attributes/expiry_ts,'...')
  │     │         (paginado via parâmetro cursor)
  │     │
  │     └── para cada thing ID:
  │           └── formatter.delete_message(id)
  │                 └── DittoProtocolEnvelope { topic, headers, path }
  │
  ├── para cada envelope:
  │     └── ditto_client.send_ws_message(msg)   # envia JSON via WS, aguarda ACK
  │
  └── ditto_client.close()
```

---

## Detalhes de Implementação

### Padrão Singleton

Cada módulo de serviço expõe um singleton ao nível do módulo através de uma fábrica `_new_instance()`:

- `src/services/auth/__init__.py` → `auth_service`
- `src/services/ditto_api/__init__.py` → `ditto_client`
- `src/services/envelope_formatter/ditto_thing/__init__.py` → `envelop_formater`
- `src/services/garbage_collector/__init__.py` → `garbage_collector`

As dependências são resolvidas no momento da construção e passadas aos consumidores downstream.

### Ciclo de Vida do WebSocket & Token

1. `DittoClient.connect()` abre um WebSocket para `{ws_url}/?x-csrf-token=no-csrf-check`.
2. Envia a mensagem de controlo `START-SEND-EVENTS`.
3. Inicia duas tarefas `asyncio` em background:
   - **`_listen_loop()`**: lê todas as mensagens recebidas. Se a mensagem for uma resposta JSON com um `correlation-id`, resolve a future correspondente em `_responses`. Mensagens de controlo não-JSON são registadas.
   - **`_token_refresh_loop()`**: calcula o tempo de vida restante do token, espera até 5 segundos antes da expiração, obtém um novo token do endpoint OIDC e envia-o como mensagem de controlo: `JWT-TOKEN?jwtToken=<new_token>`.

### Correspondência por Correlation-id

Cada envelope enviado contém um UUID em `headers.correlation-id`. O remetente armazena uma future indexada por este UUID. O loop de escuta associa respostas recebidas pelo mesmo `correlation-id` e resolve a future, permitindo uma semântica fiável de enviar-e-aguardar sobre WebSocket.

### Paginação

`get_things_expired_lt()` executa uma pesquisa paginada usando o mecanismo de cursor do Ditto. Solicita `DittoSettings.search_size` itens por página (200 por omissão, máximo 500 hard-coded). O loop continua até não haver cursor retornado.

### Loop de Recolha de Lixo

Em `main.py`, após obter a lista de envelopes de eliminação, o script itera sobre eles enviando cada um via WebSocket. O ciclo `while` exterior volta a pesquisar things expiradas após cada lote e continua até restarem menos de 5 envelopes, capturando quaisquer novas expirações desde o início do script.

---

## Dependências

### Diretas

| Pacote | Versão | Propósito |
|---|---|---|
| `httpx` | >=0.28.1 | Cliente HTTP assíncrono para a REST API do Ditto |
| `pydantic` | >=2.12.5 | Validação de dados e modelos |
| `pydantic-settings` | >=2.13.0 | Configuração baseada em variáveis de ambiente |
| `websockets` | >=16.0 | Cliente WebSocket assíncrono |

### Transitivas

`annotated-types`, `anyio`, `certifi`, `h11`, `httpcore`, `idna`, `pydantic-core`, `python-dotenv`, `typing-extensions`, `typing-inspection`.

---

## Configuração

Todas as configurações são carregadas via `pydantic-settings` a partir de variáveis de ambiente usando `__` como delimitador aninhado. Consulte `README_USER_PT.md` para a tabela completa de variáveis de ambiente.

---

## Setup de Desenvolvimento

```bash
# Clonar e entrar no diretório
cd services/dt4mob-garbage-collector

# Instalar uv se não estiver instalado (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependências
uv sync --locked

# Executar
uv run main.py
```

Para execução local, fornecer variáveis de ambiente (via ficheiro `.env` ou inline):

```bash
DITTO__API_URL=http://localhost:8080 \
AUTH__TOKEN_ENDPOINT=https://keycloak/auth/realms/dt4mob/protocol/openid-connect/token \
AUTH__USERNAME=myuser \
AUTH__PASSWORD=mypass \
uv run main.py
```

---

## Build

```bash
docker build -t dt4mob-garbage-collector:latest .
```

O Dockerfile usa `alpine:edge` com Python 3.13, copia o `uv` de `astral/uv:latest`, instala dependências de build, executa `uv sync --locked` e define `CMD ["uv","run","main.py"]`.
