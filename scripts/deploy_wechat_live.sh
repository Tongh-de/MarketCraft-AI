#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${MARKETCRAFT_PROJECT_DIR:-/opt/marketcraft-ai}"
COMPOSE_FILES=(-f docker-compose.demo.yml -f docker-compose.wechat.yml)

if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "Project directory not found: ${PROJECT_DIR}" >&2
  exit 1
fi

cd "${PROJECT_DIR}"

read -r -p "微信公众号 AppID: " WECHAT_APP_ID_INPUT
read -r -s -p "微信公众号 AppSecret（输入不会显示）: " WECHAT_APP_SECRET_INPUT
echo

if [[ ! "${WECHAT_APP_ID_INPUT}" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "AppID format is invalid." >&2
  exit 1
fi
if [[ ! "${WECHAT_APP_SECRET_INPUT}" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "AppSecret format is invalid." >&2
  exit 1
fi

touch .env
chmod 600 .env

upsert_env() {
  local key="$1"
  local value="$2"
  local temporary
  temporary="$(mktemp)"
  awk -v key="${key}" -v value="${value}" '
    BEGIN { replaced = 0 }
    index($0, key "=") == 1 {
      if (!replaced) print key "=" value
      replaced = 1
      next
    }
    { print }
    END { if (!replaced) print key "=" value }
  ' .env > "${temporary}"
  install -m 600 "${temporary}" .env
  rm -f "${temporary}"
}

upsert_env WECHAT_MODE live
upsert_env WECHAT_APP_ID "${WECHAT_APP_ID_INPUT}"
upsert_env WECHAT_APP_SECRET "${WECHAT_APP_SECRET_INPUT}"
upsert_env WECHAT_API_BASE https://api.weixin.qq.com
upsert_env WECHAT_TIMEOUT_SECONDS 20

unset WECHAT_APP_ID_INPUT WECHAT_APP_SECRET_INPUT

git pull --ff-only origin main
docker compose "${COMPOSE_FILES[@]}" up -d --build --force-recreate

echo
echo "Container status:"
docker compose "${COMPOSE_FILES[@]}" ps

echo
echo "Application health:"
curl --fail --silent --show-error http://127.0.0.1/health
echo

echo "WeChat configuration (secrets are never returned):"
curl --fail --silent --show-error http://127.0.0.1/api/v1/wechat/configuration
echo

echo "WeChat live connectivity:"
curl --fail --silent --show-error \
  --request POST \
  http://127.0.0.1/api/v1/wechat/health
echo

echo "Live WeChat deployment completed."
