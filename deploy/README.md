# Deploy na AWS (uma EC2 com Docker)

Tudo roda numa EC2 só, com `docker compose`:

| Container | O que é |
|---|---|
| `caddy` | Angular (build de produção) + proxy da API + HTTPS automático (Let's Encrypt) |
| `backend` | Django com gunicorn (migra e faz o `collectstatic` ao subir) |
| `db` | Postgres 16 (volume `postgres_data`) |
| `evolution-*` | Evolution API para o WhatsApp (opcional, `--profile whatsapp`) |

Um domínio só atende tudo:

- `https://SEU_DOMINIO/` → Angular
- `https://SEU_DOMINIO/api/` → API (é essa URL que vai no APK)
- `https://SEU_DOMINIO/admin/` → admin do Django

O app Android não roda na AWS. Ele é gerado apontando para `https://SEU_DOMINIO/api/` (seção 6).

## 1. Criar a EC2 (console da AWS)

1. **EC2 → Launch instance**
   - AMI: **Ubuntu Server 24.04 LTS**
   - Tipo: **t3.small** (2 GB de RAM, cerca de US$ 15/mês). Com a Evolution API ligada, considere a t3.medium.
   - Key pair: crie uma e guarde o `.pem`.
   - Storage: **20 GB gp3**.
   - Security group: libere **22 (SSH) só para o seu IP**, **80** e **443** para todo mundo (0.0.0.0/0).
2. **EC2 → Elastic IPs → Allocate** e associe o IP à instância, para ele não mudar quando a máquina reiniciar.
3. No DNS do seu domínio, crie um **registro A** `SEU_DOMINIO → IP elástico`.
   Espere propagar antes do passo 3: o Caddy só consegue emitir o certificado com o DNS apontando certo.

## 2. Preparar o servidor

```bash
ssh -i sua-chave.pem ubuntu@IP_ELASTICO
curl -fsSL https://raw.githubusercontent.com/zezinjr/Rota-certa-Backend-Django/main/deploy/setup-ec2.sh -o setup-ec2.sh
bash setup-ec2.sh
exit   # entre de novo para o grupo docker valer
```

O script instala o Docker, cria 2 GB de swap e clona os dois repositórios em `~/rotacerta/`
(o compose espera o Angular em `~/rotacerta/rota-certa-frontend-angular`).

## 3. Configurar e subir

```bash
cd ~/rotacerta/rota-certa-backend-django/deploy
cp .env.example .env
nano .env        # DOMAIN, SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, senha do Postgres, chaves
docker compose up -d --build
docker compose logs -f caddy backend
```

Gere a `SECRET_KEY` com `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.
A senha do Postgres aparece duas vezes no `.env` (`POSTGRES_PASSWORD` e `DATABASE_URL`) e precisa ser igual nas duas.

Primeiro acesso:

```bash
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py create_manager --company-id 1 --name "Fulano" --code 123 --phone 92999999999 --password "SenhaInicial"
```

## 4. Levar os dados do Postgres local (opcional)

No seu PC:

```bash
pg_dump -U postgres -h localhost route_monitoring --no-owner --no-acl > dump.sql
scp -i sua-chave.pem dump.sql ubuntu@IP_ELASTICO:~
```

Na EC2, com o compose já de pé (as migrações criam as tabelas vazias):

```bash
cd ~/rotacerta/rota-certa-backend-django/deploy
docker compose stop backend
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE \"$POSTGRES_DB\"" -c "CREATE DATABASE \"$POSTGRES_DB\""'
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < ~/dump.sql
docker compose start backend
```

## 5. WhatsApp pela Evolution API (opcional)

No `.env`: `WHATSAPP_PROVIDER=evolution` e uma `EVOLUTION_API_KEY` longa e aleatória. Depois:

```bash
docker compose --profile whatsapp up -d --build
# Sem tela no servidor: use o código de pareamento em vez do QR code
docker compose exec backend python manage.py conectar_whatsapp --numero +5592991234567
docker compose exec backend python manage.py testar_whatsapp
```

A Evolution API não fica exposta na internet; só o backend fala com ela, pela rede interna do Docker.
Com o perfil ligado, use `--profile whatsapp` em todos os `docker compose up`.

## 6. App Android (Kotlin)

O app fica no repositório [Rota-certa-Frontend-Kotlin](https://github.com/zezinjr/Rota-certa-Frontend-Kotlin)
e o APK precisa sair com a URL da API embutida. No GitHub desse repositório:
**Actions → Android APK → Run workflow** e preencha `api_base_url` com `https://SEU_DOMINIO/api/`.
O APK fica em *Artifacts* na página da execução.

Ou localmente, na raiz desse repositório:

```bash
./gradlew assembleDebug -PapiBaseUrl=https://SEU_DOMINIO/api/
```

Para distribuir, mande o APK direto (ou suba num bucket S3 com link público). Na Play Store
o app precisa de um build `release` assinado, que ainda não está configurado.

## 7. Atualizar depois de um push

```bash
cd ~/rotacerta/rota-certa-backend-django && git pull
cd ~/rotacerta/rota-certa-frontend-angular && git pull
cd ~/rotacerta/rota-certa-backend-django/deploy && docker compose up -d --build
```

## 8. Backup do banco

```bash
crontab -e
# adicione:
0 3 * * * bash ~/rotacerta/rota-certa-backend-django/deploy/backup.sh
```

O dump vai para `~/backups/` (guarda 14 dias). Ele fica no mesmo disco da EC2, então copie
para um S3 de vez em quando, ou ative os snapshots do volume EBS (EC2 → Lifecycle Manager).
