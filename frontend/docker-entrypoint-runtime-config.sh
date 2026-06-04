#!/bin/sh
set -eu

TENANT_ID="${MYAI_TENANT_ID:-${INSTALL_TENANT_ID:-tenant-local}}"
CORE_API_BASE_URL="${MYAI_CORE_API_BASE_URL:-${MYAI_CORE_API_URL:-http://localhost:8000}}"
DE_API_BASE_URL="${MYAI_DE_API_BASE_URL:-http://localhost:8010}"
APP_ID="${MYAI_APP_ID:-core}"

cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.__MYAI_CONFIG__ = {
  tenantId: "${TENANT_ID}",
  coreApiBaseUrl: "${CORE_API_BASE_URL}",
  deApiBaseUrl: "${DE_API_BASE_URL}",
  appId: "${APP_ID}",
};
EOF
