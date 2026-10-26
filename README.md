# 🚍 Rota Certa — Backend

API REST para gerenciamento e monitoramento de transporte corporativo, desenvolvida com **Python, Django e Django REST Framework**.

O projeto foi desenvolvido com foco em organização de domínio, validação de regras de negócio, integridade dos dados e disponibilização de uma API REST escalável para gerenciamento de empresas, funcionários, motoristas, veículos, rotas, passageiros, pontos de encontro, horários e eventos de operação.

---

## 📋 Sumário

* [Sobre o projeto](#-sobre-o-projeto)
* [Principais funcionalidades](#-principais-funcionalidades)
* [Tecnologias utilizadas](#-tecnologias-utilizadas)
* [Arquitetura](#-arquitetura)
* [Modelo de domínio](#-modelo-de-domínio)
* [Regras de negócio](#-regras-de-negócio)
* [Estrutura do projeto](#-estrutura-do-projeto)
* [Pré-requisitos](#-pré-requisitos)
* [Instalação](#-instalação)
* [Configuração das variáveis de ambiente](#-configuração-das-variáveis-de-ambiente)
* [Executando o projeto](#-executando-o-projeto)
* [Banco de dados](#-banco-de-dados)
* [Autenticação](#-autenticação)
* [Documentação da API](#-documentação-da-api)
* [Endpoints](#-endpoints)
* [Exemplos de utilização](#-exemplos-de-utilização)
* [Validações](#-validações)
* [Testes](#-testes)
* [Boas práticas adotadas](#-boas-práticas-adotadas)
* [Próximos passos](#-próximos-passos)
* [Autor](#-autor)

---

## 🚀 Sobre o projeto

O **Rota Certa Backend** é uma API REST destinada ao gerenciamento de operações de transporte corporativo.

A aplicação centraliza informações relacionadas a:

* empresas;
* funcionários;
* motoristas;
* veículos;
* rotas;
* passageiros;
* eventos de percurso;
* pontos de encontro;
* endereços;
* horários de operação.

A API foi estruturada utilizando os princípios REST e possui regras de negócio implementadas principalmente na camada de serializers, garantindo que os dados recebidos pela API respeitem as regras do domínio.

---

## ✨ Principais funcionalidades

### 🏢 Empresas

Permite cadastrar e administrar empresas responsáveis pelas operações de transporte.

Operações disponíveis:

* criação;
* consulta;
* atualização;
* exclusão;
* ativação/desativação.

---

### 👤 Pessoas

O sistema utiliza uma entidade `Person` para representar diferentes tipos de pessoas relacionadas à operação.

Atualmente existem dois tipos:

```text
EMPLOYEE
DRIVER
```

A diferenciação é realizada por meio do campo:

```text
type
```

Essa abordagem evita a criação de tabelas separadas para funcionários e motoristas.

---

### 🚗 Motoristas

Permite cadastrar motoristas vinculados a uma empresa.

Motoristas possuem informações específicas, como:

* nome;
* telefone;
* número da CNH;
* empresa;
* status de atividade.

Somente pessoas classificadas como `DRIVER` podem ser associadas a veículos.

---

### 👨‍💼 Funcionários

Funcionários representam os passageiros que utilizam o transporte corporativo.

Cada funcionário pode possuir:

* nome;
* telefone;
* código funcional;
* empresa;
* status.

Somente pessoas classificadas como `EMPLOYEE` podem ser adicionadas como passageiros de uma rota.

---

### 🚐 Veículos

Permite cadastrar os veículos utilizados nas operações.

Informações principais:

* placa;
* modelo;
* ano;
* motorista responsável;
* empresa;
* status.

Existe uma validação de domínio garantindo que somente uma pessoa do tipo `DRIVER` possa ser associada como motorista.

---

### 🛣️ Rotas

Representa uma operação de transporte entre um ponto de origem e um destino.

Cada rota possui:

* empresa;
* nome;
* origem;
* destino;
* status;
* data de criação;
* data de atualização;
* status de atividade.

Os estados possíveis são:

```text
planned
in_progress
completed
cancelled
```

---

### 👥 Passageiros da rota

O relacionamento entre funcionários e rotas é representado por `RoutePassenger`.

Isso permite associar diferentes funcionários a uma determinada rota.

Regra principal:

> Somente pessoas do tipo `EMPLOYEE` podem ser adicionadas como passageiros.

---

### 📍 Eventos de rota

Os eventos permitem registrar acontecimentos durante a operação de uma rota.

Tipos disponíveis:

```text
delay
incident
stop
departure
arrival
```

Os eventos também podem armazenar informações de geolocalização:

```text
latitude
longitude
```

Isso possibilita registrar onde determinado evento ocorreu.

---

### 📌 Pontos de encontro

Os pontos de encontro são representados por `MeetingPoint`.

Um ponto de encontro associa:

```text
Route → Address
```

permitindo definir locais onde os passageiros podem embarcar ou desembarcar.

---

### 🕐 Horários

A entidade `Schedule` permite definir os horários planejados de uma rota.

São armazenados:

* horário planejado de início;
* horário planejado de término;
* rota relacionada.

---

# 🧩 Tecnologias utilizadas

| Tecnologia            | Utilização                              |
| --------------------- | --------------------------------------- |
| Python                | Linguagem principal                     |
| Django                | Framework web                           |
| Django REST Framework | Construção da API REST                  |
| PostgreSQL            | Banco de dados relacional               |
| JWT                   | Autenticação                            |
| Swagger / OpenAPI     | Documentação da API                     |
| Django ORM            | Persistência e relacionamento dos dados |
| Unit Tests            | Testes automatizados                    |

---

# 🏗️ Arquitetura

A aplicação utiliza uma arquitetura baseada no ecossistema Django e Django REST Framework.

De forma simplificada:

```text
                    ┌─────────────────────┐
                    │     Cliente/API     │
                    │ Web / Mobile / App  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Django REST     │
                    │      Framework      │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
        Serializers         Views             URLs
             │                 │
             └────────┬────────┘
                      ▼
                Django Models
                      │
                      ▼
                Django ORM
                      │
                      ▼
                PostgreSQL
```

A camada de serializers possui papel importante na aplicação, pois além de serializar e desserializar os dados, também concentra diversas regras de negócio.

---

# 🧠 Modelo de domínio

## Company

Representa uma empresa.

```text
Company
├── id
├── name
├── created_at
├── updated_at
└── is_active
```

---

## Person

Representa funcionários e motoristas.

```text
Person
├── id
├── company
├── name
├── phone
├── type
├── employee_code
├── license_number
├── created_at
├── updated_at
└── is_active
```

Tipos:

```text
EMPLOYEE
DRIVER
```

---

## Vehicle

Representa um veículo pertencente à operação.

```text
Vehicle
├── id
├── company
├── plate_number
├── model
├── year
├── driver
├── created_at
├── updated_at
└── is_active
```

---

## Route

Representa uma rota de transporte.

```text
Route
├── id
├── company
├── name
├── origin
├── destination
├── status
├── created_at
├── updated_at
└── is_active
```

---

## RoutePassenger

Relaciona funcionários às rotas.

```text
RoutePassenger
├── id
├── route
└── person
```

---

## RouteEvent

Registra acontecimentos durante uma rota.

```text
RouteEvent
├── id
├── route
├── event_type
├── latitude
├── longitude
├── description
├── created_at
└── updated_at
```

---

## Address

Representa um endereço.

```text
Address
├── id
├── street
├── city
├── state
├── zip_code
├── created_at
└── updated_at
```

---

## MeetingPoint

Relaciona um endereço a uma rota.

```text
MeetingPoint
├── id
├── route
├── address
├── created_at
└── updated_at
```

---

## Schedule

Representa o horário planejado da rota.

```text
Schedule
├── id
├── route
├── planned_start_time
├── planned_end_time
├── created_at
└── updated_at
```

---

# 🧬 Estratégia TPH — Person

Uma das decisões arquiteturais do projeto é a utilização da estratégia **Single Table / TPH (Table Per Hierarchy)**.

Em vez de possuir:

```text
Employee
Driver
```

como tabelas independentes, ambas as representações utilizam a mesma tabela:

```text
Person
```

A diferenciação ocorre através de:

```python
type
```

Exemplo:

```text
Person
────────────────────────────
id
name
phone
type
employee_code
license_number
```

Onde:

```text
EMPLOYEE
    → employee_code obrigatório
    → license_number não permitido

DRIVER
    → license_number obrigatório
    → employee_code não permitido
```

### Vantagens

Essa abordagem proporciona:

* modelo de dados mais simples;
* redução de duplicidade;
* relacionamento centralizado;
* manutenção facilitada;
* possibilidade de expansão para novos tipos de pessoa;
* regras de domínio centralizadas.

---

# 📜 Regras de negócio

## Pessoa

Uma pessoa deve possuir obrigatoriamente um tipo.

### Funcionário

```text
type = EMPLOYEE
```

Requer:

```text
employee_code
```

Não permite:

```text
license_number
```

---

### Motorista

```text
type = DRIVER
```

Requer:

```text
license_number
```

Não permite:

```text
employee_code
```

---

## Veículo

Um veículo só pode possuir como motorista uma pessoa cujo tipo seja:

```text
DRIVER
```

---

## Passageiro

Uma pessoa somente pode ser adicionada como passageiro quando:

```text
type = EMPLOYEE
```

---

## Eventos

A latitude deve respeitar:

```text
-90 ≤ latitude ≤ 90
```

A longitude deve respeitar:

```text
-180 ≤ longitude ≤ 180
```

Para eventos críticos, a descrição é obrigatória.

Eventos críticos:

```text
delay
incident
```

---

# 🗂️ Estrutura do projeto

Estrutura principal do repositório:

```text
Rota-certa-Backend-Django/
│
├── config/
│   └── Configurações do projeto Django
│
├── core/
│   └── Aplicação principal e domínio
│
├── docs/
│   └── Documentação adicional
│
├── .env.example
├── .gitignore
├── PT-README.md
├── README.md
├── core_data.json
├── data.json
├── main.py
├── manage.py
└── requirements.txt
```

---

# ⚙️ Pré-requisitos

Antes de executar o projeto, certifique-se de possuir:

* Python 3.10 ou superior;
* PostgreSQL;
* Git;
* pip;
* ambiente virtual Python.

Opcionalmente:

* Postman;
* Insomnia;
* Docker;
* DBeaver ou pgAdmin.

---

# 📥 Instalação

Clone o repositório:

```bash
git clone https://github.com/RaybrendoT/Rota-certa-Backend-Django.git
```

Entre no diretório:

```bash
cd Rota-certa-Backend-Django
```

---

## 🐍 Criando o ambiente virtual

### Windows

```powershell
python -m venv .venv
```

Ative:

```powershell
.venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv .venv
```

Ative:

```bash
source .venv/bin/activate
```

---

# 📦 Instalando dependências

Com o ambiente virtual ativado:

```bash
pip install -r requirements.txt
```

---

# 🔐 Configuração das variáveis de ambiente

O projeto disponibiliza um arquivo:

```text
.env.example
```

Faça uma cópia para:

```text
.env
```

Exemplo:

```env
DEBUG=True

SECRET_KEY=sua-chave-secreta

DATABASE_NAME=rota_certa
DATABASE_USER=postgres
DATABASE_PASSWORD=sua-senha
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

> Os nomes exatos das variáveis devem acompanhar a configuração presente no projeto. Nunca versione credenciais reais, senhas ou chaves privadas no Git.

---

# 🗄️ Configuração do banco de dados

Crie o banco PostgreSQL utilizado pela aplicação.

Depois execute as migrações:

```bash
python manage.py makemigrations
```

```bash
python manage.py migrate
```

---

# 👤 Criando um superusuário

Para acessar o Django Admin:

```bash
python manage.py createsuperuser
```

Informe:

```text
Username:
Email:
Password:
```

---

# ▶️ Executando o projeto

Inicie o servidor:

```bash
python manage.py runserver
```

Por padrão, a aplicação estará disponível em:

```text
http://127.0.0.1:8000/
```

---

# 📚 Documentação da API

O projeto utiliza **Swagger/OpenAPI** para facilitar o desenvolvimento e testes da API.

A documentação pode ser disponibilizada através das rotas configuradas no projeto.

Exemplo:

```text
http://127.0.0.1:8000/swagger/
```

Caso a rota tenha sido configurada com outro caminho, consulte:

```text
config/urls.py
```

A documentação permite visualizar:

* endpoints;
* métodos HTTP;
* parâmetros;
* payloads;
* respostas;
* códigos HTTP;
* modelos utilizados pela API.

---

# 🔑 Autenticação JWT

A API utiliza autenticação baseada em **JSON Web Token (JWT)**.

O fluxo esperado é:

```text
Login
  │
  ▼
Access Token + Refresh Token
  │
  ▼
Requisições autenticadas
  │
  ▼
API
```

Nas requisições protegidas, o token deve ser enviado no header:

```http
Authorization: Bearer <access_token>
```

## Quem pode acessar o quê

**Toda a API exige login.** Sem token, a resposta é `401`. O perfil da pessoa logada define o acesso:

| Perfil (`Person.type`) | Acesso |
|---|---|
| `MANAGER` (gestor, painel web) | Todos os endpoints de cadastro (empresas, pessoas, veículos, rotas, horários, eventos...) |
| `DRIVER` (motorista) | `routes/my-routes/`, `routes/{id}/driver-detail/`, `routes/{id}/navigation/`; eventos (`route-events`: listar e criar) e passageiros (`route-passengers`: listar e alterar só o `boarding_status`), **apenas das próprias rotas** |
| `EMPLOYEE` (colaborador) | Apenas `/api/me/...` (perfil, viagens e confirmação de embarque) |

Os endpoints `/api/auth/` (login, refresh, verify e recuperação de senha) continuam públicos. Outros acessos retornam `403`.

### Gestores

O gestor é uma `Person` do tipo `MANAGER`, com `employee_code`. A conta de acesso é criada automaticamente, com e-mail `codigo@dominio-da-empresa`.

- **Primeiro gestor** de um banco novo:
  ```bash
  python manage.py create_manager --company-id 1 --name "Maria Gestora" --code GST001 --phone "+5592999990000" --password "SenhaInicial@1"
  ```
  O gestor troca a senha no primeiro acesso.
- Depois disso, novos gestores podem ser cadastrados por um gestor via `POST /api/people/` com `"type": "MANAGER"`.
- O seed `seed_manaus_demo` cria um gestor por empresa (`gst001@polodigitalmanaus.com` ... `gst005@pontanegraservicos.com`).

---

# 🔌 Endpoints

## Empresas

```http
GET    /companies/
POST   /companies/
GET    /companies/{id}/
PUT    /companies/{id}/
DELETE /companies/{id}/
```

---

## Funcionários

```http
GET    /employees/
POST   /employees/
GET    /employees/{id}/
PUT    /employees/{id}/
DELETE /employees/{id}/
```

---

## Motoristas

```http
GET    /drivers/
POST   /drivers/
GET    /drivers/{id}/
PUT    /drivers/{id}/
DELETE /drivers/{id}/
```

---

## Veículos

```http
GET    /vehicles/
POST   /vehicles/
GET    /vehicles/{id}/
PUT    /vehicles/{id}/
DELETE /vehicles/{id}/
```

---

## Rotas

```http
GET    /routes/
POST   /routes/
GET    /routes/{id}/
PUT    /routes/{id}/
DELETE /routes/{id}/
```

---

## Passageiros

```http
GET    /route-passengers/
POST   /route-passengers/
DELETE /route-passengers/{id}/
```

---

## Eventos

```http
GET  /route-events/
POST /route-events/
```

---

## Pontos de encontro

```http
GET  /meeting-points/
POST /meeting-points/
```

---

## Horários

```http
GET  /schedules/
POST /schedules/
```

---

## App do colaborador (`/api/me/`)

Endpoints consumidos pelo app Android dos colaboradores. Exigem `Authorization: Bearer <access_token>` de uma pessoa do tipo `EMPLOYEE` (motoristas recebem 403).

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/me/` | Perfil do colaborador logado (matrícula, e-mail, empresa, endereço) |
| GET | `/api/me/trips/` | Rotas em que o colaborador é passageiro: status da rota, veículo, motorista, meu ponto, paradas, destino, horários e últimos eventos |
| GET | `/api/me/trips/{id}/` | Detalhe de uma viagem (id do `RoutePassenger`) |
| POST | `/api/me/trips/{id}/boarding/` | Confirma ou informa ausência: `{"status": "confirmed" \| "absent" \| "pending"}` |

O colaborador só enxerga e altera os próprios registros (404 para os de outras pessoas).

## Acompanhamento ao vivo da van

| Método | Endpoint | Quem | Descrição |
|---|---|---|---|
| POST | `/api/routes/{id}/location/` | Motorista (só as próprias rotas) | Envia o GPS: `{"latitude", "longitude", "heading"?, "speed"? (m/s), "recorded_at"?}` a cada 3–5 s durante a rota |
| GET | `/api/me/trips/{id}/live/` | Colaborador (só as próprias viagens) | Posição da van, `is_live`, `phase` (`waiting`, `approaching`, `arriving`, `passed`, `at_destination`), `eta` (`minutes`, `distance_meters`, `stops_before`), `next_stop_sequence` e `path_progress` |

- A última posição de cada veículo fica em `VehicleLocation`. Posições com mais de 2 min deixam de contar como "ao vivo".
- A previsão é calculada pela distância ao longo das paradas até o ponto do colaborador, usando a velocidade média (25 km/h, ou a velocidade informada pela van quando maior) mais 1 min por parada antes da sua. Não usa API paga.
- Os parâmetros ficam em `config/settings.py` (`LIVE_*`). Esses dois endpoints têm limite próprio de requisições (`driver_location` e `trip_live`), separado do limite geral.

### Trajeto pelas ruas (Google Routes API)

Com uma chave de servidor do Google configurada, o trajeto de cada rota ("parada 1 → … → empresa") segue as ruas. Isso vale para o mapa do app, a previsão de chegada (distância pelas ruas), o progresso da van e o simulador. Sem chave, tudo continua em linha reta entre as paradas.

1. No Google Cloud Console, ative a **Routes API** e crie uma chave restrita a ela. Em "Restrições do aplicativo", use **Nenhum** em desenvolvimento ou **Endereços IP** com o IP do servidor. Não use "Apps Android": essa chave é usada pelo backend, não pelo app.
2. No `.env` (nunca no `.env.example`): `GOOGLE_MAPS_API_KEY=sua-chave-de-servidor`
3. Opcional, para calcular tudo de uma vez: `python manage.py calcular_trajetos`

O trajeto é guardado em `Route.road_path`, junto com uma assinatura das coordenadas das paradas. A API só é chamada de novo quando as paradas mudam, por isso o uso fica muito abaixo da cota gratuita. Em caso de erro, a rota usa a linha reta e a API só é tentada de novo depois de 10 min. Para desligar, use `ROAD_PATH_ENABLED=False`.

### Simulador (sem o app do motorista)

```bash
# Faz a van da rota do colaborador percorrer todas as paradas em ~5 minutos
python manage.py simular_rota --email mne001@polodigitalmanaus.com

# Outras opções: --route-id 3 · --minutos 10 · --speed-kmh 30 (ritmo real) · --loop · --start-meters 2000
```

O simulador grava a posição a cada 3 s, registra os eventos de saída e chegada, e para com Ctrl+C. Rode em um terminal separado, com o `runserver` aberto, e acompanhe no app.

## Teste com um motorista de verdade (página de rastreamento)

A página **`/rastreamento/`** é servida pelo próprio backend. O motorista entra com a conta dele, escolhe a rota e toca em **Iniciar rota**. A partir daí, o navegador do celular envia o GPS a cada 5 s e mantém a tela ligada. **Encerrar rota** registra a chegada e para o envio. Não precisa instalar nada.

### 1. Crie uma rota no trajeto que o motorista vai fazer

Pegue as coordenadas de 2 a 5 pontos do trajeto no Google Maps: um toque longo no mapa mostra algo como `-3.0956, -60.0343`.

```bash
python manage.py criar_rota_teste \
  --motorista mnd002@amazonialogistica.com \
  --colaborador mne002@amazonialogistica.com \
  --pontos "-3.0956, -60.0343; -3.0609, -60.0259; -3.0745, -60.0065" \
  --ponto-colaborador 3 \
  --destino "-3.1300, -59.9670" \
  --nome "Teste com motorista" --exclusivo
```

- `--motorista`: conta de motorista (`mndXXX@...`). A rota usa o veículo dele.
- `--colaborador`: conta que vai acompanhar pelo app.
- `--ponto-colaborador`: em qual parada o colaborador embarca.
- `--destino`: ponto final (opcional).
- `--exclusivo`: o app passa a mostrar só esta viagem.

### 2. Deixe o backend acessível pela internet (HTTPS)

O celular do motorista precisa alcançar o seu computador, e o navegador só libera o GPS em páginas `https`. Use um túnel. Com o `runserver 0.0.0.0:8000` rodando, em outro terminal:

```bash
# Cloudflare (sem cadastro) — Windows: winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8000
# ou ngrok (precisa de conta gratuita): ngrok http 8000
```

O comando mostra um endereço como `https://algo-aleatorio.trycloudflare.com`. Com `DEBUG=True` no `.env`, o Django aceita esse endereço.

### 3. No dia do teste

1. **Motorista**, antes de sair: abre `https://<endereço-do-túnel>/rastreamento/` no Chrome do celular, entra, escolhe a rota, aceita o compartilhamento, toca em **Iniciar rota** e permite a localização. Depois deixa o celular no suporte, com a página aberta, **sem mexer nele dirigindo**.
2. **Colaborador**, no app: abre a tela Viagem e toca em **Acompanhar no mapa**.
   - No emulador, o app continua usando `http://10.0.2.2:8000/api/`.
   - Num celular fora da sua rede, use a engrenagem da tela de login com `https://<endereço-do-túnel>/api/`.
3. No fim, o motorista toca em **Encerrar rota**.

**Privacidade:** a posição só é enviada com o rastreamento ligado e só aparece para os passageiros daquela rota. Combine o teste com o motorista antes. O túnel expõe o seu backend local enquanto estiver aberto, então feche-o (Ctrl+C) ao terminar.

## Avisos pelo WhatsApp

O colaborador recebe no WhatsApp:

| Aviso | Quando | Modelo na Meta |
|---|---|---|
| A van está a poucos minutos | previsão de chegada ao ponto ≤ `WHATSAPP_APPROACHING_MINUTES` (10) | `rota_van_a_caminho` |
| A van está chegando | van a menos de 300 m do ponto | `rota_van_chegando` |
| A van saiu (desligado por padrão) | motorista toca em **Iniciar rota** | `rota_van_saiu` |

Regras:
- Só recebe quem **ativou os avisos no app** (Perfil → Avisos → WhatsApp), com consentimento registrado em `whatsapp_opt_in_at`. O gestor não consegue ativar pelo painel.
- Cada aviso sai **no máximo uma vez por dia** por passageiro (tabela `Notification`), mesmo com o GPS chegando a cada 5 s.
- Quem marcou "não vou hoje" não recebe.
- Escolha quais avisos enviar em `WHATSAPP_EVENTS`.
- O simulador (`simular_rota`) também dispara os avisos, então dá para testar sem motorista.

Há dois jeitos de enviar, escolhidos em `WHATSAPP_PROVIDER` no `.env`:

| | `meta` (padrão) | `evolution` |
|---|---|---|
| O que é | API oficial do WhatsApp (Meta WhatsApp Cloud API) | [Evolution API](https://github.com/EvolutionAPI/evolution-api), de código aberto, rodando no seu Docker |
| Número que envia | número de teste da Meta ou número próprio da empresa | qualquer número de WhatsApp, conectado por QR code (como o WhatsApp Web) |
| Mensagens | modelos aprovados pela Meta | texto livre (o mesmo dos modelos) |
| Custo | por mensagem | gratuito |
| Risco | nenhum | **não é oficial**: o WhatsApp pode bloquear o número |

Sem as credenciais do provedor escolhido, nada é enviado.

### Opção A: Evolution API (mais rápido para testar)

**Use um número secundário** (um chip só para isso), nunca o seu WhatsApp pessoal: conexões não oficiais violam os termos de uso do WhatsApp, que pode banir o número, principalmente se ele mandar muitas mensagens para quem não o tem salvo. Para produção, prefira a Meta.

1. Instale o [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. No `.env` do backend, crie uma senha qualquer para a Evolution e escolha o provedor:
   ```
   WHATSAPP_PROVIDER=evolution
   EVOLUTION_API_URL=http://localhost:8080
   EVOLUTION_API_KEY=uma-senha-longa-que-voce-inventar
   EVOLUTION_INSTANCE=rotacerta
   ```
3. Suba a Evolution API (na pasta do backend):
   ```bash
   docker compose -f docker/evolution/docker-compose.yml --env-file .env up -d
   ```
4. Conecte o número que vai enviar os avisos:
   ```bash
   python manage.py conectar_whatsapp
   ```
   O comando salva `whatsapp_qrcode.png` na pasta do backend. Abra a imagem e, no celular desse número, vá em **WhatsApp → Aparelhos conectados → Conectar um aparelho** e escaneie. O QR code expira em cerca de 1 minuto; se expirar, rode o comando de novo. Com `--numero +5592...`, ele também gera um código para digitar em "Conectar com número de telefone".
5. Teste o envio para o seu número:
   ```bash
   python manage.py testar_whatsapp --telefone +5592991234567
   ```

Para desligar: `docker compose -f docker/evolution/docker-compose.yml down`. A conexão do número fica salva e volta ao subir de novo.

### Opção B: Meta (oficial)

#### 1. Crie o app na Meta (número de teste gratuito)

1. Em <https://developers.facebook.com/apps>, crie um app do tipo **Empresa** e adicione o produto **WhatsApp**.
2. Em **WhatsApp → Configuração da API**, a Meta fornece um **número de teste**. Anote o **Identificador do número de telefone** e gere o **Token de acesso temporário** (vale 24 h).
3. Na mesma tela, em **Para**, cadastre o seu número de WhatsApp (até 5 números no modo de teste) e confirme o código recebido.
4. No `.env` do backend:
   ```
   WHATSAPP_PROVIDER=meta
   WHATSAPP_TOKEN=token-da-meta
   WHATSAPP_PHONE_NUMBER_ID=identificador-do-numero
   ```
5. Teste com o modelo `hello_world`, que já vem aprovado:
   ```bash
   python manage.py testar_whatsapp --telefone +5592991234567
   ```

#### 2. Crie os modelos de mensagem

No **WhatsApp Manager → Modelos de mensagem → Criar modelo**, categoria **Utilidade**, idioma **Português (BR)**. Os nomes e as variáveis precisam ser exatamente estes (a ordem das variáveis importa):

| Nome | Texto |
|---|---|
| `rota_van_a_caminho` | `Olá, {{1}}! A van da {{2}} chega ao seu ponto ({{3}}) em cerca de {{4}} minutos.` |
| `rota_van_chegando` | `Olá, {{1}}! A van da {{2}} está chegando ao seu ponto ({{3}}). Prepare-se para embarcar.` |
| `rota_van_saiu` | `Olá, {{1}}! A van da {{2}} saiu e já está a caminho. Acompanhe a localização pelo app Rota Certa.` |

Variáveis: `{{1}}` primeiro nome do colaborador, `{{2}}` nome da rota, `{{3}}` nome do ponto de embarque, `{{4}}` minutos. A aprovação costuma levar minutos. Para conferir um modelo:

```bash
python manage.py testar_whatsapp --email mne007@amazonialogistica.com \
  --modelo rota_van_chegando --idioma pt_BR --parametros Ana "Rota 02" "Ponto Centro"
```

### Teste com o simulador (as duas opções)

1. No app, entre como o colaborador e ative **Avisos → WhatsApp** no Perfil. O telefone do cadastro dele precisa ser o número que vai receber (na Meta, um dos números cadastrados em **Para**). Altere pelo painel ou:
   ```bash
   python manage.py shell -c "from core.models import AccessAccount as A; p=A.objects.get(email='mne007@amazonialogistica.com').person; p.phone='+5592991234567'; p.save()"
   ```
2. Rode `python manage.py simular_rota --email <email do colaborador> --minutos 5`.
3. O WhatsApp recebe "a poucos minutos" e, depois, "chegando". Envios com erro ficam na tabela `core_notification` com o motivo em `error`.
4. Cada aviso sai uma vez por dia. Para repetir o teste no mesmo dia:
   ```bash
   python manage.py shell -c "from core.models import Notification; Notification.objects.all().delete()"
   ```

### Produção (Meta)

- O token temporário expira em 24 h. Gere um **token permanente** em **Configurações do negócio → Usuários do sistema**, com a permissão `whatsapp_business_messaging`.
- Troque o número de teste por um número próprio da empresa (sem WhatsApp instalado nele).
- O token é secreto: fica só no `.env` do servidor.

# 🧪 Exemplos de utilização

## Criando um funcionário

Exemplo conceitual:

```json
{
    "name": "João da Silva",
    "phone": "92999999999",
    "type": "EMPLOYEE",
    "employee_code": "EMP001"
}
```

---

## Criando um motorista

```json
{
    "name": "Carlos Oliveira",
    "phone": "92988888888",
    "type": "DRIVER",
    "license_number": "12345678900"
}
```

---

## Criando uma rota

```json
{
    "name": "Rota Centro",
    "origin": "Distrito Industrial",
    "destination": "Centro",
    "status": "planned"
}
```

---

## Registrando um evento

```json
{
    "route": "UUID_DA_ROTA",
    "event_type": "delay",
    "latitude": -3.119,
    "longitude": -60.021,
    "description": "Atraso causado pelo trânsito."
}
```

---

# 🛡️ Validações

A aplicação possui múltiplas camadas de proteção da integridade dos dados.

Entre elas:

```text
Model validation
      ↓
full_clean()
      ↓
Serializer validation
      ↓
Business rules
      ↓
Database
```

São utilizadas estratégias como:

* `validate()`;
* `validate_<field>()`;
* `full_clean()`;
* validações nos serializers;
* constraints e relacionamentos do banco;
* validação de tipos;
* validação geográfica.

---

# 🧪 Testes

O projeto possui estrutura voltada para testes de:

* models;
* serializers;
* endpoints;
* regras de negócio.

Para executar os testes:

```bash
python manage.py test
```

Ou, caso sejam utilizados testes específicos:

```bash
python manage.py test core
```

## Integração contínua (GitHub Actions)

O workflow [`.github/workflows/tests.yml`](.github/workflows/tests.yml) roda a cada push na `main`
e em todo pull request (também pode ser disparado manualmente em **Actions → Testes do backend → Run workflow**):

1. `python manage.py check` — configuração do Django;
2. `python manage.py makemigrations --check --dry-run` — falha se um model mudou sem migração;
3. `python manage.py test` — testes automatizados;
4. `migrate` + `seed_manaus_demo` — garante que o seed de demonstração continua funcionando.

O CI usa SQLite e não precisa de `.env`.

---

# 🔍 Testando com Postman

Uma forma simples de testar a API é utilizando o Postman.

Fluxo recomendado:

```text
1. Autenticar
      ↓
2. Obter access_token
      ↓
3. Configurar Authorization
      ↓
4. Criar empresa
      ↓
5. Criar funcionário
      ↓
6. Criar motorista
      ↓
7. Criar veículo
      ↓
8. Criar rota
      ↓
9. Adicionar passageiros
      ↓
10. Registrar eventos
```

---

# 🧹 Comandos úteis

Executar servidor:

```bash
python manage.py runserver
```

Criar migrações:

```bash
python manage.py makemigrations
```

Aplicar migrações:

```bash
python manage.py migrate
```

Criar superusuário:

```bash
python manage.py createsuperuser
```

Abrir shell Django:

```bash
python manage.py shell
```

Executar testes:

```bash
python manage.py test
```

Verificar problemas do projeto:

```bash
python manage.py check
```

---

# 📊 Fluxo geral da aplicação

```text
                    EMPRESA
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
      FUNCIONÁRIOS  MOTORISTAS   VEÍCULOS
          │            │
          │            └──────┐
          │                   │
          ▼                   ▼
     PASSAGEIROS           MOTORISTA
          │                   │
          └────────┐   ┌──────┘
                   ▼   ▼
                    ROTA
                     │
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
      HORÁRIOS   PONTOS      EVENTOS
                 ENCONTRO
                     │
                     ▼
                 ENDEREÇO
```

---

# 🎯 Objetivos técnicos

O projeto foi estruturado buscando demonstrar conhecimentos em:

* desenvolvimento de APIs REST;
* Django;
* Django REST Framework;
* modelagem relacional;
* PostgreSQL;
* autenticação JWT;
* serializers;
* validação de regras de negócio;
* relacionamentos entre entidades;
* tratamento de dados geográficos;
* testes automatizados;
* documentação de APIs;
* organização de projetos Python.

---

# 🔮 Próximos passos

Algumas evoluções que podem ser incorporadas futuramente:

* [ ] Paginação dos endpoints;
* [ ] Filtros avançados;
* [ ] Ordenação;
* [ ] Busca textual;
* [ ] Controle de permissões por perfil;
* [ ] Histórico de alterações;
* [ ] Logs de auditoria;
* [ ] Rastreamento em tempo real;
* [ ] Integração com mapas;
* [ ] WebSockets;
* [ ] Redis;
* [ ] Celery para tarefas assíncronas;
* [ ] Docker;
* [ ] CI/CD com GitHub Actions;
* [ ] Testes de integração;
* [ ] Cobertura de testes;
* [ ] Deploy em ambiente cloud.

---

# 🔒 Segurança

Algumas recomendações para utilização em produção:

* não versionar o arquivo `.env`;
* utilizar `DEBUG=False`;
* utilizar uma `SECRET_KEY` segura;
* configurar corretamente `ALLOWED_HOSTS`;
* utilizar HTTPS;
* proteger endpoints com autenticação;
* configurar permissões adequadas;
* utilizar banco de dados com credenciais próprias;
* evitar exposição de informações sensíveis nos logs.

---

# 📌 Status do projeto

**Em desenvolvimento 🚧**

O backend possui a estrutura principal da API e as entidades fundamentais para gerenciamento de transporte corporativo.

Novas funcionalidades e melhorias podem ser adicionadas conforme a evolução do sistema.

---

# 👨‍💻 Autor

Desenvolvido por **Raybrendo Trindade** e **Jose Eduardo**.

GitHub:

https://github.com/RaybrendoT
https://github.com/zezinjr

Repositório:

https://github.com/RaybrendoT/Rota-certa-Backend-Django

---

## 📄 Licença

Este projeto é destinado a fins educacionais, acadêmicos e de desenvolvimento de software.

Consulte o repositório para informações adicionais sobre a licença e utilização do código.
