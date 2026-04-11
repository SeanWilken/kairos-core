import type { CheckItem, CheckResult, GeneratedArtifact, WizardState } from "./types";

function setEnvValue(content: string, key: string, value: string): string {
  const line = `${key}=${value}`;
  const regex = new RegExp(`^${key}=.*$`, "m");
  if (regex.test(content)) return content.replace(regex, line);
  return `${content.trimEnd()}\n${line}\n`;
}

export function buildPreflightChecks(state: WizardState): CheckItem[] {
  const checks: CheckItem[] = [
    {
      name: "tenant_name_present",
      label: "Tenant name provided",
      required: true,
      status: state.tenant_name.trim() ? "pass" : "fail",
      message: state.tenant_name.trim() ? "Tenant name is set." : "Provide tenant name in Runtime step.",
    },
    {
      name: "connection_models_present",
      label: "Connection model refs",
      required: true,
      status: state.connections.length > 0 && state.connections.every((c) => c.model_ref.trim()) ? "pass" : "fail",
      message:
        state.connections.length > 0 && state.connections.every((c) => c.model_ref.trim())
          ? "All connections include model refs."
          : "Set model_ref for each connection.",
    },
    {
      name: "core_component_enabled",
      label: "Core API component",
      required: true,
      status: state.infra_components.includes("core_api") ? "pass" : "fail",
      message: state.infra_components.includes("core_api") ? "core_api selected." : "core_api is required.",
    },
  ];

  if (state.vector_store_mode === "enabled" && state.vector_provider === "pgvector") {
    const ok = state.infra_components.includes("postgres") && state.infra_components.includes("pgvector");
    checks.push({
      name: "pgvector_dependencies",
      label: "pgvector dependencies",
      required: true,
      status: ok ? "pass" : "fail",
      message: ok ? "postgres + pgvector selected." : "Enable postgres and pgvector in Deployment.",
    });
  }

  if (state.vector_store_mode === "enabled" && state.vector_provider === "pinecone") {
    checks.push({
      name: "pinecone_endpoint",
      label: "Pinecone endpoint configured",
      required: true,
      status: state.vector_endpoint.trim() ? "pass" : "fail",
      message: state.vector_endpoint.trim() ? "Pinecone endpoint set." : "Set Pinecone endpoint in Vector step.",
    });
  }

  checks.push({
    name: "secrets_mode_set",
    label: "Secrets strategy",
    required: true,
    status: state.secrets_mode ? "pass" : "fail",
    message: state.secrets_mode ? "Secrets strategy selected." : "Select secrets strategy.",
  });

  return checks;
}

export function buildRuntimeChecks(state: WizardState): CheckItem[] {
  const checks: CheckItem[] = [];

  if (state.infra_components.includes("core_api")) {
    checks.push({ name: "core_health_endpoint", label: "Core API health", required: true, status: "pending", message: "" });
  }
  if (state.infra_components.includes("postgres")) {
    checks.push({ name: "postgres_reachable", label: "PostgreSQL reachable", required: true, status: "pending", message: "" });
    checks.push({ name: "postgres_auth_valid", label: "PostgreSQL credentials", required: true, status: "pending", message: "" });
    checks.push({ name: "postgres_database_exists", label: "PostgreSQL database exists", required: true, status: "pending", message: "" });
  }
  if (state.infra_components.includes("pgvector")) {
    checks.push({ name: "pgvector_extension", label: "pgvector extension", required: true, status: "pending", message: "" });
    checks.push({ name: "pgvector_version_compatible", label: "pgvector version", required: true, status: "pending", message: "" });
    checks.push({ name: "migration_permissions", label: "DB migration permissions", required: true, status: "pending", message: "" });
  }
  if (state.connections.some((c) => c.mode === "api_provider")) {
    checks.push({ name: "provider_connectivity", label: "API provider connectivity", required: true, status: "pending", message: "" });
  }
  if (state.model_modes.includes("local_model")) {
    checks.push({ name: "local_model_endpoint", label: "Local model endpoint", required: true, status: "pending", message: "" });
  }

  return checks;
}

