import type { CheckItem, CheckResult, GeneratedArtifact, WizardState } from "./types";
import {
  CoreApiError,
  bootstrapApi,
  createCoreApiClient,
  systemApi,
  type ApiScope,
  type RuntimeCheck,
} from "../../../lib/api";

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

function buildApiScope(state: WizardState): ApiScope {
  const slug = state.tenant_name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-") || "local";
  return {
    tenantId: `tenant-${slug}`,
    orgId: `org-${slug}`,
  };
}

export async function ensureBootstrapSession(state: WizardState): Promise<string> {
  const client = createCoreApiClient({
    baseUrl: state.runtime_base_url,
    scope: buildApiScope(state),
  });

  if (state.bootstrap_session_id.trim()) {
    try {
      await bootstrapApi.getSession(client, state.bootstrap_session_id);
      return state.bootstrap_session_id;
    } catch (error) {
      if (!(error instanceof CoreApiError) || error.status !== 404) {
        throw error;
      }
    }
  }

  const latest = await bootstrapApi.listSessions(client, { latest: true });
  if (latest && !Array.isArray(latest)) {
    const latestId = latest.session_id;
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
      database_name: state.local_env_overrides.POSTGRES_DB || "myai",
      username: state.local_env_overrides.POSTGRES_USER || "myai",
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

  const createdSession = await bootstrapApi.createSession(client, payload);
  const sessionId = createdSession.session_id;
  if (!sessionId) throw new Error("Bootstrap session response missing session_id.");
  return sessionId;
}

function mapRuntimeChecksFromApi(checks: RuntimeCheck[]): Array<{ check_id?: string; status?: string; message?: string; label?: string }> {
  return checks.map((check) => ({
    check_id: check.check_id,
    status: check.status,
    message: check.message,
    label: check.label,
  }));
}

export async function runRuntimeChecks(state: WizardState): Promise<{ results: CheckItem[]; sessionId: string }> {
  const checks = buildRuntimeChecks(state);
  const client = createCoreApiClient({
    baseUrl: state.runtime_base_url,
    scope: buildApiScope(state),
  });
  const sessionId = await ensureBootstrapSession(state);

  let latestStatus: Array<{ check_id?: string; status?: string; message?: string; label?: string }> = [];
  try {
    const runStatus = await systemApi.runChecks(client, { session_id: sessionId });
    latestStatus = mapRuntimeChecksFromApi(runStatus.checks ?? []);
  } catch (error) {
    if (!(error instanceof CoreApiError) || error.status !== 404) {
      throw error;
    }
  }

  if (latestStatus.length === 0) {
    const status = await systemApi.getStatus(client, sessionId);
    latestStatus = mapRuntimeChecksFromApi(status.checks ?? []);
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
  const defaultStableImage = "myaitech/core-api:stable";
  const selectedCoreImage =
    state.core_api_runtime_mode === "custom_image"
      ? state.core_api_custom_image.trim() || "your-registry/your-core-api:tag"
      : defaultStableImage;
  const tenantSlug = state.tenant_name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const installTenantId = tenantSlug ? `tenant-${tenantSlug}` : "tenant-local";

  let env = "# .env.template - generated by MyAI Core Setup\n# Do not commit real values to source control.\n\n";
  env += "# Core\nCORE_API_PORT=8000\nCORE_ENV=development\n\n";
  env += `# Container engine preference\nCONTAINER_ENGINE=${state.container_engine}\n\n`;
  env += `# Core runtime mode\nCORE_API_RUNTIME_MODE=${state.core_api_runtime_mode}\n`;
  env += `CORE_API_IMAGE=${selectedCoreImage}\n\n`;
  if (state.infra_components.includes("myai_de_api")) {
    env += "# Optional myAIDE server\n";
    env += "MYAI_DE_API_IMAGE=myaitech/aide-api:local\n";
    env += "MYAI_DE_API_PORT=8010\n\n";
    env += "MYAIDE_AUTH_MODE=core\n";
    env += "CORE_BASE_URL=http://core_api:8000\n";
    env += `CORE_TENANT_ID=${installTenantId}\n\n`;
  }
  if (state.frontend_services.length) {
    env += "# Frontend images\n";
    if (state.frontend_services.includes("myai_core_frontend")) {
      env += "CORE_FRONTEND_IMAGE=myaitech/core-frontend:local\n";
      env += "CORE_FRONTEND_PORT=8080\n";
    }
    if (state.frontend_services.includes("myai_studio_frontend")) {
      env += "STUDIO_FRONTEND_IMAGE=myaitech/studio:local\n";
      env += "STUDIO_FRONTEND_PORT=8081\n";
    }
    if (state.frontend_services.includes("myai_council_frontend")) {
      env += "COUNCIL_FRONTEND_IMAGE=myaitech/council:local\n";
      env += "COUNCIL_FRONTEND_PORT=8082\n";
    }
    if (state.frontend_services.includes("myai_de_frontend")) {
      env += "MYAI_DE_FRONTEND_IMAGE=myaitech/aide-frontend:local\n";
      env += "MYAI_DE_FRONTEND_PORT=8083\n";
    }
    if (state.frontend_services.includes("myai_knowledger_frontend")) {
      env += "MYAI_KNOWLEDGER_FRONTEND_IMAGE=myaitech/knowledger:local\n";
      env += "MYAI_KNOWLEDGER_FRONTEND_PORT=8084\n";
    }
    env += "\n";
  }
  env += "# Install tenancy\n";
  env += "SINGLE_TENANT_MODE=true\n";
  env += `INSTALL_TENANT_ID=${installTenantId}\n\n`;
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
    if (apiConns.some((c) => c.provider === "google")) {
      env += "GEMINI_API_KEY=\nGEMINI_API_ENDPOINT=https://generativelanguage.googleapis.com/v1beta\nGEMINI_MODEL=gemini-2.5-flash\n";
    }
    if (apiConns.some((c) => c.provider === "custom")) {
      env += "CUSTOM_API_KEY=\nCUSTOM_API_BASE_URL=\n";
    }
    env += "\n";
  }

  if (state.infra_components.includes("postgres")) {
    env += "# PostgreSQL / pgvector\nPOSTGRES_HOST=localhost\nPOSTGRES_PORT=5432\nPOSTGRES_DB=myai\nPOSTGRES_USER=myai\nPOSTGRES_PASSWORD=\nPOSTGRES_SSL_MODE=prefer\n";
    env += "MYAI_DATABASE_URL=postgresql+psycopg://myai:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}\n\n";
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
      compose += "      context: ./backend\n";
      compose += "      dockerfile: Dockerfile\n";
      compose += "    image: ${CORE_API_IMAGE}\n";
      compose += "    env_file: .env\n";
      compose += "    profiles: [\"core\", \"suite\", \"de\", \"knowledger\", \"all\"]\n";
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
      compose += "    profiles: [\"core\", \"suite\", \"de\", \"knowledger\", \"all\"]\n";
      compose += "    ports:\n";
      compose += "      - \"${CORE_API_PORT:-8000}:8000\"\n";
      compose += "    restart: unless-stopped\n";
      if (deps.length) {
        compose += `    depends_on:\n${deps.map((d) => `      - ${d}`).join("\n")}\n`;
      }
    }
  }

  if (state.infra_components.includes("myai_de_api")) {
    compose += "\n  myai_de_api:\n";
    compose += "    image: ${MYAI_DE_API_IMAGE:-myaitech/aide-api:stable}\n";
    compose += "    env_file: .env\n";
    compose += "    environment:\n";
    compose += "      MYAIDE_AUTH_MODE: ${MYAIDE_AUTH_MODE:-core}\n";
    compose += "      CORE_BASE_URL: ${CORE_BASE_URL:-http://core_api:8000}\n";
    compose += "      CORE_TENANT_ID: ${CORE_TENANT_ID:-${INSTALL_TENANT_ID:-tenant-local}}\n";
    compose += "    profiles: [\"de\", \"all\"]\n";
    compose += "    ports:\n";
    compose += "      - \"${MYAI_DE_API_PORT:-8010}:8000\"\n";
    compose += "    restart: unless-stopped\n";
    const myAideDeps = ["core_api", ...deps.filter((dependency) => dependency !== "core_api")];
    if (myAideDeps.length) {
      compose += `    depends_on:\n${myAideDeps.map((d) => `      - ${d}`).join("\n")}\n`;
    }
  }

  const frontendMap: Record<string, { image: string; port: string; containerName: string; apiUrl: string; dependsOn: string }> = {
    myai_core_frontend: {
      image: "${CORE_FRONTEND_IMAGE:-myaitech/core-frontend:local}",
      port: "${CORE_FRONTEND_PORT:-8080}",
      containerName: "myai-core-frontend",
      apiUrl: "http://localhost:${CORE_API_PORT:-8000}",
      dependsOn: "core_api",
    },
    myai_studio_frontend: {
      image: "${STUDIO_FRONTEND_IMAGE:-myaitech/studio:local}",
      port: "${STUDIO_FRONTEND_PORT:-8081}",
      containerName: "myai-studio-frontend",
      apiUrl: "http://localhost:${CORE_API_PORT:-8000}",
      dependsOn: "core_api",
    },
    myai_council_frontend: {
      image: "${COUNCIL_FRONTEND_IMAGE:-myaitech/council:local}",
      port: "${COUNCIL_FRONTEND_PORT:-8082}",
      containerName: "myai-council-frontend",
      apiUrl: "http://localhost:${CORE_API_PORT:-8000}",
      dependsOn: "core_api",
    },
    myai_de_frontend: {
      image: "${MYAI_DE_FRONTEND_IMAGE:-myaitech/aide-frontend:local}",
      port: "${MYAI_DE_FRONTEND_PORT:-8083}",
      containerName: "myai-de-frontend",
      apiUrl: "http://localhost:${MYAI_DE_API_PORT:-8010}",
      dependsOn: "myai_de_api",
    },
    myai_knowledger_frontend: {
      image: "${MYAI_KNOWLEDGER_FRONTEND_IMAGE:-myaitech/knowledger:local}",
      port: "${MYAI_KNOWLEDGER_FRONTEND_PORT:-8084}",
      containerName: "myai-knowledger-frontend",
      apiUrl: "http://localhost:${CORE_API_PORT:-8000}",
      dependsOn: "core_api",
    },
  };

  for (const serviceId of state.frontend_services) {
    const frontend = frontendMap[serviceId];
    if (!frontend) continue;
    const resolvedDependency = frontend.dependsOn === "myai_de_api" && !state.infra_components.includes("myai_de_api")
      ? "core_api"
      : frontend.dependsOn;
    const resolvedApiUrl = frontend.dependsOn === "myai_de_api" && !state.infra_components.includes("myai_de_api")
      ? "http://localhost:${CORE_API_PORT:-8000}"
      : frontend.apiUrl;
    compose += `\n  ${serviceId}:\n`;
    if (serviceId === "myai_core_frontend") {
      compose += "    build:\n";
      compose += "      context: ./frontend\n";
      compose += "      dockerfile: Dockerfile\n";
      compose += `    image: ${frontend.image}\n`;
    } else {
      compose += `    image: ${frontend.image}\n`;
    }
    compose += `    container_name: ${frontend.containerName}\n`;
    if (serviceId === "myai_core_frontend") compose += "    profiles: [\"core\", \"all\"]\n";
    if (serviceId === "myai_studio_frontend" || serviceId === "myai_council_frontend") compose += "    profiles: [\"suite\", \"all\"]\n";
    if (serviceId === "myai_de_frontend") compose += "    profiles: [\"de\", \"all\"]\n";
    if (serviceId === "myai_knowledger_frontend") compose += "    profiles: [\"knowledger\", \"all\"]\n";
    compose += "    environment:\n";
    compose += `      MYAI_CORE_API_URL: ${resolvedApiUrl}\n`;
    compose += `      MYAI_CORE_API_BASE_URL: ${resolvedApiUrl}\n`;
    compose += "      MYAI_TENANT_ID: ${INSTALL_TENANT_ID:-tenant-local}\n";
    compose += `      MYAI_APP_ID: ${serviceId}\n`;
    if (serviceId === "myai_de_frontend") {
      compose += "      MYAI_DE_API_BASE_URL: ${MYAI_DE_API_BASE_URL:-}\n";
      compose += "      MYAI_DE_API_UPSTREAM: http://myai_de_api:8000\n";
    } else {
      compose += "      MYAI_DE_API_BASE_URL: http://localhost:${MYAI_DE_API_PORT:-8010}\n";
    }
    compose += "    ports:\n";
    compose += `      - \"${frontend.port}:80\"\n`;
    compose += "    depends_on:\n";
    compose += `      - ${resolvedDependency}\n`;
    compose += "    restart: unless-stopped\n";
  }

  if (state.infra_components.includes("postgres") || state.infra_components.includes("pgvector")) {
    const img = state.infra_components.includes("pgvector") ? "pgvector/pgvector:pg16" : "postgres:16-alpine";
    compose += `\n  postgres:\n    image: ${img}\n    profiles: ["core", "suite", "de", "knowledger", "all"]\n    environment:\n      POSTGRES_DB: \${POSTGRES_DB}\n      POSTGRES_USER: \${POSTGRES_USER}\n      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n    ports:\n      - \"\${POSTGRES_PORT:-5432}:5432\"\n`;
  }

  if (state.infra_components.includes("local_model_runtime")) {
    compose += "\n  ollama:\n    image: ollama/ollama:latest\n    profiles: [\"core\", \"suite\", \"de\", \"knowledger\", \"all\"]\n    ports:\n      - \"11434:11434\"\n    volumes:\n      - ollama_data:/root/.ollama\n";
  }

  compose += "\nvolumes:\n";
  if (state.infra_components.includes("postgres") || state.infra_components.includes("pgvector")) compose += "  pgdata:\n";
  if (state.infra_components.includes("local_model_runtime")) compose += "  ollama_data:\n";

  const quickstart = `# MyAI Core Local Bootstrap

## Privacy disclosure
If you configure an external API provider (OpenAI or Anthropic), prompts and retrieved context sent to the provider are processed by that provider according to their policies. Do not route regulated or sensitive data unless your legal and compliance policy allows it.

## Folder structure
Recommended for repo-local development: place generated files in the repository root (or an infra subfolder) so scripts and docs align with the local backend workflow:

\`\`\`text
myai-core/
  .env
  docker-compose.yml
  bootstrap-local.sh
  bootstrap-local.ps1
  check-runtime.sh
  check-runtime.ps1
  migrate-db.sh
  migrate-db.ps1
  migrations/
    0001_initial_onboarding.sql
    0002_studio_identity_foundation.sql
  bootstrap-report.json
  backend/
\`\`\`

## Script reference
- \`bootstrap-local.sh\` / \`bootstrap-local.ps1\`: starts local infrastructure containers using your selected engine (Docker or Podman).
- \`deploy.sh\` / \`deploy.ps1\`: non-destructive deployment refresh and versioned migration apply (preserves database volumes).
- \`refresh-images.sh\` / \`refresh-images.ps1\`: pulls images, recreates matching services, and applies pending versioned migrations.
- \`migrate-db.sh\` / \`migrate-db.ps1\`: runs Grate apply, status, dry-run, or one-time legacy baseline operations.
- \`check-runtime.sh\` / \`check-runtime.ps1\`: checks Core health endpoint and prints runtime-status endpoint guidance.
- SQL files in \`migrations/\` are applied through the Grate version ledger after PostgreSQL starts.
- If you rebuild \`:local\` images during development, make sure \`CONTAINER_ENGINE\` matches the engine where those images were built (for example \`docker\` on Windows if you built with Docker Desktop).
- \`../scripts/multi-repo-workflow.sh\` / \`../scripts/multi-repo-workflow.ps1\`: orchestrates building, refreshing, deploying, resetting, and publishing across mapped sibling repos.

## Core runtime options
- local source mode: build and run Core from this repository backend Dockerfile.
- bundled stable image mode: run core_api via default stable image.
- custom image mode: run core_api via your image (you must already have CLI registry access).

## Setup steps
1. Copy \`.env.template\` to \`.env\` and set API/database secrets locally.
2. Start infrastructure:
   - Bash: \`./bootstrap-local.sh --profile-set all\`
   - PowerShell: \`.\\bootstrap-local.ps1 -ProfileSet all\`
   - Refresh images before restart: add \`--refresh\` or \`-Refresh\`
3. If using local source mode, compose builds \`core_api\` from \`./backend/Dockerfile\`.
4. After PostgreSQL starts, the bootstrap script applies pending Grate migrations from repo-root \`migrations/\`.
5. Run runtime checks:
   - Bash: \`./check-runtime.sh\`
   - PowerShell: \`.\\check-runtime.ps1\`
6. Continue to document ingest only after required checks pass.

## Updating local images during development

### Multi-repo helper (recommended from \`kairos-core/\`)

- List mapped repos:
  - \`bash ./scripts/multi-repo-workflow.sh --action list\`
  - \`.\\scripts\\multi-repo-workflow.ps1 -Action list\`
- Build all mapped repos:
  - \`bash ./scripts/multi-repo-workflow.sh --action build --targets all --engine podman\`
  - \`.\\scripts\\multi-repo-workflow.ps1 -Action build -Targets all -Engine podman\`
- Refresh all mapped repos into the suite:
  - \`bash ./scripts/multi-repo-workflow.sh --action refresh --targets all --engine podman\`
  - \`.\\scripts\\multi-repo-workflow.ps1 -Action refresh -Targets all -Engine podman\`
- Deploy while preserving volumes:
  - \`bash ./scripts/multi-repo-workflow.sh --action deploy --targets all --engine podman\`
  - \`.\\scripts\\multi-repo-workflow.ps1 -Action deploy -Targets all -Engine podman\`
- Destroy data volumes and start clean:
  - \`bash ./scripts/multi-repo-workflow.sh --action reset-data --targets all --engine podman\`
  - \`.\\scripts\\multi-repo-workflow.ps1 -Action reset-data -Targets all -Engine podman\`

### Refresh a rebuilt local image into the running stack

- Council frontend:
  - \`.\\refresh-images.ps1 -ImagesCsv "myaitech/council:local" -ProfileSet suite\`
- Studio frontend:
  - \`.\\refresh-images.ps1 -ImagesCsv "myaitech/studio:local" -ProfileSet suite\`
- Core frontend:
  - \`.\\refresh-images.ps1 -ImagesCsv "myaitech/core-frontend:local" -ProfileSet core\`

### Build sibling frontend repos (not included in this repo)

- From \`../kairos-council\`:
  - \`podman build -t myaitech/council:local .\`
- From \`../kairos-studio\`:
  - \`podman build -t myaitech/studio:local .\`

### Build included repos/components from this repository

- From repo root for Core API:
  - \`podman build -t myaitech/core-api:local ./backend\`
- From repo root for Core frontend:
  - \`podman build -t myaitech/core-frontend:local ./frontend\`

### Preserve data while updating

- Preferred:
  - \`.\\deploy.ps1 -ProfileSet all\`
- Or rebuild/recreate only targeted services with the refresh script.

### Destroy volumes and reset local state completely

Run from \`myai-suite/\`:

\`\`\`powershell
podman compose --profile all down -v
\`\`\`

Then start fresh again with:

\`\`\`powershell
.\\deploy.ps1 -ProfileSet all
\`\`\`

This removes Postgres and other named volume data.

## Deploy workflow (preserve data)
- Deploy everything and keep existing Postgres data: \`./deploy.sh all\`
- Deploy + pull latest images first: \`./deploy.sh all true\`
- PowerShell equivalents:
  - \`.\\deploy.ps1 -ProfileSet all\`
  - \`.\\deploy.ps1 -ProfileSet all -RefreshImages\`
- This flow does not remove volumes and applies only pending Grate migrations from \`../migrations\`.

## Compose note
- Generated compose always includes infrastructure dependencies (PostgreSQL/pgvector and optional local model runtime).
- In local source mode, core_api is built from local repository backend source.
- In bundled/custom image modes, core_api is active and uses CORE_API_IMAGE.
- Optional frontend services are included only when selected in the Frontends step.
- Profile sets: \`core\`, \`suite\`, \`de\`, \`knowledger\`, or \`all\`.
- \`myai_de_frontend\` uses \`myai_de_api\` when that service is enabled, otherwise it falls back to \`core_api\`.
- \`all\` covers the release baseline: Core, Studio, Council, MyAIDE API/frontend, and KnowLedger.
- The standalone \`knowledger\` profile remains available for targeted refresh/deploy operations.

## Session resume
- Runtime checks and ingest use a bootstrap \`session_id\`.
- The UI will reuse the latest session in your tenant/org scope when available.
- CLI scripts use \`MYAI_SESSION_ID\`; if unset, run from UI once to create a session and copy the id.
`;

const bootstrapSh = `#!/usr/bin/env bash
set -euo pipefail

ENGINE="\${CONTAINER_ENGINE:-${state.container_engine}}"
CORE_MODE="\${CORE_API_RUNTIME_MODE:-${state.core_api_runtime_mode}}"
PROFILE_SET="all"
REFRESH=0
APPLY_MIGRATIONS=true

while [ $# -gt 0 ]; do
  case "$1" in
    --profile-set)
      PROFILE_SET="\${2:-all}"
      shift 2
      ;;
    --refresh)
      REFRESH=1
      shift
      ;;
    --skip-migrations)
      APPLY_MIGRATIONS=false
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: ./bootstrap-local.sh [--profile-set core|suite|de|knowledger|all] [--refresh] [--skip-migrations]"
      exit 1
      ;;
  esac
done

if [ ! -f .env ]; then
  echo "Missing .env. Copy .env.template to .env and fill values first."
  exit 1
fi

if [ "$REFRESH" -eq 1 ]; then
  "$ENGINE" compose --profile "$PROFILE_SET" pull || true
fi

"$ENGINE" compose --profile "$PROFILE_SET" up -d postgres

if [[ "$APPLY_MIGRATIONS" == "true" ]]; then
  bash "$(dirname -- "\${BASH_SOURCE[0]}")/migrate-db.sh" apply
fi

"$ENGINE" compose --profile "$PROFILE_SET" up -d --remove-orphans

echo "Infrastructure started with $ENGINE compose (profile: $PROFILE_SET)."
if [ "$CORE_MODE" = "local_source" ]; then
  echo "Core API local-source mode active (built from ./backend/Dockerfile)."
else
  echo "Core API container mode active via CORE_API_IMAGE."
fi
`;

  const bootstrapPs1 = `param(
  [ValidateSet("core", "suite", "de", "knowledger", "all")]
  [string]$ProfileSet = "all",
  [switch]$Refresh,
  [switch]$SkipMigrations
)

$ErrorActionPreference = "Stop"

$engine = if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { "${state.container_engine}" }
$coreMode = if ($env:CORE_API_RUNTIME_MODE) { $env:CORE_API_RUNTIME_MODE } else { "${state.core_api_runtime_mode}" }

if (-not (Test-Path ".env")) {
  Write-Error "Missing .env. Copy .env.template to .env and fill values first."
}

if ($Refresh) {
  & $engine compose --profile $ProfileSet pull
}

& $engine compose --profile $ProfileSet up -d postgres
if ($LASTEXITCODE -ne 0) {
  throw "PostgreSQL startup failed for profile set: $ProfileSet"
}
if (-not $SkipMigrations) {
  & (Join-Path $PSScriptRoot "migrate-db.ps1") -Action apply
  if ($LASTEXITCODE -ne 0) {
    throw "Migration apply failed with exit code $LASTEXITCODE."
  }
}
& $engine compose --profile $ProfileSet up -d --remove-orphans
if ($LASTEXITCODE -ne 0) {
  throw "Compose startup failed for profile set: $ProfileSet"
}
Write-Host "Infrastructure started with $engine compose (profile: $ProfileSet)."
if ($coreMode -eq "local_source") {
  Write-Host "Core API local-source mode active (built from ./backend/Dockerfile)."
} else {
  Write-Host "Core API container mode active via CORE_API_IMAGE."
}
`;

  const checkRuntimeSh = `#!/usr/bin/env bash
set -euo pipefail

BASE_URL="\${CORE_BASE_URL:-http://localhost:8000}"
SESSION_ID="\${MYAI_SESSION_ID:-}"

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
  echo "Set MYAI_SESSION_ID and re-run to query /v1/system/status."
  echo "Example: MYAI_SESSION_ID=<session-uuid> ./check-runtime.sh"
fi
`;

const checkRuntimePs1 = `$ErrorActionPreference = "Stop"
$baseUrl = if ($env:CORE_BASE_URL) { $env:CORE_BASE_URL } else { "http://localhost:8000" }
$sessionId = if ($env:MYAI_SESSION_ID) { $env:MYAI_SESSION_ID } else { "" }

Write-Host "Checking $baseUrl/v1/health"
Invoke-RestMethod -Uri "$baseUrl/v1/health" -Method Get

if ($sessionId) {
  Write-Host "Checking $baseUrl/v1/system/status?session_id=$sessionId"
  Invoke-RestMethod -Uri "$baseUrl/v1/system/status?session_id=$sessionId" -Method Get
} else {
  Write-Host "Set MYAI_SESSION_ID and re-run to query /v1/system/status."
  Write-Host "Example: $env:MYAI_SESSION_ID='<session-uuid>'; .\\check-runtime.ps1"
}
`;

  const refreshImagesSh = `#!/usr/bin/env bash
set -euo pipefail

ENGINE="\${CONTAINER_ENGINE:-${state.container_engine}}"
PROFILE_SET="\${2:-all}"
IMAGES_CSV="\${1:-}"
APPLY_MIGRATIONS="\${3:-true}"

if [ ! -f .env ]; then
  echo "Missing .env. Copy .env.template to .env and fill values first."
  exit 1
fi

CONFIG_JSON="$("$ENGINE" compose --profile "$PROFILE_SET" config --format json)"

is_local_tag() {
  case "$1" in
    *:local) return 0 ;;
    *) return 1 ;;
  esac
}

apply_pending_migrations() {
  [[ "$APPLY_MIGRATIONS" == "true" ]] || return 0
  echo "Ensuring PostgreSQL is available..."
  "$ENGINE" compose --profile "$PROFILE_SET" up -d postgres
  echo "Applying pending versioned migrations..."
  bash "$(dirname -- "\${BASH_SOURCE[0]}")/migrate-db.sh" apply
}

if [ -n "$IMAGES_CSV" ]; then
  IFS=',' read -r -a IMAGES <<< "$IMAGES_CSV"
  MATCHED_SERVICES=""

  for image in "\${IMAGES[@]}"; do
    image_trimmed="$(echo "$image" | xargs)"
    [ -z "$image_trimmed" ] && continue

    if is_local_tag "$image_trimmed"; then
      echo "Skipping pull for local tag $image_trimmed"
    else
      echo "Pulling $image_trimmed"
      if ! "$ENGINE" pull "$image_trimmed"; then
        echo "Pull failed for $image_trimmed" >&2
        exit 1
      fi
    fi

    SERVICE_MATCHES="$(printf '%s' "$CONFIG_JSON" | python3 -c "import json,sys; cfg=json.load(sys.stdin); target=sys.argv[1]; out=[name for name,svc in cfg.get('services',{}).items() if str(svc.get('image','')).strip()==target]; print(' '.join(out))" "$image_trimmed")"
    if [ -n "$SERVICE_MATCHES" ]; then
      MATCHED_SERVICES="$MATCHED_SERVICES $SERVICE_MATCHES"
    else
      echo "No service matched requested image $image_trimmed in profile $PROFILE_SET" >&2
      exit 1
    fi
  done

  MATCHED_SERVICES="$(echo "$MATCHED_SERVICES" | xargs)"
  if [ -n "$MATCHED_SERVICES" ]; then
    apply_pending_migrations
    echo "Recreating services: $MATCHED_SERVICES"
    "$ENGINE" compose --profile "$PROFILE_SET" up -d --no-deps --force-recreate $MATCHED_SERVICES
  else
    echo "No services matched requested images for profile $PROFILE_SET" >&2
    exit 1
  fi
else
  REMOTE_IMAGES="$(printf '%s' "$CONFIG_JSON" | python3 -c "import json,sys; cfg=json.load(sys.stdin); imgs=sorted({str(svc.get('image','')).strip() for svc in cfg.get('services',{}).values() if str(svc.get('image','')).strip() and not str(svc.get('image','')).strip().endswith(':local')}); print('\\n'.join(imgs))")"

  if [ -n "$REMOTE_IMAGES" ]; then
    while IFS= read -r image; do
      [ -z "$image" ] && continue
      echo "Pulling $image"
      if ! "$ENGINE" pull "$image"; then
        echo "Pull failed for $image" >&2
        exit 1
      fi
    done <<EOF
$REMOTE_IMAGES
EOF
  fi

  apply_pending_migrations
  "$ENGINE" compose --profile "$PROFILE_SET" up -d --force-recreate --remove-orphans
fi
`;

  const refreshImagesPs1 = `param(
  [string]$ImagesCsv = "",
  [string]$ProfileSet = "all",
  [switch]$SkipMigrations
)

$ErrorActionPreference = "Stop"
$engine = if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { "${state.container_engine}" }

if (-not (Test-Path ".env")) {
  Write-Error "Missing .env. Copy .env.template to .env and fill values first."
}

$configJson = & $engine compose --profile $ProfileSet config --format json
if ($LASTEXITCODE -ne 0) {
  throw "Compose config failed for profile $ProfileSet."
}
$config = $configJson | ConvertFrom-Json

function Get-IsLocalTag([string]$image) {
  return $image -match ':local$'
}

function Invoke-PendingMigrations {
  if ($SkipMigrations) { return }
  Write-Host "Ensuring PostgreSQL is available..."
  & $engine compose --profile $ProfileSet up -d postgres
  if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL startup failed for profile $ProfileSet."
  }
  Write-Host "Applying pending versioned migrations..."
  & (Join-Path $PSScriptRoot "migrate-db.ps1") -Action apply
  if ($LASTEXITCODE -ne 0) {
    throw "Migration apply failed with exit code $LASTEXITCODE."
  }
}

if ($ImagesCsv) {
  $images = $ImagesCsv.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  foreach ($image in $images) {
    if (Get-IsLocalTag $image) {
      Write-Host "Skipping pull for local tag $image"
    } else {
      Write-Host "Pulling $image"
      & $engine pull $image
      if ($LASTEXITCODE -ne 0) {
        throw "Pull failed for $image."
      }
    }
  }

  $imageSet = @{}
  foreach ($image in $images) { $imageSet[$image] = $true }
  $matchedImageSet = @{}

  $services = @()
  foreach ($svc in $config.services.PSObject.Properties) {
    $serviceImage = [string]$svc.Value.image
    if ($serviceImage -and $imageSet.ContainsKey($serviceImage)) {
      $services += $svc.Name
      $matchedImageSet[$serviceImage] = $true
    }
  }

  $missingImages = $images | Where-Object { -not $matchedImageSet.ContainsKey($_) }
  if ($missingImages.Count -gt 0) {
    throw "No service matched requested images: $($missingImages -join ', ')"
  }

  if ($services.Count -gt 0) {
    Invoke-PendingMigrations
    Write-Host "Recreating services: $($services -join ', ')"
    & $engine compose --profile $ProfileSet up -d --no-deps --force-recreate @services
    if ($LASTEXITCODE -ne 0) {
      throw "Service recreate failed for profile $ProfileSet."
    }
  } else {
    throw "No services matched requested images for profile $ProfileSet."
  }
} else {
  $remoteImages = @()
  foreach ($svc in $config.services.PSObject.Properties) {
    $serviceImage = [string]$svc.Value.image
    if ($serviceImage -and -not (Get-IsLocalTag $serviceImage)) {
      $remoteImages += $serviceImage
    }
  }
  $remoteImages = $remoteImages | Select-Object -Unique

  foreach ($image in $remoteImages) {
    Write-Host "Pulling $image"
    & $engine pull $image
    if ($LASTEXITCODE -ne 0) {
      throw "Pull failed for $image."
    }
  }

  Invoke-PendingMigrations
  & $engine compose --profile $ProfileSet up -d --force-recreate --remove-orphans
  if ($LASTEXITCODE -ne 0) {
    throw "Service recreate failed for profile $ProfileSet."
  }
}
`;

  const migrateDbSh = `#!/usr/bin/env bash
set -euo pipefail

ACTION="\${1:-apply}"
shift || true
SUITE_ROOT="$(cd -- "$(dirname -- "\${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SUITE_ROOT/migration-runner.sh" && -d "$SUITE_ROOT/migrations" ]]; then
  CORE_ROOT="$SUITE_ROOT"
else
  CORE_ROOT="$(cd -- "$SUITE_ROOT/.." && pwd)"
fi

[[ -f "$CORE_ROOT/migration-runner.sh" ]] || { echo "Migration runner not found: $CORE_ROOT/migration-runner.sh" >&2; exit 1; }
[[ -d "$CORE_ROOT/migrations" ]] || { echo "Migrations directory not found: $CORE_ROOT/migrations" >&2; exit 1; }

exec bash "$CORE_ROOT/migration-runner.sh" \\
  --action "$ACTION" \\
  --suite-path "$SUITE_ROOT" \\
  --migrations-path "$CORE_ROOT/migrations" \\
  "$@"
`;

  const migrateDbPs1 = `param(
  [ValidateSet("apply", "baseline", "dry-run", "status")]
  [string]$Action = "apply",
  [ValidatePattern("^\\d{4}$")]
  [string]$BaselineThrough = "",
  [switch]$BaselineConfirmSchema,
  [switch]$RestoreTools,
  [switch]$Json
)

$ErrorActionPreference = "Stop"
$localRunner = Join-Path $PSScriptRoot "migration-runner.ps1"
$localMigrations = Join-Path $PSScriptRoot "migrations"
$coreRoot = if ((Test-Path $localRunner) -and (Test-Path $localMigrations)) {
  Resolve-Path $PSScriptRoot
} else {
  Resolve-Path (Join-Path $PSScriptRoot "..")
}
$runner = Join-Path $coreRoot "migration-runner.ps1"
$migrations = Join-Path $coreRoot "migrations"

if (-not (Test-Path $runner)) { throw "Migration runner not found: $runner" }
if (-not (Test-Path $migrations)) { throw "Migrations directory not found: $migrations" }

$runnerArguments = @{
  Action = $Action
  SuitePath = $PSScriptRoot
  MigrationsPath = $migrations
}
if ($RestoreTools) { $runnerArguments.RestoreTools = $true }
if ($BaselineThrough) { $runnerArguments.BaselineThrough = $BaselineThrough }
if ($BaselineConfirmSchema) { $runnerArguments.BaselineConfirmSchema = $true }
if ($Json) { $runnerArguments.Json = $true }

& $runner @runnerArguments
if ($LASTEXITCODE -ne 0) {
  throw "Migration runner failed with exit code $LASTEXITCODE."
}
`;

  const deploySh = `#!/usr/bin/env bash
set -euo pipefail

ENGINE="\${CONTAINER_ENGINE:-${state.container_engine}}"
PROFILE_SET="\${1:-all}"
REFRESH_IMAGES="\${2:-false}"
APPLY_MIGRATIONS="\${3:-true}"

if [ ! -f .env ]; then
  echo "Missing .env. Copy env.template to .env and fill values first."
  exit 1
fi

if [ "$REFRESH_IMAGES" = "true" ]; then
  echo "Pulling images for profile set: $PROFILE_SET"
  if ! "$ENGINE" compose --profile "$PROFILE_SET" pull; then
    echo "Pull reported failures. Continuing so local/buildable images can still be deployed."
  fi
fi

echo "Ensuring PostgreSQL is available..."
"$ENGINE" compose --profile "$PROFILE_SET" up -d postgres

if [[ "$APPLY_MIGRATIONS" == "true" ]]; then
  echo "Applying pending versioned migrations..."
  bash "$(dirname -- "\${BASH_SOURCE[0]}")/migrate-db.sh" apply
fi

echo "Deploying services for profile set: $PROFILE_SET"
"$ENGINE" compose --profile "$PROFILE_SET" up -d --build --force-recreate --remove-orphans

echo "Deployment complete. Containers refreshed, volumes preserved."
`;

  const deployPs1 = `param(
  [string]$ProfileSet = "all",
  [switch]$RefreshImages,
  [switch]$SkipMigrations
)

$ErrorActionPreference = "Stop"
$engine = if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { "${state.container_engine}" }

if (-not (Test-Path ".env")) {
  Write-Error "Missing .env. Copy env.template to .env and fill values first."
}

if ($RefreshImages) {
  Write-Host "Pulling images for profile set: $ProfileSet"
  & $engine compose --profile $ProfileSet pull
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Image pull reported failures. Continuing so local/buildable images can still be deployed."
  }
}

Write-Host "Ensuring PostgreSQL is available..."
& $engine compose --profile $ProfileSet up -d postgres
if ($LASTEXITCODE -ne 0) {
  throw "PostgreSQL startup failed for profile set: $ProfileSet"
}

if (-not $SkipMigrations) {
  Write-Host "Applying pending versioned migrations..."
  & (Join-Path $PSScriptRoot "migrate-db.ps1") -Action apply
  if ($LASTEXITCODE -ne 0) {
    throw "Migration apply failed with exit code $LASTEXITCODE."
  }
}

Write-Host "Deploying services for profile set: $ProfileSet"
& $engine compose --profile $ProfileSet up -d --build --force-recreate --remove-orphans
if ($LASTEXITCODE -ne 0) {
  throw "Compose deploy failed for profile set: $ProfileSet"
}

Write-Host "Deployment complete. Containers refreshed, volumes preserved."
`;

  const bundleManifest = (files: GeneratedArtifact[]) => {
    const entries = files.map((file) => ({ name: file.name, type: file.type, content: file.content }));
    return JSON.stringify(
      {
        schema: "myai-bootstrap-bundle/v0.1",
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
    artifacts.push({ name: "deploy.sh", type: "sh", content: deploySh });
    artifacts.push({ name: "deploy.ps1", type: "ps1", content: deployPs1 });
    artifacts.push({ name: "refresh-images.sh", type: "sh", content: refreshImagesSh });
    artifacts.push({ name: "refresh-images.ps1", type: "ps1", content: refreshImagesPs1 });
    artifacts.push({ name: "migrate-db.sh", type: "sh", content: migrateDbSh });
    artifacts.push({ name: "migrate-db.ps1", type: "ps1", content: migrateDbPs1 });
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
      content: "# Experimental template\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: myai-core-api\nspec:\n  replicas: 1\n",
    });
  }

  if (state.deployment_target === "terraform") {
    artifacts.push({
      name: "terraform.tfvars.example",
      type: "sh",
      content: `project_name = \"${state.tenant_name || "myai-core"}\"\nenvironment = \"dev\"\n`,
    });
  }

  if (state.deployment_target === "github_actions") {
    artifacts.push({
      name: "github-actions-snippet.yml",
      type: "yaml",
      content: "name: myai-core-bootstrap\non:\n  workflow_dispatch:\n",
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
