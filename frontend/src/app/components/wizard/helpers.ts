import type { CheckItem, CheckResult, GeneratedArtifact, WizardState } from "./types";

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
  }
  if (state.infra_components.includes("pgvector")) {
    checks.push({ name: "pgvector_extension", label: "pgvector extension", required: true, status: "pending", message: "" });
  }
  if (state.connections.some((c) => c.mode === "api_provider")) {
    checks.push({ name: "provider_connectivity", label: "API provider connectivity", required: true, status: "pending", message: "" });
  }
  if (state.model_modes.includes("local_model")) {
    checks.push({ name: "local_model_endpoint", label: "Local model endpoint", required: true, status: "pending", message: "" });
  }
  return checks;
}

async function pingJson(url: string): Promise<{ ok: boolean; status: number; body?: unknown }> {
  const response = await fetch(url, { method: "GET" });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  return { ok: response.ok, status: response.status, body };
}

export async function runRuntimeChecks(state: WizardState): Promise<CheckItem[]> {
  const checks = buildRuntimeChecks(state);
  const base = state.runtime_base_url.replace(/\/$/, "");

  const out: CheckItem[] = [];
  for (const check of checks) {
    if (check.name === "core_health_endpoint") {
      try {
        const res = await pingJson(`${base}/v1/health`);
        out.push({ ...check, status: res.ok ? "pass" : "fail", message: res.ok ? "Core health endpoint reachable." : `Health returned HTTP ${res.status}.` });
      } catch {
        out.push({ ...check, status: "fail", message: "Could not reach Core health endpoint." });
      }
      continue;
    }

    if (check.name === "postgres_reachable" || check.name === "pgvector_extension" || check.name === "provider_connectivity") {
      try {
        const res = await pingJson(`${base}/v1/system/status`);
        if (!res.ok || !res.body || typeof res.body !== "object") {
          out.push({ ...check, status: "warn", message: "System status endpoint unavailable; verify manually." });
          continue;
        }
        out.push({ ...check, status: "pass", message: "Validated via system status endpoint." });
      } catch {
        out.push({ ...check, status: "warn", message: "Status endpoint unavailable; verify manually." });
      }
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

  return out;
}

export function buildArtifacts(state: WizardState): GeneratedArtifact[] {
  let env = "# .env.template — generated by Kairos Core Setup\n# Do not commit real values to source control.\n\n";
  env += "# Core\nCORE_API_PORT=8000\nCORE_ENV=development\n\n";
  const apiConns = state.connections.filter((c) => c.mode === "api_provider");
  if (apiConns.length) {
    env += "# Model Providers\n";
    apiConns.forEach((c) => {
      const keyMap: Record<string, string> = {
        openai: "OPENAI_API_KEY=",
        anthropic: "ANTHROPIC_API_KEY=",
        google: "GOOGLE_AI_API_KEY=",
        azure_openai: "AZURE_OPENAI_API_KEY=\nAZURE_OPENAI_ENDPOINT=",
        custom: "CUSTOM_API_KEY=",
      };
      env += `${keyMap[c.provider] ?? "API_KEY="}\n`;
    });
    env += "\n";
  }
  if (state.infra_components.includes("postgres")) {
    env += "# PostgreSQL\nPOSTGRES_HOST=localhost\nPOSTGRES_PORT=5432\nPOSTGRES_DB=app\nPOSTGRES_USER=app\nPOSTGRES_PASSWORD=\n\n";
  }
  if (state.vector_store_mode === "enabled" && state.vector_provider === "pinecone") {
    env += "# Pinecone\nPINECONE_API_KEY=\nPINECONE_ENVIRONMENT=\nPINECONE_INDEX=\n\n";
  }

  let compose = "version: \"3.9\"\n\nservices:\n\n  core_api:\n    build: .\n    ports:\n      - \"${CORE_API_PORT:-8000}:8000\"\n    env_file: .env\n    restart: unless-stopped\n";
  const deps: string[] = [];
  if (state.infra_components.includes("postgres") || state.infra_components.includes("pgvector")) deps.push("postgres");
  if (state.infra_components.includes("local_model_runtime")) deps.push("ollama");
  if (deps.length) compose += `    depends_on:\n${deps.map((d) => `      - ${d}`).join("\n")}\n`;
  if (state.infra_components.includes("postgres") || state.infra_components.includes("pgvector")) {
    const img = state.infra_components.includes("pgvector") ? "pgvector/pgvector:pg16" : "postgres:16-alpine";
    compose += `\n  postgres:\n    image: ${img}\n    environment:\n      POSTGRES_DB: \${POSTGRES_DB}\n      POSTGRES_USER: \${POSTGRES_USER}\n      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n    ports:\n      - \"5432:5432\"\n`;
  }
  if (state.infra_components.includes("local_model_runtime")) {
    compose += "\n  ollama:\n    image: ollama/ollama:latest\n    ports:\n      - \"11434:11434\"\n    volumes:\n      - ollama_data:/root/.ollama\n";
  }
  if (state.infra_components.includes("reverse_proxy")) {
    compose += "\n  nginx:\n    image: nginx:alpine\n    ports:\n      - \"80:80\"\n    volumes:\n      - ./nginx.conf:/etc/nginx/conf.d/default.conf\n    depends_on:\n      - core_api\n";
  }
  compose += "\nvolumes:\n";
  if (state.infra_components.includes("postgres") || state.infra_components.includes("pgvector")) compose += "  pgdata:\n";
  if (state.infra_components.includes("local_model_runtime")) compose += "  ollama_data:\n";

  const nginxConf = `server {
  listen 80;

  location / {
    proxy_pass http://core_api:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
`;

  const report = JSON.stringify(
    {
      schema: "bootstrap-report/v0.1",
      generated_at: new Date().toISOString().split("T")[0],
      tenant: { name: state.tenant_name, type: state.tenant_type },
      runtime: {
        model_modes: state.model_modes,
        connections: state.connections.map((c) => ({ mode: c.mode, provider: c.provider, model_ref: c.model_ref })),
      },
      deployment: { target: state.deployment_target, execution_mode: state.execution_mode, components: state.infra_components },
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

  const artifacts: GeneratedArtifact[] = [{ name: ".env.template", type: "env", content: env }];
  if (state.deployment_target === "docker_local") {
    artifacts.push({ name: "docker-compose.yml", type: "yaml", content: compose });
    if (state.infra_components.includes("reverse_proxy")) {
      artifacts.push({ name: "nginx.conf", type: "sh", content: nginxConf });
    }
  }
  if (state.deployment_target === "k8s") {
    artifacts.push({
      name: "k8s-manifests.yaml",
      type: "yaml",
      content:
        "# Experimental template\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: kairos-core-api\nspec:\n  replicas: 1\n",
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
  artifacts.push({ name: "bootstrap-report.json", type: "json", content: report });
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
