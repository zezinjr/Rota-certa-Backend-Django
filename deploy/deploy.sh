#!/usr/bin/env bash
# Atualiza a stack na EC2. Roda sozinho pelo CI/CD (.github/workflows/ci-cd.yml) a cada push
# na main, ou à mão:
#   bash deploy/deploy.sh                  # imagem "latest" do backend
#   bash deploy/deploy.sh sha-1a2b3c4      # uma versão específica (rollback)
#   FRONTEND=1 bash deploy/deploy.sh       # também atualiza e reconstrói o Angular
set -euo pipefail

# Tudo dentro de main: o git pull abaixo pode trocar este arquivo enquanto ele roda.
main() {
  cd "$(dirname "$0")"

  export BACKEND_TAG="${1:-latest}"

  # Com a Evolution API configurada, o perfil whatsapp precisa estar em todos os comandos.
  if grep -qE '^WHATSAPP_PROVIDER=evolution' .env 2>/dev/null; then
    export COMPOSE_PROFILES=whatsapp
  fi

  echo "==> Código do deploy (compose, Caddyfile, scripts)"
  git -C .. pull --ff-only

  mkdir -p secrets

  echo "==> Backend: ${BACKEND_IMAGE:-ghcr.io/zezinjr/rota-certa-backend-django}:${BACKEND_TAG}"
  docker compose pull backend

  if [ "${FRONTEND:-0}" = "1" ]; then
    echo "==> Frontend (Angular)"
    git -C "${FRONTEND_DIR:-../../rota-certa-frontend-angular}" pull --ff-only
    docker compose build caddy
  fi

  echo "==> Subindo"
  # Sem --build: o backend vem do GHCR; o Caddy só é construído se ainda não existir.
  docker compose up -d --remove-orphans

  # Guarda a versão no ar, para saber o que está rodando e para o rollback.
  echo "${BACKEND_TAG}" > .deployed-tag

  docker image prune -f > /dev/null
  docker compose ps
}

main "$@"
