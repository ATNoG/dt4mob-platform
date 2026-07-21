# dt4mob-garbage-collector — Manual do Utilizador

## O que é?

`dt4mob-garbage-collector` é um job batch que limpa periodicamente twins digitais expirados do [Eclipse Ditto](https://www.eclipse.org/ditto/). Liga-se ao Ditto, pesquisa things cujo timestamp `attributes/expiry_ts` está no passado e elimina-os.

Foi desenhado para executar como um **Kubernetes CronJob** (por omissão: a cada 5 minutos), mas também pode ser executado localmente com Docker ou Python.

---

## Pré-requisitos

- Uma instância do **Eclipse Ditto** (com Thing Search ativado)
- Um **servidor de autenticação OIDC** (ex.: Keycloak) com um cliente capaz de emitir tokens via fluxo **password grant**
- Para execução local: Python 3.13 + [uv](https://docs.astral.sh/uv/) ou Docker
- Para Kubernetes: um cluster Kubernetes + Helm 3

---

## Configuração

Toda a configuração é feita através de variáveis de ambiente. Chaves aninhadas usam `__` como delimitador (ex.: `DITTO__API_URL`).

### Gerais

| Variável | Omisso | Descrição |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Nível de logging: `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG` |

### Conexão Ditto

| Variável | Omisso | Descrição |
|---|---|---|
| `DITTO__API_URL` | `http://localhost:8080` | URL base da API do Ditto |
| `DITTO__BASE_API_PATH` | `/api/2` | Prefixo do caminho REST API |
| `DITTO__BASE_WS_PATH` | `/ws/2` | Prefixo do caminho WebSocket |
| `DITTO__SEARCH_SIZE` | `200` | Tamanho da página para resultados de pesquisa |

### Autenticação (OIDC)

| Variável | Omisso | Descrição |
|---|---|---|
| `AUTH__TOKEN_ENDPOINT` | `https://localhost:8443/auth/realms/dt4mob/protocol/openid-connect/token` | Endpoint OIDC do token |
| `AUTH__USERNAME` | — | Nome de utilizador (mutuamente exclusivo com `AUTH__USERNAME_FILE`) |
| `AUTH__USERNAME_FILE` | — | Caminho para ficheiro com o nome de utilizador |
| `AUTH__PASSWORD` | — | Palavra-passe (mutuamente exclusivo com `AUTH__PASSWORD_FILE`) |
| `AUTH__PASSWORD_FILE` | — | Caminho para ficheiro com a palavra-passe |
| `AUTH__CLIENT_ID` | `ditto` | ID do cliente OIDC |
| `AUTH__CA_CRT_FILE` | — | Caminho para ficheiro de certificado CA para TLS do servidor OIDC |

> **É obrigatório definir um de `AUTH__USERNAME` ou `AUTH__USERNAME_FILE`** (o mesmo para a palavra-passe). São mutuamente exclusivos.

---

## Deploy

### Opção 1: Local com Docker

```bash
# Build
docker build -t dt4mob-garbage-collector:latest .

# Executar com ficheiro .env
docker run --env-file .env dt4mob-garbage-collector:latest
```

### Opção 2: Local com Python + uv

```bash
# Instalar dependências
uv sync --locked

# Executar
uv run main.py
```

### Opção 3: Kubernetes via Helm

O projeto inclui um Helm chart em `charts/dt4mob-garbage-collector/`.

```bash
# Instalar (a partir do diretório charts)
helm install garbage-collector ./charts/dt4mob-garbage-collector --values values.yaml
```

**Referência de valores Helm:**

| Valor | Omisso | Descrição |
|---|---|---|
| `image.repository` | `atnog-harbor.av.it.pt/dt4mob/garbage-collector` | Imagem do contentor |
| `image.tag` | `latest` | Tag da imagem |
| `image.imagePullPolicy` | `Always` | Política de pull |
| `config.schedule` | `*/5 * * * *` | Schedule cron |
| `config.logLevel` | `INFO` | Nível de logging |
| `config.ditto.apiUrl` | `ditto-gateway:8080` | URL da API Ditto |
| `config.ditto.baseApiPath` | `/api/2` | Caminho REST do Ditto |
| `config.ditto.baseWsPath` | `/ws/2` | Caminho WebSocket do Ditto |
| `config.auth.tokenEndpoint` | `https://dt4mob-keycloak:8443/auth/realms/dt4mob/protocol/openid-connect/token` | Endpoint OIDC do token |
| `config.auth.existingSecret` | `""` | Nome de um Kubernetes Secret existente (se vazio, o chart cria um) |
| `config.auth.caSecret` | `""` | Nome do Secret contendo o certificado CA (chave: `ca.crt`) |

**Credenciais no Kubernetes:**

Se `config.auth.existingSecret` estiver vazio e uma palavra-passe for fornecida, o chart cria um Secret com o nome de utilizador e palavra-passe. Também pode pré-criar um Secret com as chaves `username` e `password` e referenciá-lo via `config.auth.existingSecret`.

---

## Como Funciona

1. O script abre uma ligação **WebSocket** ao Ditto e autentica-se com um token JWT Bearer.
2. Inicia uma tarefa em background que **renova o token** antes de expirar, enviando o novo token para o Ditto via mensagem de controlo.
3. Consulta a **REST search API** do Ditto por things onde `lt(attributes/expiry_ts,'<current_time>')` — i.e., things cujo timestamp de expiração está no passado.
4. Para cada thing expirada, constrói um envelope de comando **delete** do Protocolo Ditto.
5. Envia cada comando delete através da ligação **WebSocket** e aguarda uma resposta de sucesso (status 200 ou 204).
6. Após todas as eliminações serem confirmadas, o script **termina**.
7. O **CronJob** (ou outro scheduler) desencadeia a próxima execução de acordo com o schedule configurado.

---

## Monitorização & Logs

**Docker:**
```bash
docker logs <container_id>
```

**Kubernetes:**
```bash
# Listar CronJob e os seus Jobs
kubectl get cj,garbage-collector
kubectl get jobs -l app.kubernetes.io/name=garbage-collector

# Ver logs da última execução
kubectl logs job/<job_name>
```

O output dos logs inclui informação sobre:
- Número de things expiradas encontradas
- Cada comando delete enviado e o seu resultado
- Eventos de renovação de token
- Ciclo de vida da ligação

---

## Resolução de Problemas

| Problema | Causa provável | Verificar |
|---|---|---|
| O script não consegue ligar | URL do Ditto errado ou inacessível | Confirmar `DITTO__API_URL` e conectividade de rede |
| A autenticação falha | Credenciais OIDC erradas ou expiradas | Confirmar `AUTH__USERNAME`/`AUTH__PASSWORD` e `AUTH__TOKEN_ENDPOINT` |
| Nenhuma thing eliminada | Sem things expiradas, ou atributo `expiry_ts` em falta nas things | Verificar things no Ditto e o caminho do atributo |
| Erros de renovação de token | Endpoint OIDC inacessível ou problema de TLS | Verificar `AUTH__CA_CRT_FILE` se usar CA personalizada |
| Instalação Helm falha | Valores obrigatórios em falta | Confirmar que username/password ou `existingSecret` foram fornecidos |
