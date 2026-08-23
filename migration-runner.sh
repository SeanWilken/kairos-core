#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if command -v node >/dev/null 2>&1; then
  RUNTIME=node
elif command -v bun >/dev/null 2>&1; then
  RUNTIME=bun
else
  echo "Node.js or Bun is required to run migrations." >&2
  exit 1
fi

exec "$RUNTIME" "$ROOT/scripts/migration-helper.mjs" "$@"
