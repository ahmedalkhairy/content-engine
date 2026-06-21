#!/usr/bin/env bash
# Wire a subdomain to Content Engine (nginx + Let's Encrypt on a shared VPS)
#
# Prerequisites:
#   - DNS A record: content.infrapilot.tech → this server's public IP
#   - Docker stack running: web on 127.0.0.1:8010 (APP_BIND=127.0.0.1 APP_PORT=8010)
#   - nginx installed on the host (ports 80/443 already used by other projects — OK)
#
# Usage (on the VPS as root):
#   cd ~/content-engine
#   sudo DOMAIN=content.infrapilot.tech APP_PORT=8010 CERTBOT_EMAIL=you@infrapilot.tech bash scripts/setup-domain.sh

set -euo pipefail

DOMAIN="${DOMAIN:-content.infrapilot.tech}"
APP_PORT="${APP_PORT:-8010}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
SITE_NAME="content-engine"
AVAILABLE="/etc/nginx/sites-available/${SITE_NAME}"
ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/setup-domain.sh"
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "nginx is not installed. Install it first: apt install nginx"
  exit 1
fi

echo "==> Domain: ${DOMAIN}"
echo "==> Upstream: 127.0.0.1:${APP_PORT}"

if ! curl -sf "http://127.0.0.1:${APP_PORT}/health" >/dev/null 2>&1; then
  echo "WARNING: http://127.0.0.1:${APP_PORT}/health is not reachable."
  echo "Start Docker first:"
  echo "  cd ~/content-engine && docker compose -f docker-compose.prod.yml up -d"
  echo ""
  read -r -p "Continue anyway? [y/N] " ans
  [[ "${ans,,}" == "y" ]] || exit 1
fi

cat > "${AVAILABLE}" <<EOF
# Content Engine — ${DOMAIN}
# Managed by scripts/setup-domain.sh

server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF

ln -sf "${AVAILABLE}" "${ENABLED}"
nginx -t
systemctl reload nginx

echo "==> HTTP proxy live: http://${DOMAIN}"

if command -v certbot >/dev/null 2>&1; then
  if [[ -z "${CERTBOT_EMAIL}" ]]; then
    echo ""
    echo "Set CERTBOT_EMAIL to obtain HTTPS automatically, e.g.:"
    echo "  sudo DOMAIN=${DOMAIN} CERTBOT_EMAIL=you@example.com bash scripts/setup-domain.sh"
    exit 0
  fi

  echo "==> Obtaining Let's Encrypt certificate..."
  certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --redirect
  systemctl reload nginx
  echo "==> HTTPS ready: https://${DOMAIN}"
else
  echo ""
  echo "Install certbot for HTTPS:"
  echo "  apt install certbot python3-certbot-nginx"
  echo "  sudo certbot --nginx -d ${DOMAIN}"
fi

echo ""
echo "Update .env on the server:"
echo "  DOMAIN=${DOMAIN}"
echo "  APP_PUBLIC_URL=https://${DOMAIN}"
echo "  SESSION_COOKIE_SECURE=true"
echo "  APP_BIND=127.0.0.1"
echo "  APP_PORT=${APP_PORT}"
echo ""
echo "Then restart:"
echo "  docker compose -f docker-compose.prod.yml up -d"