function buildScopeHeaders(state: WizardState): Record<string, string> {
  const slug = state.tenant_name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-") || "local";
  return {
    "X-Tenant-ID": `tenant-${slug}`,
    "X-Org-ID": `org-${slug}`,
  };
}

async function postJson(
  url: string,
  payload: unknown,
  headers: Record<string, string>
): Promise<{ ok: boolean; status: number; body?: unknown }> {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(payload),
  });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  return { ok: response.ok, status: response.status, body };
}

async function getWithQueryParams(
  url: string,
  params: Record<string, string>,
  headers: Record<string, string>
): Promise<{ ok: boolean; status: number; body?: unknown }> {
  const urlWithParams = new URL(url);
  Object.entries(params).forEach(([key, value]) => {
    urlWithParams.searchParams.set(key, value);
  });

  const response = await fetch(urlWithParams.toString(), { method: "GET", headers });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  return { ok: response.ok, status: response.status, body };
}

async function getJson(url: string, headers: Record<string, string>): Promise<{ ok: boolean; status: number; body?: unknown }> {
  const response = await fetch(url, { method: "GET", headers });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  return { ok: response.ok, status: response.status, body };
}

function parseApiError(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const root = body as { error?: { message?: string; details?: Record<string, unknown> } };
  const message = root.error?.message;
  const reason = root.error?.details?.reason_code;
  if (typeof message === "string" && typeof reason === "string") {
    return `${message} (${reason})`;
  }
  if (typeof message === "string") return message;
  return fallback;
}

export async function ensureBootstrapSession(state: WizardState): Promise<string> {
  const base = state.runtime_base_url.replace(/\/$/, "");
  const headers = buildScopeHeaders(state);

  if (state.bootstrap_session_id.trim()) {
    const existing = await getJson(`${base}/v1/bootstrap/sessions/${state.bootstrap_session_id}`, headers);
    if (existing.ok) return state.bootstrap_session_id;
  }

  const latest = await getWithQueryParams(`${base}/v1/bootstrap/sessions`, { latest: "true" }, headers);
  if (latest.ok && latest.body && typeof latest.body === "object") {
    const body = latest.body as { data?: { session_id?: string } | null };
    const latestId = body.data?.session_id;
    if (latestId) return latestId;
  }

  const payload = {
    runtime: {
      tenant_name: state.tenant_name || "local-tenant",
      tenant_type: state.tenant_type,
      model_modes: state.model_modes,
      connections: state.connections,
    },
    database: {
      connection_mode: "existing",
      deployment_location: "local",
      host: state.local_env_overrides.POSTGRES_HOST || "localhost",
      port: Number(state.local_env_overrides.POSTGRES_PORT || "5432"),
      database_name: state.local_env_overrides.POSTGRES_DB || "kairos",
      username: state.local_env_overrides.POSTGRES_USER || "kairos",
      requires_pgvector: state.infra_components.includes("pgvector"),
      password_ref: "POSTGRES_PASSWORD",
    },
    deployment: {
      target: state.deployment_target,
      execution_mode: state.execution_mode,
      infra_components: state.infra_components,
      frontend_services: state.frontend_services,
    },
    secrets: {
      mode: state.secrets_mode,
      storage_target: state.storage_target,
      required_key_names: state.required_keys,
    },
    vector: {
      mode: state.vector_store_mode,
      provider: state.vector_provider,
      namespace_pattern: state.namespace_pattern || "tenant_default",
      index_strategy: state.index_strategy,
      endpoint: state.vector_endpoint,
    },
  };

  const res = await postJson(`${base}/v1/bootstrap/sessions`, payload, headers);
  if (!res.ok || !res.body || typeof res.body !== "object") {
    throw new Error(parseApiError(res.body, "Failed to create bootstrap session."));
  }
  const body = res.body as { data?: { session_id?: string } };
  const sessionId = body.data?.session_id;
  if (!sessionId) throw new Error("Bootstrap session response missing session_id.");
  return sessionId;
}

