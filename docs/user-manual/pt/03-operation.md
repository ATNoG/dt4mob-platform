# Operação {#sec:operation}

As seguintes secções documentam procedimentos padrão para a operação regular da
plataforma.

## Gestão de utilizadores

A plataforma utiliza uma abordagem de gestão centralizada de utilizadores
construída sobre o Keycloak[^keycloak] e o OpenID Connect[^oidc] (OIDC daqui
em diante) para permitir que os utilizadores tenham uma experiência de Single
Sign On (SSO) entre todos os diferentes serviços da plataforma. Para os serviços
partilham lógica de autenticação e autorização, e para os administradores
poderem gerir facilmente os utilizadores e os seus cargos.

Ao instalar ou atualizar a plataforma, uma tarefa de manutenção é iniciada
automaticamente, que criará as configurações necessárias do Keycloak, incluindo
um realm, um cliente e cargos para administração e para os serviços do
sistema funcionarem corretamente. Como tal, os administradores não precisam de
configurar contas de serviço e/ou cargos para a plataforma começar a funcionar
normalmente, necessitando apenas de configurar contas de utilizador para
participantes externos conforme necessário.

[^keycloak]: <https://www.keycloak.org/>
[^oidc]: <https://openid.net/developers/how-connect-works/>

### Aceder à consola de administração do Keycloak

O Keycloak é exposto no caminho `https://<host>/auth`, onde `<host>` é o nome
de domínio configurado na @sec:installation. Navegar diretamente para `/auth`
redirecionará para um formulário de login que controla o acesso à consola de
administração. Uma conta de administração é criada automaticamente durante a
instalação com o nome de utilizador `admin` e uma palavra-passe gerada de forma
segura, que pode ser recuperada com acesso ao cluster Kubernetes executando o
seguinte comando:

```
$ kubectl get secrets dt4mob-keycloak-admin -o jsonpath="{.data.password}" | base64 -d
```

Isto imprimirá a palavra-passe no standard output do terminal. Utilizando as
credenciais obtidas e submetendo o formulário de login, é permitido o acesso à
consola de administração do Keycloak.

![Consola de administração do Keycloak](./user-manual/assets/03-operation/keycloak-admin-master-realm.png)

O Keycloak exibirá um aviso a indicar que a conta é um utilizador administrador
temporário e para criar uma conta de administrador permanente. O Keycloak é
provisionado exclusivamente para a plataforma, e as credenciais para o
utilizador admin são geradas de forma segura; como tal, não é estritamente
necessário criar uma conta de administrador permanente.

No entanto, pode ser útil fazê-lo para definir uma conta de administração mais
granular ou aumentar a segurança da conta de administrador, por exemplo,
adicionando 2FA. Para tal, consulte a documentação do Keycloak para
mais instruções.

As próximas secções vão incidir todas sobre o realm `dt4mob`; para trocar o
realm selecionado, clique no link "Manage realms" na barra lateral esquerda e
depois no nome do realm `dt4mob`, que deve estar destacado como um link.

![Seleção de realms no Keycloak](./user-manual/assets/03-operation/keycloak-admin-manage-realms.png)

### Adicionar um utilizador

Uma instalação nova conterá apenas os utilizadores dos serviços da plataforma.
Para criar uma conta de utilizador para uma entidade externa poder interagir com
a plataforma, comece por navegar para o link "Users" na barra lateral esquerda
(certifique-se de que o realm atual é o realm `dt4mob`).

![Listagem de utilizadors do realm](./user-manual/assets/03-operation/keycloak-dt4mob-users.png)

Em seguida, pressione o botão "Add user" na interface; isto abrirá um
formulário para criar um novo utilizador. O único campo obrigatório é o nome de
utilizador, que deve ser único e será utilizado na autenticação. No entanto, se
o utilizador tiver de ter acesso à instância de visualização Grafana, então um
email também tem de ser especificado, caso contrário o utilizador não conseguirá
aceder mesmo com os cargos corretos. Os outros campos podem ser deixados vazios
ou preenchidos conforme necessário; para mais detalhes, consulte a documentação
do Keycloak.

