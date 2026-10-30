# Controle de Pedidos — CNP

Sistema web interno para **cadastro, acompanhamento e gestão de pedidos de compra**, desenvolvido em Python com Flask e SQLite.

A aplicação centraliza o ciclo operacional do pedido — desde o cadastro e anexos até o acompanhamento de previsão de chegada, entrega, lixeira e notificações automáticas por e-mail.

> **Versão atual:** `8.0.0`  
> **Aplicação:** Controle de Pedidos — CNP  
> **Autor:** Gabriel S. Justino

---

## Sumário

- [Visão geral](#visão-geral)
- [Principais funcionalidades](#principais-funcionalidades)
- [Fluxo operacional](#fluxo-operacional)
- [Arquitetura](#arquitetura)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Tecnologias](#tecnologias)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Execução](#execução)
- [Acesso pela rede local](#acesso-pela-rede-local)
- [Autenticação e segurança](#autenticação-e-segurança)
- [Gestão de pedidos](#gestão-de-pedidos)
- [Status operacionais](#status-operacionais)
- [Filtros e dashboard](#filtros-e-dashboard)
- [Anexos](#anexos)
- [Notificações por e-mail](#notificações-por-e-mail)
- [Banco de dados](#banco-de-dados)
- [Rotas HTTP](#rotas-http)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Logs](#logs)
- [Backup e persistência](#backup-e-persistência)
- [Manutenção e evolução](#manutenção-e-evolução)
- [Desenvolvimento](#desenvolvimento)
- [Troubleshooting](#troubleshooting)
- [Limitações e pontos de atenção](#limitações-e-pontos-de-atenção)
- [Licença](#licença)

---

## Visão geral

O **Controle de Pedidos — CNP** é uma aplicação web voltada para uso interno, com foco no acompanhamento de pedidos de compra.

O sistema permite:

- cadastrar pedidos;
- registrar fornecedor e transportadora;
- definir o tipo de frete;
- controlar datas do pedido, embarque e previsão de chegada;
- registrar valores financeiros;
- associar vendedor e responsável;
- registrar nota fiscal e CTE;
- anexar documentos;
- manter histórico de observações;
- acompanhar pedidos em um dashboard;
- marcar pedidos como entregues;
- enviar notificações automáticas por e-mail;
- mover pedidos para uma lixeira lógica;
- restaurar pedidos;
- consultar documentos anexados;
- registrar eventos relevantes em logs.

A aplicação utiliza **SQLite**, portanto não depende de um servidor de banco de dados externo.

---

## Principais funcionalidades

### Dashboard

O dashboard concentra a visão operacional dos pedidos ativos.

Indicadores disponíveis:

- **Total de pedidos**
- **Pedidos atrasados**
- **Pedidos próximos do prazo**
- **Pedidos entregues**
- **Pedidos em trânsito**
- **Valor total dos pedidos**
- **Valor dos pedidos em trânsito**
- **Valor dos pedidos atrasados**

Também é possível aplicar filtros combináveis.

### Cadastro de pedido

Campos principais:

| Campo | Obrigatório | Descrição |
|---|---:|---|
| Número do pedido | Não | Identificação do pedido |
| Fornecedor | Sim | Empresa fornecedora |
| Vendedor | Não | Contato/comercial do fornecedor |
| Responsável | Sim | Responsável interno |
| E-mail | Não | Destinatário das notificações |
| Transportadora | Sim | Empresa responsável pelo transporte |
| Tipo de frete | Sim | Aéreo, Rodoviário ou Retirada |
| Data do pedido | Sim | Data de emissão/cadastro |
| Previsão de chegada | Sim | Data prevista para recebimento |
| Data de embarque | Não | Data em que o pedido foi embarcado |
| Valor do pedido | Não | Valor principal do pedido |
| Valor da NF | Não | Valor informado na nota fiscal |
| Valor do frete | Não | Custo do transporte |
| Nota fiscal | Não | Número/identificação da NF |
| CTE | Não | Conhecimento de transporte |
| Arquivo | Não | Documento anexado |
| Observação | Não | Informação adicional |

### Edição

Pedidos existentes podem ser editados sem perder o histórico de observações.

Ao adicionar uma nova observação, o sistema registra:

```text
DD/MM/AAAA >> texto da observação
```

Exemplo:

```text
18/09/2026 >> Fornecedor confirmou embarque.
18/09/2026 >> NF enviada por e-mail.
```

Se um novo arquivo for anexado durante a edição, o arquivo anterior é removido do armazenamento após o banco confirmar a alteração.

### Entrega

Um pedido pode ser marcado/desmarcado como **Entregue**.

Ao marcar como entregue:

1. o banco recebe `entregue = 1`;
2. o pedido passa para o status operacional `Entregue`;
3. caso exista e-mail cadastrado, uma notificação de entrega pode ser enviada;
4. o sistema registra que a notificação foi enviada para evitar duplicidade.

Ao desfazer a entrega, a flag de notificação de entrega é zerada.

### Lixeira

A exclusão de pedidos é **lógica**, não física.

Em vez de remover o registro do SQLite:

```text
deletado = 1
```

O pedido deixa de aparecer no dashboard normal e passa para a tela **Lixeira**.

É possível restaurá-lo:

```text
deletado = 0
```

Esse modelo preserva o registro no banco e reduz o risco de exclusões irreversíveis acidentais.

---

## Fluxo operacional

```text
┌──────────────┐
│ Login        │
└──────┬───────┘
       │
       ▼
┌─────────────────────┐
│ Dashboard           │
│ - KPIs              │
│ - filtros           │
│ - pedidos           │
└──────┬──────────────┘
       │
       ├──────────────► Novo pedido
       │                    │
       │                    ▼
       │              Validação dos dados
       │                    │
       │                    ▼
       │              SQLite + anexo
       │
       ├──────────────► Visualizar / editar
       │
       ├──────────────► Marcar entregue
       │                    │
       │                    ▼
       │              E-mail de entrega
       │
       ├──────────────► Excluir
       │                    │
       │                    ▼
       │                 Lixeira
       │                    │
       │                    ▼
       │                 Restaurar
       │
       ▼
Scheduler em segundo plano
       │
       ├── atrasado ───────► e-mail
       │
       └── até 3 dias ─────► alerta por e-mail
```

---

## Arquitetura

A aplicação utiliza uma arquitetura simples baseada em **Flask + Blueprints + camada de persistência + serviços**.

```text
Browser
   │
   ▼
Flask
   │
   ├── login blueprint
   │      └── autenticação
   │
   ├── pedidos blueprint
   │      ├── dashboard
   │      ├── CRUD operacional
   │      ├── lixeira
   │      └── uploads
   │
   ├── extensions
   │      ├── CSRF
   │      └── rate limiting
   │
   ├── database.py
   │      └── SQLite
   │
   └── services
          ├── email_service.py
          └── notification_service.py
```

### Componentes principais

#### `app.py`

Inicializa a aplicação Flask.

Responsabilidades:

- criação da instância Flask;
- configuração da sessão;
- limite de upload;
- inicialização de CSRF;
- inicialização do rate limiting;
- proteção contra acessos externos;
- registro dos Blueprints;
- configuração opcional de `ProxyFix`.

#### `server.py`

É o ponto de entrada recomendado para execução do ambiente de servidor.

Responsabilidades:

- inicializar logging;
- criar/migrar o banco;
- iniciar o scheduler;
- determinar o IP do servidor;
- iniciar o **Waitress**;
- disponibilizar a aplicação na rede configurada.

O servidor utiliza:

```text
8 threads
porta padrão: 8080
```

#### `config.py`

Centraliza:

- caminhos;
- segredo da aplicação;
- banco;
- uploads;
- logs;
- SMTP;
- notificações;
- limites;
- extensões de arquivos.

As informações sensíveis são carregadas através de variáveis de ambiente.

#### `database.py`

Responsável pelo banco principal de pedidos.

Recursos:

- SQLite;
- `sqlite3.Row`;
- WAL;
- `busy_timeout` de 5 segundos;
- criação automática da tabela;
- migração automática de colunas.

#### `routes/pedidos.py`

Implementa as operações dos pedidos:

- dashboard;
- cadastro;
- edição;
- consulta;
- entrega;
- exclusão lógica;
- lixeira;
- restauração;
- download de anexos.

#### `login/login.py`

Implementa:

- login;
- logout;
- cadastro;
- proteção de rotas através de `login_required`;
- limitação de tentativas nos endpoints.

#### `login/login_database.py`

Camada de persistência da autenticação.

Responsabilidades:

- criar usuários;
- validar usuários;
- validar senha;
- validar e-mail;
- armazenar senha com hash;
- bloquear temporariamente contas após falhas consecutivas;
- realizar migrações da tabela de usuários.

#### `services/email_service.py`

Monta e envia os e-mails transacionais.

Possui modelos específicos para:

- pedido atrasado;
- pedido próximo do prazo;
- pedido entregue.

Os e-mails são construídos em HTML e possuem versão alternativa em texto.

#### `services/notification_service.py`

Executa o monitoramento automático dos pedidos.

O scheduler:

1. consulta pedidos não deletados;
2. calcula a situação em relação à previsão;
3. identifica atrasos;
4. identifica pedidos com até 3 dias para chegada;
5. identifica entregas;
6. envia notificações;
7. grava flags para impedir reenvios.

#### `helpers.py`

Concentra funções auxiliares para:

- moeda;
- valores;
- datas;
- status;
- e-mail;
- validação de arquivos;
- MIME;
- diretórios de upload.

---

## Estrutura do projeto

```text
Controle-de-Pedidos-V8/
└── App/
    ├── app.py
    ├── config.py
    ├── database.py
    ├── extensions.py
    ├── helpers.py
    ├── server.py
    │
    ├── .env
    ├── .env.example
    ├── .gitignore
    │
    ├── databases/
    │   ├── pedidos.db
    │   └── usuarios.db
    │
    ├── login/
    │   ├── __init__.py
    │   ├── login.py
    │   ├── login_database.py
    │   └── requirements.txt
    │
    ├── routes/
    │   ├── __init__.py
    │   └── pedidos.py
    │
    ├── services/
    │   ├── __init__.py
    │   ├── email_service.py
    │   └── notification_service.py
    │
    ├── static/
    │   ├── css/
    │   │   ├── admin.css
    │   │   ├── auth.css
    │   │   └── style.css
    │   │
    │   └── js/
    │       ├── admin.js
    │       ├── cadastro.js
    │       ├── dashboard.js
    │       ├── layout.js
    │       ├── lixeira.js
    │       ├── login.js
    │       └── sidebar.js
    │
    ├── templates/
    │   ├── cadastro.html
    │   ├── dashboard.html
    │   ├── layout.html
    │   ├── lixeira.html
    │   ├── login.html
    │   ├── _pedido_fields.html
    │   └── _sidebar.html
    │
    ├── uploads/
    │   └── YYYY/
    │       └── MM/
    │
    └── logs/
        └── YYYY/
            └── MM/
                └── DD/
                    └── server.log
```

> Bancos, uploads, logs e `.env` são dados de execução e devem permanecer fora do controle de versão.

---

## Tecnologias

| Tecnologia | Utilização |
|---|---|
| **Python 3** | Linguagem principal |
| **Flask** | Framework web |
| **SQLite** | Banco de dados |
| **Werkzeug** | Segurança, hash e utilidades Flask |
| **Flask-WTF** | Proteção CSRF |
| **Flask-Limiter** | Rate limiting |
| **python-dotenv** | Carregamento do `.env` |
| **Waitress** | Servidor WSGI |
| **HTML/CSS** | Interface |
| **JavaScript** | Interações assíncronas e interface |

---

## Requisitos

### Sistema

Recomendado:

- Windows 10/11 ou Linux;
- Python compatível com as dependências do projeto;
- acesso à rede local para uso por outros computadores;
- conta SMTP válida para notificações.

### Dependências

O arquivo `requirements/requirements.txt` contém:

```text
Flask>=3.0
Werkzeug>=3.0
Flask-WTF>=1.3
Flask-Limiter>=4.0
python-dotenv>=1.0
waitress>=3.0
```

Para desenvolvimento, `requirements/requirements-dev.txt` adiciona:

```text
pytest
pytest-cov
freezegun
ruff
mypy
```

---

## Instalação

### 1. Clonar ou copiar o projeto

```bash
git clone <URL_DO_REPOSITORIO>
cd Controle-de-Pedidos-V8/App
```

Caso o projeto seja recebido como arquivo ZIP, extraia e entre na pasta `App`.

### 2. Criar ambiente virtual

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements/requirements.txt
```

Para desenvolvimento:

```bash
pip install -r requirements/requirements-dev.txt
```

### 4. Criar o `.env`

Copie:

```text
.env.example
```

para:

```text
.env
```

No Windows:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

### 5. Configurar as variáveis

Edite o `.env` e informe pelo menos:

```env
SECRET_KEY=uma-chave-aleatoria-e-segura
SMTP_USER=seuemail@empresa.com
SMTP_PASSWORD=sua-senha-ou-senha-de-app
```

---

## Configuração

### Gerar uma `SECRET_KEY`

Não utilize uma chave previsível.

Exemplo:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copie o resultado para:

```env
SECRET_KEY=...
```

### SMTP

Exemplo:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seuemail@empresa.com
SMTP_PASSWORD=sua-senha-de-app
SMTP_USE_TLS=true
```

Para provedores diferentes do Gmail, substitua o host, porta e credenciais conforme o serviço SMTP utilizado.

> Para contas que utilizam autenticação em dois fatores, normalmente deve ser utilizada uma **senha de aplicativo**, quando suportada pelo provedor.

---

## Execução

### Execução recomendada

Dentro da pasta `App`:

```bash
python server.py
```

O servidor:

1. inicializa o banco;
2. executa migrações necessárias;
3. inicia o scheduler;
4. configura o logging;
5. inicia o Waitress.

A porta padrão é:

```text
8080
```

### Execução direta do Flask

Também é possível executar:

```bash
python app.py
```

Nesse modo, a aplicação utiliza o servidor de desenvolvimento do Flask em:

```text
127.0.0.1:5000
```

Para ambiente de uso interno/produção, prefira `server.py` com Waitress.

---

## Acesso pela rede local

O `server.py` tenta descobrir automaticamente o IP da máquina através da interface usada para saída da rede.

Por padrão:

```text
HOST = IP detectado
PORT = 8080
```

Exemplo:

```text
http://192.168.1.50:8080
```

### Definir host manualmente

No `.env`:

```env
SERVER_HOST=192.168.1.50
SERVER_PORT=8080
```

O código utiliza essas variáveis quando presentes.

### Firewall

Se outros computadores não conseguirem acessar o sistema, verifique:

- firewall do Windows;
- regra de entrada da porta `8080`;
- conectividade entre as máquinas;
- perfil da rede;
- IP correto do servidor.

---

## Autenticação e segurança

A aplicação possui várias camadas de proteção.

### Senhas com hash

As senhas não são armazenadas em texto puro.

O sistema utiliza:

```python
generate_password_hash()
check_password_hash()
```

do Werkzeug.

### Proteção contra session fixation

Após login bem-sucedido:

```python
session.clear()
```

A sessão anterior é descartada antes da criação da sessão autenticada.

### CSRF

A aplicação utiliza:

```text
Flask-WTF
```

para proteção contra Cross-Site Request Forgery.

Formulários incluem tokens CSRF e as requisições AJAX de alteração utilizam o token disponibilizado no layout.

### Rate limiting

O Flask-Limiter possui limites globais:

```text
200 requisições por dia
50 requisições por hora
```

Além disso:

```text
/login    → 5 por minuto
/cadastro → 10 por minuto
```

### Bloqueio de login

Uma conta é temporariamente bloqueada após:

```text
5 tentativas falhas
```

por:

```text
15 minutos
```

Quando o bloqueio expira, o contador de tentativas é resetado.

### Proteção contra timing attack

Quando o usuário informado não existe, o sistema executa uma verificação usando um hash fictício.

Isso reduz a diferença de tempo entre:

- usuário inexistente;
- usuário existente com senha incorreta.

### Validação de e-mail

O sistema valida o formato do endereço e evita que quebras de linha sejam utilizadas em valores relacionados a cabeçalhos de e-mail.

### Sanitização de logs

Valores controlados pelo usuário utilizados em logs são sanitizados contra `CRLF/log injection`.

### Restrição de acesso externo

Existe uma proteção no `before_request` que aceita somente endereços:

- privados;
- loopback.

Isso é compatível com o objetivo de uso interno.

IPs públicos são bloqueados com HTTP 403.

### Cookies de sessão

A configuração inclui:

```text
HttpOnly = True
SameSite = Lax
```

Quando `ATRAS_DE_PROXY=true`, o cookie também pode ser marcado como `Secure`.

---

## Gestão de pedidos

### Criar

Endpoint:

```text
POST /salvar
```

O processo inclui:

1. leitura dos campos;
2. validação;
3. normalização de valores;
4. validação de datas;
5. validação do anexo;
6. gravação do arquivo;
7. inserção no SQLite;
8. registro do evento no log.

### Editar

Endpoint:

```text
POST /editar/<id>
```

O sistema:

- atualiza os dados;
- mantém o histórico de observações;
- preserva o anexo quando nenhum novo arquivo é enviado;
- substitui o arquivo quando um novo documento é enviado;
- remove o arquivo anterior após o commit do banco.

### Consultar

Endpoint:

```text
GET /pedido/<id>
```

Retorna os dados do pedido em JSON para utilização pela interface.

### Entregar

Endpoint:

```text
POST /entregar/<id>
```

Alterna:

```text
entregue = 0
```

e:

```text
entregue = 1
```

### Excluir

Endpoint:

```text
POST /apagar/<id>
```

Realiza exclusão lógica:

```text
deletado = 1
```

### Restaurar

Endpoint:

```text
POST /restaurar/<id>
```

Reativa:

```text
deletado = 0
```

---

## Status operacionais

O status não é armazenado como uma coluna independente.

Ele é **derivado dinamicamente** a partir dos dados do pedido.

### Entregue

Se:

```text
entregue = 1
```

Status:

```text
Entregue
```

### Atrasado

Se a previsão de chegada já passou:

```text
previsão < hoje
```

Status:

```text
Atrasado
```

### Próximo do prazo

Se faltam até 3 dias:

```text
0 <= dias <= 3
```

Status:

```text
Próximo do prazo
```

### Em trânsito

Se existe data de embarque e o pedido ainda não foi entregue, desde que não esteja nas condições prioritárias anteriores:

```text
Em trânsito
```

### Novo

Se a data do pedido é hoje:

```text
Novo
```

### Aguardando envio

Quando nenhuma das condições anteriores é atendida:

```text
Aguardando envio
```

### Prioridade operacional

A implementação define a seguinte ordem prática:

```text
Atrasado
    ↓
Próximo do prazo
    ↓
Em trânsito
    ↓
Novo
    ↓
Aguardando envio
```

A entrega possui prioridade superior às demais.

---

## Filtros e dashboard

O dashboard aceita filtros combináveis.

Campos disponíveis:

- fornecedor;
- número do pedido;
- vendedor;
- transportadora;
- status;
- próximos do prazo;
- nota fiscal.

Os filtros são enviados via query string.

Exemplo conceitual:

```text
/dashboard?fornecedor=Fornecedor&status=Entregue
```

Os filtros são combinados usando lógica `AND`.

A busca textual utiliza `LIKE`, permitindo correspondência parcial.

Exemplo:

```text
PED-12
```

pode localizar pedidos como:

```text
PED-120
PED-1205
PED-12-A
```

---

## Anexos

São aceitos:

```text
.pdf
.png
.jpg
.jpeg
.xlsx
```

O sistema valida:

1. extensão;
2. MIME informado pelo upload;
3. nome do arquivo com `secure_filename()`.

### Limite

O tamanho máximo padrão da requisição é:

```text
10 MB
```

Configurável por:

```env
MAX_CONTENT_LENGTH=10485760
```

### Armazenamento

Os arquivos são organizados por ano e mês:

```text
uploads/
└── 2026/
    └── 09/
        ├── a1b2c3d4_documento.pdf
        └── e5f6g7h8_nota.xlsx
```

O prefixo aleatório reduz o risco de colisão entre arquivos com o mesmo nome.

### Download

Os anexos são disponibilizados pela rota:

```text
/uploads/<arquivo>
```

A rota exige autenticação.

---

## Notificações por e-mail

O sistema possui um scheduler em segundo plano.

O intervalo padrão é:

```text
1800 segundos
```

ou:

```text
30 minutos
```

Configurável por:

```env
NOTIFICATION_INTERVAL=1800
```

### Tipos de notificação

#### Pedido atrasado

Disparado quando:

```text
previsão de chegada < hoje
```

A notificação informa a quantidade de dias de atraso.

#### Pedido próximo do prazo

Disparado quando:

```text
0 <= dias <= 3
```

#### Pedido entregue

Enviado quando o pedido é marcado como entregue.

Também existe verificação pelo scheduler para pedidos entregues que ainda não possuam a flag de notificação.

### Controle de duplicidade

O banco mantém flags:

```text
email_atraso_enviado
email_alerta_enviado
email_entregue_enviado
```

Essas flags impedem que o scheduler envie repetidamente a mesma notificação.

### Link para o pedido

Quando `APP_BASE_URL` estiver configurada no ambiente, os e-mails podem conter um link direto para o pedido.

Exemplo:

```env
APP_BASE_URL=http://192.168.1.50:8080
```

> `APP_BASE_URL` é utilizada pelo serviço de notificações, embora não esteja listada no `.env.example` atual. Se for necessário gerar links nos e-mails, adicione essa variável ao `.env`.

### Anexos nos e-mails

Quando o pedido possui arquivo associado, o serviço de e-mail pode anexar o documento à mensagem.

---

## Banco de dados

O banco principal é:

```text
databases/pedidos.db
```

O banco de autenticação é:

```text
databases/usuarios.db
```

### Tabela `pedidos`

Estrutura atual:

| Campo | Tipo | Finalidade |
|---|---|---|
| `id` | INTEGER | Identificador |
| `fornecedor` | TEXT | Fornecedor |
| `transportadora` | TEXT | Transportadora |
| `tipo_frete` | TEXT | Tipo de frete |
| `data_pedido` | TEXT | Data do pedido |
| `previsao_chegada` | TEXT | Previsão |
| `valor` | REAL | Valor do pedido |
| `responsavel` | TEXT | Responsável |
| `email` | TEXT | E-mail |
| `arquivo` | TEXT | Caminho do anexo |
| `entregue` | INTEGER | Indicador de entrega |
| `deletado` | INTEGER | Exclusão lógica |
| `email_atraso_enviado` | INTEGER | Controle de e-mail de atraso |
| `email_alerta_enviado` | INTEGER | Controle de e-mail de alerta |
| `email_entregue_enviado` | INTEGER | Controle de e-mail de entrega |
| `vendedor` | TEXT | Vendedor |
| `nota_fiscal` | TEXT | Nota fiscal |
| `cte` | TEXT | CTE |
| `data_embarque` | TEXT | Data de embarque |
| `observacao` | TEXT | Histórico de observações |
| `valor_nota` | REAL | Valor da NF |
| `valor_frete` | REAL | Valor do frete |
| `numero_pedido` | TEXT | Número do pedido |

### Tabela `usuarios`

Estrutura:

| Campo | Tipo | Finalidade |
|---|---|---|
| `id` | INTEGER | Identificador |
| `username` | TEXT | Usuário |
| `email` | TEXT | E-mail |
| `senha_hash` | TEXT | Hash da senha |
| `tentativas_falhas` | INTEGER | Contador de falhas |
| `bloqueado_ate` | TIMESTAMP | Fim do bloqueio |
| `criado_em` | TIMESTAMP | Criação |

### SQLite WAL

O banco principal utiliza:

```sql
PRAGMA journal_mode=WAL
```

Isso melhora a convivência entre:

- requisições do Waitress;
- threads;
- scheduler de notificações.

Também é utilizado:

```sql
PRAGMA busy_timeout=5000
```

para aguardar até 5 segundos em situações de lock.

### Migrações automáticas

O sistema verifica a existência das colunas antes de executar `ALTER TABLE`.

Isso permite adicionar campos novos sem recriar o banco existente.

---

## Rotas HTTP

### Autenticação

| Método | Rota | Função |
|---|---|---|
| GET/POST | `/login` | Login |
| GET | `/logout` | Logout |
| GET/POST | `/cadastro` | Cadastro |

### Pedidos

| Método | Rota | Função |
|---|---|---|
| GET | `/` | Redireciona para dashboard |
| GET | `/dashboard` | Dashboard |
| POST | `/salvar` | Criar pedido |
| POST | `/editar/<id>` | Editar pedido |
| GET | `/pedido/<id>` | Obter pedido em JSON |
| POST | `/entregar/<id>` | Alternar entrega |
| POST | `/apagar/<id>` | Exclusão lógica |
| GET | `/lixeira` | Lista pedidos excluídos |
| POST | `/restaurar/<id>` | Restaurar pedido |
| GET | `/uploads/<filename>` | Download de anexo |

Todas as rotas operacionais de pedidos são protegidas pelo `login_required`.

---

## Variáveis de ambiente

Exemplo completo:

```env
SECRET_KEY=gere-uma-chave-segura

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seuemail@empresa.com
SMTP_PASSWORD=sua-senha-de-app
SMTP_USE_TLS=true

NOTIFICATION_INTERVAL=1800

MAX_CONTENT_LENGTH=10485760

DATABASE=databases/pedidos.db
UPLOAD_FOLDER=uploads
LOG_FOLDER=logs

ATRAS_DE_PROXY=false
FLASK_DEBUG=false
```

### Referência

| Variável | Padrão | Obrigatória | Descrição |
|---|---|---:|---|
| `SECRET_KEY` | — | **Sim** | Chave da sessão Flask |
| `SMTP_HOST` | `smtp.gmail.com` | Não | Servidor SMTP |
| `SMTP_PORT` | `587` | Não | Porta SMTP |
| `SMTP_USER` | — | **Sim** | Usuário SMTP |
| `SMTP_PASSWORD` | — | **Sim** | Senha SMTP |
| `SMTP_USE_TLS` | `true` | Não | TLS SMTP |
| `NOTIFICATION_INTERVAL` | `1800` | Não | Intervalo do scheduler |
| `MAX_CONTENT_LENGTH` | `10485760` | Não | Limite de upload |
| `DATABASE` | `databases/pedidos.db` | Não | Banco principal |
| `UPLOAD_FOLDER` | `uploads` | Não | Pasta de anexos |
| `LOG_FOLDER` | `logs` | Não | Pasta de logs |
| `ATRAS_DE_PROXY` | `false` | Não | Ativa `ProxyFix` |
| `FLASK_DEBUG` | `false` | Não | Debug do Flask |
| `SERVER_HOST` | IP detectado | Não | Host do Waitress |
| `SERVER_PORT` | `8080` | Não | Porta do Waitress |
| `APP_BASE_URL` | — | Não | URL usada nos links dos e-mails |

---

## Logs

O servidor grava logs em estrutura diária:

```text
logs/
└── 2026/
    └── 09/
        ├── 18/
        │   └── server.log
        └── ...
```

Cada registro contém:

```text
data/hora
nível
arquivo
linha
mensagem
```

Exemplo:

```text
[2026-09-18 15:00:00] [INFO] [server.py:...] Servidor disponível...
```

### Eventos registrados

Entre os eventos relevantes:

- inicialização;
- criação do banco;
- inicialização do scheduler;
- tentativas de login;
- tentativas de cadastro;
- criação de pedidos;
- edição de pedidos;
- exclusões;
- falhas de notificações;
- falhas de inicialização;
- tentativas de acesso externo bloqueadas.

Senhas não são gravadas nos logs.

---

## Backup e persistência

Os principais dados persistentes são:

```text
databases/pedidos.db
databases/usuarios.db
uploads/
logs/
```

Para um backup funcional da aplicação, não basta copiar somente o código.

Recomenda-se preservar:

```text
App/
├── databases/
├── uploads/
└── .env
```

O `.env` contém segredos e deve ser armazenado de maneira protegida.

### Backup mínimo

```text
databases/pedidos.db
databases/usuarios.db
uploads/
```

### Backup completo

```text
databases/
uploads/
logs/
.env
```

O diretório `logs` pode ser excluído do backup quando a política de retenção não exigir histórico operacional.

---

## Manutenção e evolução

### Adição de campos ao pedido

Quando um novo campo for necessário:

1. adicionar o campo no `CREATE TABLE`;
2. adicionar a migração em `database.py`;
3. atualizar cadastro;
4. atualizar edição;
5. atualizar consulta;
6. atualizar template;
7. atualizar JavaScript, quando necessário;
8. atualizar notificações, se o campo for utilizado nos e-mails;
9. atualizar esta documentação.

### Adição de campos ao usuário

Utilizar o mesmo padrão em:

```text
login/login_database.py
```

A função `init_db()` suporta migrações incrementais.

### Alteração do status

A regra central está em:

```text
helpers.py
└── obter_status_operacional()
```

Alterações de status devem ser feitas nessa função para evitar regras duplicadas entre dashboard, tabela e notificações.

### Alteração das notificações

As regras estão principalmente em:

```text
services/notification_service.py
```

Os templates dos e-mails estão em:

```text
services/email_service.py
```

---

## Desenvolvimento

### Ambiente de desenvolvimento

Instale:

```bash
pip install -r requirements/requirements-dev.txt
```

Ferramentas previstas:

- `pytest`;
- `pytest-cov`;
- `freezegun`;
- `ruff`;
- `mypy`.

### Testes

O projeto possui dependências preparadas para testes automatizados, mas o pacote analisado não contém uma suíte de testes automatizados no diretório entregue.

Antes de alterar regras críticas, recomenda-se criar testes para:

- cálculo de status;
- conversão de datas;
- normalização monetária;
- validação de e-mail;
- autenticação;
- bloqueio de conta;
- migrações;
- notificações;
- exclusão/restauração;
- upload;
- filtros.

### Qualidade de código

Para projetos em evolução, recomenda-se executar:

```bash
ruff check .
```

e:

```bash
mypy .
```

quando o código estiver preparado para a cobertura de tipos correspondente.

---

## Troubleshooting

### Aplicação não inicia

Verifique primeiro:

```text
.env
```

Principalmente:

```env
SECRET_KEY
SMTP_USER
SMTP_PASSWORD
```

As três são obrigatórias para a configuração atual.

### Erro relacionado ao banco

Confirme:

- existência da pasta `databases`;
- permissão de escrita;
- caminho configurado em `DATABASE`;
- se outro processo está mantendo o arquivo bloqueado.

O sistema utiliza WAL e `busy_timeout`, mas SQLite continua sujeito às limitações de escrita concorrente.

### Usuários de outras máquinas não conseguem acessar

Verifique:

1. IP do servidor;
2. porta `8080`;
3. firewall;
4. conectividade de rede;
5. configuração de `SERVER_HOST`.

### Acesso retorna 403

A aplicação bloqueia IPs considerados externos.

O acesso normal deve ocorrer por:

```text
localhost
127.0.0.1
rede privada
```

Se a aplicação estiver atrás de proxy reverso, a arquitetura precisa ser configurada cuidadosamente, pois a validação de IP ocorre antes do processamento das rotas.

### E-mails não são enviados

Verifique:

```env
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
SMTP_USE_TLS
```

Também consulte:

```text
logs/YYYY/MM/DD/server.log
```

### Alertas não chegam imediatamente

O scheduler não trabalha em tempo real.

Por padrão ele verifica os pedidos a cada:

```text
30 minutos
```

Para testes, é possível reduzir temporariamente:

```env
NOTIFICATION_INTERVAL=60
```

Isso fará uma verificação aproximadamente a cada minuto.

### Pedido aparece como atrasado

O cálculo utiliza a data atual do servidor.

A condição é:

```text
previsão de chegada < data atual
```

Confirme a data configurada no pedido e o horário/data do sistema operacional.

---

## Limitações e pontos de atenção

### SQLite

SQLite atende bem a uma aplicação interna de pequeno/médio porte, mas não é ideal para cenários com grande volume de escrita concorrente.

Se o sistema evoluir para:

- muitos usuários simultâneos;
- múltiplos servidores;
- grande volume de registros;
- integrações externas;
- alta taxa de escrita;

pode ser apropriado migrar para PostgreSQL ou outro SGBD servidor.

### Servidor HTTP interno

O `server.py` utiliza Waitress diretamente.

A configuração atual não implementa TLS/HTTPS por conta própria.

Para exposição além de uma rede interna controlada, recomenda-se utilizar um reverse proxy com HTTPS e revisar a configuração de:

```env
ATRAS_DE_PROXY=true
```

### Restrição de IP

A aplicação foi desenhada para uso interno.

A proteção:

```python
ip.is_private or ip.is_loopback
```

não deve ser tratada como substituta de:

- firewall;
- VPN;
- autenticação;
- HTTPS;
- controle de acesso da rede.

### Arquivos enviados

A validação atual utiliza extensão e MIME informado pelo upload.

Para ambientes de maior criticidade, pode ser interessante adicionar:

- inspeção real do conteúdo;
- antivírus;
- quotas;
- armazenamento externo;
- controle de tamanho por arquivo;
- políticas de retenção.

### Notificações em múltiplas instâncias

O scheduler é iniciado dentro do processo da aplicação.

Se forem executadas várias instâncias do servidor simultaneamente, cada instância poderá executar seu próprio scheduler.

Nesse cenário, recomenda-se mover as notificações para um worker dedicado ou mecanismo de tarefas distribuídas.

### `APP_BASE_URL`

A variável é utilizada pelo serviço de notificações para montar links diretos dos pedidos, mas não aparece no `.env.example` atual.

Se os links forem utilizados, adicione:

```env
APP_BASE_URL=http://IP_DO_SERVIDOR:8080
```

---

## Boas práticas operacionais

### Não versionar

Nunca envie para o Git:

```text
.env
*.db
*.sqlite
uploads/
logs/
__pycache__/
```

O `.gitignore` do projeto já contempla esses tipos de arquivo.

### Produção interna

Para uso contínuo:

```text
Cliente
   │
   ▼
Rede interna
   │
   ▼
Servidor Windows/Linux
   │
   ├── Waitress
   ├── Flask
   ├── SQLite
   ├── uploads
   └── scheduler
```

Recomenda-se:

- manter backups periódicos;
- proteger a máquina do servidor;
- restringir a porta no firewall;
- proteger o `.env`;
- monitorar logs;
- evitar `FLASK_DEBUG=true`;
- documentar alterações de schema;
- manter Python e dependências atualizados.

---

## Checklist de implantação

```text
[ ] Python instalado
[ ] Ambiente virtual criado
[ ] Dependências instaladas
[ ] .env criado
[ ] SECRET_KEY configurada
[ ] SMTP configurado
[ ] Banco inicializado
[ ] Pasta uploads criada
[ ] Pasta logs criada
[ ] Porta liberada no firewall
[ ] SERVER_HOST validado
[ ] SERVER_PORT validada
[ ] Primeiro usuário cadastrado
[ ] Teste de criação de pedido realizado
[ ] Teste de upload realizado
[ ] Teste de edição realizado
[ ] Teste de entrega realizado
[ ] Teste de e-mail realizado
[ ] Backup configurado
```

---

## Licença

Este repositório não apresenta, no pacote analisado, um arquivo `LICENSE` definindo uma licença de código aberto específica.

Caso o projeto seja publicado ou distribuído publicamente, recomenda-se definir explicitamente a licença de uso, alteração e redistribuição.

---

## Informações de versão

### 8.0.0

Principais componentes presentes nesta versão:

- dashboard operacional;
- cadastro e edição de pedidos;
- controle de entrega;
- lixeira e restauração;
- anexos;
- observações com histórico;
- controle de NF e CTE;
- valores do pedido, NF e frete;
- notificações automáticas;
- autenticação;
- bloqueio de tentativas de login;
- CSRF;
- rate limiting;
- SQLite com WAL;
- migrações automáticas;
- logs diários;
- execução com Waitress;
- organização por Blueprints e serviços.

---

## Autor

**Gabriel S. Justino**

Projeto: **Controle de Pedidos — CNP**