export async function runRuntimeChecks(state: WizardState): Promise<{ results: CheckItem[]; sessionId: string }> {
  const checks = buildRuntimeChecks(state);
  const base = state.runtime_base_url.replace(/\/$/, "");
  const headers = buildScopeHeaders(state);
  const sessionId = await ensureBootstrapSession(state);

  let latestStatus: Array<{ check_id?: string; status?: string; message?: string; label?: string }> = [];
  const runRes = await postJson(`${base}/v1/system/checks/run`, { session_id: sessionId }, headers);
  if (runRes.ok && runRes.body && typeof runRes.body === "object") {
    const body = runRes.body as { data?: { checks?: Array<{ check_id?: string; status?: string; message?: string; label?: string }> } };
    latestStatus = body.data?.checks ?? [];
  } else if (runRes.status !== 404) {
    throw new Error(parseApiError(runRes.body, "Failed to run runtime checks."));
  }

  if (latestStatus.length === 0) {
    const statusRes = await getWithQueryParams(`${base}/v1/system/status`, { session_id: sessionId }, headers);
    if (statusRes.ok && statusRes.body && typeof statusRes.body === "object") {
      const body = statusRes.body as { data?: { checks?: Array<{ check_id?: string; status?: string; message?: string; label?: string }> } };
      latestStatus = body.data?.checks ?? [];
    } else {
      throw new Error(parseApiError(statusRes.body, "Failed to fetch runtime status."));
    }
  }

  const byCheckId = new Map<string, { status?: string; message?: string; label?: string }>();
  latestStatus.forEach((item) => {
    if (item.check_id) byCheckId.set(item.check_id, item);
  });

  const out: CheckItem[] = [];
  for (const check of checks) {
    const mapped = byCheckId.get(check.name);
    if (mapped) {
      out.push({
        ...check,
        status:
          mapped.status === "pass" || mapped.status === "fail" || mapped.status === "warn" || mapped.status === "pending"
            ? (mapped.status as CheckResult)
            : "warn",
        label: mapped.label || check.label,
        message: mapped.message || "Validated via runtime status endpoint.",
      });
      continue;
    }

    if (check.name === "local_model_endpoint") {
      const localConn = state.connections.find((c) => c.mode === "local_model");
      if (!localConn) {
        out.push({ ...check, status: "warn", message: "No local model connection configured." });
        continue;
      }
      try {
        const res = await fetch(`${localConn.endpoint.replace(/\/$/, "")}/api/tags`, { method: "GET" });
        out.push({ ...check, status: res.ok ? "pass" : "warn", message: res.ok ? "Local model endpoint reachable." : `Local endpoint returned HTTP ${res.status}.` });
      } catch {
        out.push({ ...check, status: "warn", message: "Could not reach local model endpoint." });
      }
      continue;
    }

    out.push({ ...check, status: "warn", message: "Manual verification required." });
  }

  return { results: out, sessionId };
}