Submeter o formulário criará o utilizador e redirecionará para a sua página de
detalhes.

![User details page](./user-manual/assets/03-operation/keycloak-user-details.png)

Neste ponto, ainda não será possível utilizar a conta, pois não tem quaisquer
credenciais para usar na autenticação. Para atribuir uma palavra-passe, navegue
para o separador "Credentials" na página de detalhes do utilizador e pressione
o botão "Set password". Isto abrirá um popup com um formulário para definir uma
palavra-passe para o utilizador.

![Setting the user's password](./user-manual/assets/03-operation/keycloak-set-password.png)

A palavra-passe pode ser definida como temporária (opção por predefinição), que
implicara a solicitação ao utilizador da sua alteração após o primeiro login.
Configure esta opção conforme relevante para o utilizador criado. Preencha o
formulário com uma palavra-passe adequada, confirme-a e submeta o formulário.
O utilizador terá agora credenciais na forma do seu nome de utilizador e da
palavra-passe que acabou de ser configurada. Estas devem ser comunicadas à
entidade externa através de um canal seguro.

### Atribuição de cargos {#sec:assign-role}

Uma conta recém-criada não terá quaisquer cargos na plataforma atribuídos.
Isto permite-lhe aceder ao Ditto e ao serviço de visualização e interagir com
things que são permitidas pelas suas respetivas políticas.

No entanto, para aceder a outros serviços, como a API de dados históricos, o
serviço de emissão de certificados, ou até mesmo para ter acesso
administrativo, tem de ser atribuídos cargos ao utilizador.

Para atribuir um cargo ao utilizador, navegue para a sua página de
detalhes, depois para o separador "Role mapping" e pressione o botão "Assign
Role". Isto abrirá um dropdown com duas opções; selecione a opção "Client
roles".

![Atribuição de cargos](./user-manual/assets/03-operation/keycloak-assign-client-roles.png)

Isto abrirá um popup com uma lista de cargos que podem ser atribuídos ao
utilizador; destes, apenas os que têm o Client ID `ditto` são relevantes para
autorização no contexto dos serviços da plataforma.

![Seleção de cargos da plataforma](./user-manual/assets/03-operation/keycloak-select-client-roles.png)

Os cargos podem ser criadas por administradores para uso em políticas Ditto, e
a própria plataforma define um conjunto de cargos especiais que concedem acesso
a serviços extra dentro da plataforma. A tabela abaixo lista estes cargos
especiais e o acesso extra que concedem.

<!-- &nbsp; is used to pad the table column so that the column is not so small that it causes the text to be broken up -->

| Cargo &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Acesso concedido                                                                                                                                                                            |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `admin`                                              | Concede acesso total à plataforma, incluindo todas as things, todos os serviços e capacidade de gerar certificados personificando outros utilizadores.                                      |
| `historical-read`                                    | Concede acesso de leitura à API de dados históricos. Deve notar-se que não existe noção de políticas nos dados históricos e, como tal, todas as things são consultáveis por qualquer pessoa com este cargo. |
| `historical-write`                                   | Concede acesso de escrita à API de dados históricos, permitindo o preenchimento retrospetivo de informações de outros sistemas.                                                             |
| `certificate-issuer`                                 | Concede acesso ao serviço de emissão de certificados, permitindo ao utilizador obter certificados de cliente válidos que podem ser usados para conetar dispositivos ao Hono.                |

Table: Cargos especiais da plataforma

Basta selecionar os cargos que o utilizador deve ter e finalizar clicando
em "Assign" na parte inferior do popup. Apesar dos cargos serem atribuídos
instantaneamente, as sessões mais antigas ainda estarão a usar tokens mais
antigos que não têm esses cargos. Isto pode ser resolvido aguardando que o
token seja atualizado, momento em que terá os cargos, ou fazendo logout e
login novamente. Isto fará com que um novo token seja gerado, que conterá a nova
atribuição de cargos.

### Criação de cargos

Como mencionado anteriormente, os administradores podem criar cargos adicionais
que podem então ser usados em políticas para controlar o acesso a things dentro
da plataforma. Isto pode ser útil, pois permite definir políticas de autorização
em termos de cargo do utilizador em vez de identidade. Por exemplo, os técnicos
podem precisar de acesso a todas as portagens da empresa no país. Em vez de
definir cada técnico na política para as portagens, pode ser criada um cargo e
atribuído aos técnicos conforme necessário, e a política só precisa de conceder
acesso ao cargo uma vez.

Para definir uma novo cargo, comece por navegar para o link "Clients" na barra
lateral esquerda (certifique-se de que o realm atual é o realm `dt4mob`). Deve
aparecer uma lista de clients, incluindo os usados internamente pelo Keycloak e
o client `ditto`, que é o client usado pela plataforma.

![Listagem de clientes no realm](./user-manual/assets/03-operation/keycloak-clients.png)

Clicando no link para o cliente `ditto` abrirá a sua página de detalhes do
cliente; a partir daqui, navegue para o separador "Roles", que exibirá uma lista
de todos os cargos do cliente.

![Listagem de cargos do cliente](./user-manual/assets/03-operation/keycloak-client-roles.png)

A partir daqui, pressione o botão "Create role", que irá navegar para o
formulário de criação de cargo. Insira o nome do novo cargo e opcionalmente
uma descrição para o mesmo, e submeta o formulário para concluir a criação do
cargo. Atribua o cargo a um utilizador conforme explicado na @sec:assign-role
para começar a utilizá-lo.

## Ditto

Como mencionado anteriormente, o Eclipse Ditto é o backend que permite o
armazenamento e consulta de gémeos digitais na plataforma DT4Mob. As seguintes
secções explicam como aceder ao Ditto, criar políticas e obter privilégios
DevOps.

### Aceder ao Ditto

O Ditto é exposto nos caminhos `https://<host>/ui` e `https://<host>/api`, onde
`<host>` é o nome de domínio configurado na @sec:installation, para a Interface
Web e a API, respetivamente. Navegar para a Interface Web redirecionará
automaticamente para o formulário de login do Keycloak, se o utilizador ainda
não tiver uma sessão de autenticação válida. Não é necessário nenhum cargo
para interagir com o Ditto. O acesso à API requer que o token de acesso seja
obtido previamente e passado como um bearer token no cabeçalho `Authorization`.

### Definição de políticas

As políticas controlam o acesso a si próprias e a things dentro do Ditto. Uma
política é composta por um conjunto de entradas, cada uma definindo para um
conjunto de subjects as operações de recurso permitidas. Uma thing tem
exatamente uma política associada que controla o seu acesso. As políticas podem
importar umas das outras para permitir reutilizar lógica para decisões de
autorização comuns. Para mais informações, consulte a documentação
relevante[^policies].

Uma política pode ser criada através da Interface Web no separador "policies"
ou através da API. Para criar uma política através da Interface Web,
certifique-se de que nenhuma política está selecionada e navegue
para o separador "JSON" no painel direito (não na barra de navegação).

![Painel de políticas](./user-manual/assets/03-operation/ditto-create-policy.png)

A partir daqui, pressione o botão "create" no painel direito para começar a
editar a nova política; não será possível editar nenhum dos campos antes de o
fazer. Defina um ID de política único que deve seguir o formato
`<namespace>:<name>` e escreva a definição da política na caixa de texto
abaixo. Para detalhes sobre a sintaxe de definição de política, consulte a
documentação do Ditto.

No painel esquerdo, na secção "Who am I", encontra-se uma lista de todos os
subjects que o utilizador atual representa. Estes são diretamente derivados do
token de acesso obtido do Keycloak. A tabela abaixo lista os diferentes
subjects extraídos do token que podem estar em definições de política:

| Subject &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Descrição                                                                                                                                                                                                                                                                                  |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `keycloak:sub:<uid>`                                                                         | O campo `sub` do token de acesso, identifica o utilizador de forma única. Não deve ser usado em definições de política, pois não é óbvio quem é o utilizador real a partir do UID.                                                                                                         |
| `keycloak:user:<uid>`                                                                        | O nome de utilizador extraído do token de acesso, identifica o utilizador de forma única neste momento, mas pode ser reutilizado para outro utilizador mais tarde se este for eliminado e um novo for criado. Preferível a `keycloak:sub`, mas na maioria dos casos devem ser usados cargos. |
| `keycloak:role:<uid>`                                                                        | Cargos do utilizador extraídos do token de acesso. Geralmente a melhor opção ao definir políticas, pois permite definir acesso por cargo em vez de identidade do utilizador, sendo também mais fácil de gerir.                                                                             |

Table: Subjects obtidos a partir do token de acesso

[^policies]: <https://eclipse.dev/ditto/basic-policy.html>

#### Permitir mensagens do Hono

As políticas precisam de incluir um subject especial para permitir que mensagens
sejam aceites da conexão Hono para things controladas pela política. Isto é
feito adicionando a seguinte entrada à política:

```{.json caption="Entrada da conexão Hono na política"}
"HONO": {
  "subjects": {
    "pre-authenticated:hono-connection-<tenant>": {
      "type": "Connection to Eclipse Hono"
    }
  },
  "resources": {
    "thing:/": {
      "grant": [
        "READ",
        "WRITE"
      ],
      "revoke": []
    },
    "message:/": {
      "grant": [
        "READ",
        "WRITE"
      ],
      "revoke": []
    },
    "policy:/": {
      "grant": [
        "READ"
      ],
      "revoke": []
    }
  },
  "importable": "implicit"
}
```

Onde `<tenant>` é o nome do tenant que foi configurado na @sec:installation.

#### Permitir exportação histórica

A conexão do exportador histórico também requer uma entrada especial para
permitir que a evolução das things seja armazenada. Isto permite que as things
sejam excluídas da base de dados histórica, de modo a que apenas as things
estritamente necessárias sejam guardadas, ajudando com custos, desempenho e
conformidade.

```{.json caption="Entrada da exportação histórica na política"}
"KAFKA_EXPORT": {
  "subjects": {
    "pre-authenticated:kafka-export-connection-<tenant>": {
      "type": "Kafka Connection"
    }
  },
  "resources": {
    "thing:/": {
      "grant": [
        "READ"
      ],
      "revoke": []
    },
    "policy:/": {
      "grant": [
        "READ"
      ],
      "revoke": []
    }
  },
  "importable": "implicit"
}
```

Onde `<tenant>` é o nome do tenant que foi configurado na @sec:installation.

### Acesso DevOps

Algumas operações, como gerir conexões de entrada (Hono) e de saída (exporter
histórico) ou executar operações de administração no Ditto, requerem a
utilização de uma conta especial chamada DevOps. Esta conta não utiliza a
gestão centralizada de utilizadores, sendo as suas credenciais geradas durante
a instalação no cluster.

O nome de utilizador é `devops`, e a palavra-passe pode ser recuperada usando o
seguinte comando:

```sh
$ kubectl get secret dt4mob-ditto-gateway-secret -o jsonpath="{.data.devops-password}" | base64 -d
```

Estas credenciais podem então ser usadas através de autenticação básica nas
APIs que requerem a utilização desta conta ou na Interface Web pressionando o
botão "Authorize" no extremo direito da barra de navegação. Isto abrirá um
popup com dois formulários para autenticação. O de cima é para autenticação
regular usando Keycloak, enquanto que o de baixo é para autenticação DevOps.

Ao inserir as credenciais e submeter o formulário, o acesso às páginas
"Connections" e "Operations" será possível sem receber erros de autenticação em
falta.

Nota: Por vezes, o botão de rádio "Basic" junto ao formulário de login DevOps
não está selecionado (isto deve-se a um bug no Ditto), e a autenticação não
prosseguirá nesse caso. Para corrigir, basta selecionar o botão de rádio e
submeter o formulário novamente.
