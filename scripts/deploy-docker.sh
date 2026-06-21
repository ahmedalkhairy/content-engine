#!/usr/bin/env bash
# First-time production deploy on Ubuntu/Debian VPS
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/infra-content-engine}"
COMPOSE_FILE="docker-compose.prod.yml"

echo "==> Content Engine — Docker deploy"

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose plugin required."
  exit 1
fi

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found in $APP_DIR"
  echo "Copy .env.example to .env and configure DOMAIN, APP_SECRET_KEY, API keys."
  exit 1
fi

if ! grep -q '^DOMAIN=' .env || grep -q '^DOMAIN=$' .env || grep -q 'DOMAIN=localhost' .env; then
  echo "WARNING: Set DOMAIN=your-domain.com in .env for HTTPS"
fi

mkdir -p storage/images storage/logs

echo "==> Building and starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "==> Waiting for web health..."
sleep 5
docker compose -f "$COMPOSE_FILE" ps

if ! docker compose -f "$COMPOSE_FILE" exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" 2>/dev/null; then
  echo "Web health check failed — see: docker compose -f $COMPOSE_FILE logs web"
  exit 1
fi

echo ""
echo "Deploy complete."
echo "  Dashboard: https://\$(grep ^DOMAIN= .env | cut -d= -f2)  (or http://SERVER_IP if DOMAIN not set)"
echo ""
echo "First-time setup (if not done yet):"
echo "  docker compose -f $COMPOSE_FILE exec web python -m app create-admin --email YOU@example.com --password YOURPASS"
echo "  docker compose -f $COMPOSE_FILE exec web python -m app seed"
echo ""
echo "Logs:"
echo "  docker compose -f $COMPOSE_FILE logs -f web worker"