export function buildArtifacts(state: WizardState): GeneratedArtifact[] {
  const primaryApiConn = state.connections.find((c) => c.mode === "api_provider") ?? null;
  const defaultStableImage = "ghcr.io/kairosstack/kairos-core-api:stable";
  const selectedCoreImage =
    state.core_api_runtime_mode === "custom_image"
      ? state.core_api_custom_image.trim() || "your-registry/your-core-api:tag"
      : defaultStableImage;

  let env = "# .env.template - generated by Kairos Core Setup\n# Do not commit real values to source control.\n\n";
  env += "# Core\nCORE_API_PORT=8000\nCORE_ENV=development\n\n";
  env += `# Container engine preference\nCONTAINER_ENGINE=${state.container_engine}\n\n`;
  env += `# Core runtime mode\nCORE_API_RUNTIME_MODE=${state.core_api_runtime_mode}\n`;
  env += `CORE_API_IMAGE=${selectedCoreImage}\n\n`;
  env += "# LLM + RAG routing\nLLM_PROVIDER=";
  env += `${primaryApiConn?.provider ?? "openai"}\n`;
  env += `LLM_ENDPOINT=${primaryApiConn?.endpoint ?? "https://api.openai.com/v1"}\n`;
  env += `LLM_MODEL=${primaryApiConn?.model_ref || "gpt-4o-mini"}\n`;
  env += "RAG_ENABLED=true\nRAG_TOP_K=6\nRAG_SCORE_THRESHOLD=0.2\n\n";

  const apiConns = state.connections.filter((c) => c.mode === "api_provider");
  if (apiConns.length) {
    env += "# Provider credentials\n";
    if (apiConns.some((c) => c.provider === "openai")) {
      env += "OPENAI_API_KEY=\nOPENAI_BASE_URL=https://api.openai.com/v1\n";
    }
    if (apiConns.some((c) => c.provider === "anthropic")) {
      env += "ANTHROPIC_API_KEY=\nANTHROPIC_BASE_URL=https://api.anthropic.com\n";
    }
    if (apiConns.some((c) => c.provider === "custom")) {
      env += "CUSTOM_API_KEY=\nCUSTOM_API_BASE_URL=\n";
    }
    env += "\n";
  }

  if (state.infra_components.includes("postgres")) {
    env += "# PostgreSQL / pgvector\nPOSTGRES_HOST=localhost\nPOSTGRES_PORT=5432\nPOSTGRES_DB=kairos\nPOSTGRES_USER=kairos\nPOSTGRES_PASSWORD=\nPOSTGRES_SSL_MODE=prefer\n\n";
  }

  let compose = "services:\n";
  const deps: string[] = [];
  if (state.infra_components.includes("postgres") || state.infra_components.includes("pgvector")) deps.push("postgres");
  if (state.infra_components.includes("local_model_runtime")) deps.push("ollama");

  if (state.infra_components.includes("core_api")) {
    if (state.core_api_runtime_mode === "local_source") {
      compose += "\n  # Core API built from local repository source.\n";
      compose += "  core_api:\n";
      compose += "    build:\n";
      compose += "      context: ../backend\n";
      compose += "      dockerfile: Dockerfile\n";
      compose += "    image: ${CORE_API_IMAGE}\n";
      compose += "    env_file: .env\n";
      compose += "    ports:\n";
      compose += "      - \"${CORE_API_PORT:-8000}:8000\"\n";
      compose += "    restart: unless-stopped\n";
      if (deps.length) {
        compose += `    depends_on:\n${deps.map((d) => `      - ${d}`).join("\n")}\n`;
      }
    } else {
      compose += "\n  core_api:\n";
      compose += "    image: ${CORE_API_IMAGE}\n";
      compose += "    env_file: .env\n";
      compose += "    ports:\n";
      compose += "      - \"${CORE_API_PORT:-8000}:8000\"\n";
      compose += "    restart: unless-stopped\n";
      if (deps.length) {
        compose += `    depends_on:\n${deps.map((d) => `      - ${d}`).join("\n")}\n`;
      }
    }
  }

  const frontendMap: Record<string, { image: string; port: string; containerName: string }> = {
    kros_core_frontend: {
      image: "kairos/core-frontend:local",
      port: "8080",
      containerName: "kros-core-frontend",
    },
    kros_studio_frontend: {
      image: "ghcr.io/kairosstack/kros-studio-frontend:stable",
      port: "8081",
      containerName: "kros-studio-frontend",
    },
    kros_council_frontend: {
      image: "ghcr.io/kairosstack/kros-council-frontend:stable",
      port: "8082",
      containerName: "kros-council-frontend",
    },
  };

  for (const serviceId of state.frontend_services) {
    const frontend = frontendMap[serviceId];
    if (!frontend) continue;
    compose += `\n  ${serviceId}:\n`;
    if (serviceId === "kros_core_frontend") {
      compose += "    build:\n";
      compose += "      context: ../frontend\n";
      compose += "      dockerfile: Dockerfile\n";
      compose += `    image: ${frontend.image}\n`;
    } else {
      compose += `    image: ${frontend.image}\n`;
    }
    compose += `    container_name: ${frontend.containerName}\n`;
    compose += "    environment:\n";
    compose += "      KAIROS_CORE_API_URL: http://localhost:${CORE_API_PORT:-8000}\n";
    compose += "    ports:\n";
    compose += `      - \"${frontend.port}:80\"\n`;
    compose += "    depends_on:\n";
    compose += "      - core_api\n";
    compose += "    restart: unless-stopped\n";
  }

  if (state.infra_components.includes("postgres") || state.infra_components.includes("pgvector")) {
    const img = state.infra_components.includes("pgvector") ? "pgvector/pgvector:pg16" : "postgres:16-alpine";
    compose += `\n  postgres:\n    image: ${img}\n    environment:\n      POSTGRES_DB: \${POSTGRES_DB}\n      POSTGRES_USER: \${POSTGRES_USER}\n      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n      - ./migrations/0001_initial_onboarding.sql:/docker-entrypoint-initdb.d/0001_initial_onboarding.sql:ro\n    ports:\n      - \"\${POSTGRES_PORT:-5432}:5432\"\n`;
  }

  if (state.infra_components.includes("local_model_runtime")) {
    compose += "\n  ollama:\n    image: ollama/ollama:latest\n    ports:\n      - \"11434:11434\"\n    volumes:\n      - ollama_data:/root/.ollama\n";
  }

  compose += "\nvolumes:\n";
  if (state.infra_components.includes("postgres") || state.infra_components.includes("pgvector")) compose += "  pgdata:\n";
  if (state.infra_components.includes("local_model_runtime")) compose += "  ollama_data:\n";

  const quickstart = `# Kairos Core Local Bootstrap

## Privacy disclosure
If you configure an external API provider (OpenAI or Anthropic), prompts and retrieved context sent to the provider are processed by that provider according to their policies. Do not route regulated or sensitive data unless your legal and compliance policy allows it.

## Folder structure
Recommended for repo-local development: place generated files in the repository root (or an infra subfolder) so scripts and docs align with the local backend workflow:

\`\`\`text
kairos-core/
  .env
  docker-compose.yml
  bootstrap-local.sh
  bootstrap-local.ps1
  check-runtime.sh
  check-runtime.ps1
  migrations/
    0001_initial_onboarding.sql
  bootstrap-report.json
  backend/
\`\`\`

## Script reference
- \`bootstrap-local.sh\` / \`bootstrap-local.ps1\`: starts local infrastructure containers using your selected engine (Docker or Podman).
- \`check-runtime.sh\` / \`check-runtime.ps1\`: checks Core health endpoint and prints runtime-status endpoint guidance.
- Initial DB schema is auto-applied on first postgres boot from \`migrations/0001_initial_onboarding.sql\`.

## Core runtime options
- local source mode: build and run Core from this repository backend Dockerfile.
- bundled stable image mode: run core_api via default stable image.
- custom image mode: run core_api via your image (you must already have CLI registry access).

## Setup steps
1. Copy \`.env.template\` to \`.env\` and set API/database secrets locally.
2. Start infrastructure:
   - Bash: \`./bootstrap-local.sh\`
   - PowerShell: \`.\\bootstrap-local.ps1\`
3. If using local source mode, compose builds \`core_api\` from \`../backend/Dockerfile\`.
4. On first postgres start, compose auto-applies \`migrations/0001_initial_onboarding.sql\` via \`/docker-entrypoint-initdb.d\`.
5. Run runtime checks:
   - Bash: \`./check-runtime.sh\`
   - PowerShell: \`.\\check-runtime.ps1\`
6. Continue to document ingest only after required checks pass.

## Compose note
- Generated compose always includes infrastructure dependencies (PostgreSQL/pgvector and optional local model runtime).
- In local source mode, core_api is built from local repository backend source.
- In bundled/custom image modes, core_api is active and uses CORE_API_IMAGE.
- Optional frontend services are included only when selected in the Frontends step and are wired to \`http://core_api:8000\`.

## Session resume
- Runtime checks and ingest use a bootstrap \`session_id\`.
- The UI will reuse the latest session in your tenant/org scope when available.
- CLI scripts use \`KAIROS_SESSION_ID\`; if unset, run from UI once to create a session and copy the id.
`;

  const bootstrapSh = `#!/usr/bin/env bash
set -euo pipefail

ENGINE="\${CONTAINER_ENGINE:-${state.container_engine}}"
CORE_MODE="\${CORE_API_RUNTIME_MODE:-${state.core_api_runtime_mode}}"

if [ ! -f .env ]; then
  echo "Missing .env. Copy .env.template to .env and fill values first."
  exit 1
fi

$ENGINE compose up -d

echo "Infrastructure started with $ENGINE compose."
if [ "$CORE_MODE" = "local_source" ]; then
  echo "Core API local-source mode active (built from ../backend/Dockerfile)."
else
  echo "Core API container mode active via CORE_API_IMAGE."
fi
`;

  const bootstrapPs1 = `$ErrorActionPreference = "Stop"

$engine = if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { "${state.container_engine}" }
$coreMode = if ($env:CORE_API_RUNTIME_MODE) { $env:CORE_API_RUNTIME_MODE } else { "${state.core_api_runtime_mode}" }

if (-not (Test-Path ".env")) {
  Write-Error "Missing .env. Copy .env.template to .env and fill values first."
}

& $engine compose up -d
Write-Host "Infrastructure started with $engine compose."
if ($coreMode -eq "local_source") {
  Write-Host "Core API local-source mode active (built from ../backend/Dockerfile)."
} else {
  Write-Host "Core API container mode active via CORE_API_IMAGE."
}
`;

  const checkRuntimeSh = `#!/usr/bin/env bash
set -euo pipefail

BASE_URL="\${CORE_BASE_URL:-http://localhost:8000}"
SESSION_ID="\${KAIROS_SESSION_ID:-}"

echo "Checking $BASE_URL/v1/health"
if ! curl -fsS "$BASE_URL/v1/health"; then
  echo
  echo "Core API health check failed. Ensure backend is running."
  exit 1
fi

echo
if [ -n "$SESSION_ID" ]; then
  echo "Checking $BASE_URL/v1/system/status?session_id=$SESSION_ID"
  curl -fsS "$BASE_URL/v1/system/status?session_id=$SESSION_ID"
  echo
else
  echo "Set KAIROS_SESSION_ID and re-run to query /v1/system/status."
  echo "Example: KAIROS_SESSION_ID=<session-uuid> ./check-runtime.sh"
fi
`;

  const checkRuntimePs1 = `$ErrorActionPreference = "Stop"
$baseUrl = if ($env:CORE_BASE_URL) { $env:CORE_BASE_URL } else { "http://localhost:8000" }
$sessionId = if ($env:KAIROS_SESSION_ID) { $env:KAIROS_SESSION_ID } else { "" }

Write-Host "Checking $baseUrl/v1/health"
Invoke-RestMethod -Uri "$baseUrl/v1/health" -Method Get

if ($sessionId) {
  Write-Host "Checking $baseUrl/v1/system/status?session_id=$sessionId"
  Invoke-RestMethod -Uri "$baseUrl/v1/system/status?session_id=$sessionId" -Method Get
} else {
  Write-Host "Set KAIROS_SESSION_ID and re-run to query /v1/system/status."
  Write-Host "Example: $env:KAIROS_SESSION_ID='<session-uuid>'; .\\check-runtime.ps1"
}
`;

  const initialMigrationSql = `-- 0001_initial_onboarding.sql
-- Initial schema for bootstrap sessions, runtime checks, and ingest jobs.

CREATE TABLE IF NOT EXISTS bootstrap_sessions (
  session_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  status TEXT NOT NULL,
  runtime_json JSONB NOT NULL,
  database_json JSONB NOT NULL,
  deployment_json JSONB NOT NULL,
  secrets_json JSONB NOT NULL,
  vector_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_check_runs (
  run_id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES bootstrap_sessions(session_id) ON DELETE CASCADE,
  checks_json JSONB NOT NULL,
  summary_json JSONB NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
  job_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES bootstrap_sessions(session_id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  source_files_json JSONB NOT NULL,
  chunking_profile TEXT NOT NULL,
  embedding_profile TEXT NOT NULL,
  result_json JSONB,
  error_json JSONB,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bootstrap_sessions_scope ON bootstrap_sessions (tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_runtime_check_runs_session ON runtime_check_runs (session_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_session ON ingest_jobs (session_id, created_at DESC);
`;

  const bundleManifest = (files: GeneratedArtifact[]) => {
    const entries = files.map((file) => ({ name: file.name, type: file.type, content: file.content }));
    return JSON.stringify(
      {
        schema: "kairos-bootstrap-bundle/v0.1",
        generated_at: new Date().toISOString(),
        files: entries,
      },
      null,
      2
    );
  };

  const report = JSON.stringify(
    {
      schema: "bootstrap-report/v0.1",
      generated_at: new Date().toISOString().split("T")[0],
      tenant: { name: state.tenant_name, type: state.tenant_type },
      runtime: {
        model_modes: state.model_modes,
        connections: state.connections.map((c) => ({ mode: c.mode, provider: c.provider, model_ref: c.model_ref })),
      },
      deployment: {
        target: state.deployment_target,
        container_engine: state.container_engine,
        core_api_runtime_mode: state.core_api_runtime_mode,
        core_api_image: selectedCoreImage,
        execution_mode: state.execution_mode,
        components: state.infra_components,
        frontend_services: state.frontend_services,
      },
      secrets: { mode: state.secrets_mode, storage_target: state.storage_target, keys: state.required_keys },
      vector_store: { mode: state.vector_store_mode, provider: state.vector_store_mode === "enabled" ? state.vector_provider : null },
      checks: {
        total: state.check_results.length,
        passed: state.check_results.filter((r) => r.status === "pass").length,
        warnings: state.check_results.filter((r) => r.status === "warn").length,
      },
    },
    null,
    2
  );

  const artifacts: GeneratedArtifact[] = [
    { name: "README-quickstart.md", type: "md", content: quickstart },
    { name: ".env.template", type: "env", content: env },
  ];

  if (state.materialize_local_env) {
    let populatedEnv = env;
    for (const [key, value] of Object.entries(state.local_env_overrides)) {
      populatedEnv = setEnvValue(populatedEnv, key, value.trim());
    }
    for (const key of state.required_keys) {
      const value = state.local_secret_values[key] ?? "";
      populatedEnv = setEnvValue(populatedEnv, key, value.trim());
    }
    artifacts.push({ name: ".env", type: "env", content: populatedEnv });
  }

  if (state.deployment_target === "docker_local") {
    artifacts.push({ name: "docker-compose.yml", type: "yaml", content: compose });
    artifacts.push({ name: "bootstrap-local.sh", type: "sh", content: bootstrapSh });
    artifacts.push({ name: "bootstrap-local.ps1", type: "ps1", content: bootstrapPs1 });
    artifacts.push({
      name: "migrations/0001_initial_onboarding.sql",
      type: "sql",
      content: initialMigrationSql,
    });
    artifacts.push({ name: "check-runtime.sh", type: "sh", content: checkRuntimeSh });
    artifacts.push({ name: "check-runtime.ps1", type: "ps1", content: checkRuntimePs1 });
    artifacts.push({ name: "bootstrap-bundle.json", type: "json", content: "" });
  }

  artifacts.push({ name: "bootstrap-report.json", type: "json", content: report });

  const bundleIndex = artifacts.findIndex((a) => a.name === "bootstrap-bundle.json");
  if (bundleIndex >= 0) {
    artifacts[bundleIndex] = {
      name: "bootstrap-bundle.json",
      type: "json",
      content: bundleManifest(artifacts.filter((a) => a.name !== "bootstrap-bundle.json")),
    };
  }

  if (state.deployment_target === "k8s") {
    artifacts.push({
      name: "k8s-manifests.yaml",
      type: "yaml",
      content: "# Experimental template\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: kairos-core-api\nspec:\n  replicas: 1\n",
    });
  }

  if (state.deployment_target === "terraform") {
    artifacts.push({
      name: "terraform.tfvars.example",
      type: "sh",
      content: `project_name = \"${state.tenant_name || "kairos-core"}\"\nenvironment = \"dev\"\n`,
    });
  }

  if (state.deployment_target === "github_actions") {
    artifacts.push({
      name: "github-actions-snippet.yml",
      type: "yaml",
      content: "name: kairos-core-bootstrap\non:\n  workflow_dispatch:\n",
    });
  }

  return artifacts;
}

export function applyCheckOutcome(
  results: CheckItem[],
  index: number,
  outcome: { status: CheckResult; message: string }
): { results: CheckItem[]; done: boolean } {
  const next = [...results];
  next[index] = { ...next[index], ...outcome };
  const done = next.every((r) => r.status !== "pending");
  return { results: next, done };
}
