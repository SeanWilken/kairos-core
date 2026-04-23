import {
  ClipboardCheck,
  Container,
  Database,
  KeyRound,
  Monitor,
  PackageCheck,
  Rocket,
  Server,
  ShieldCheck,
} from "lucide-react";

import type { CheckResult, WizardState } from "./types";

export const INFRA_COMPONENTS = [
  { id: "core_api", label: "core_api", description: "Primary application server", required: true },
  { id: "postgres", label: "postgres", description: "Relational database" },
  { id: "pgvector", label: "pgvector", description: "Vector extension (requires postgres)" },
  { id: "local_model_runtime", label: "local_model_runtime", description: "Ollama / LM Studio runtime" },
];

export const STEP_DEFS = [
  { id: 1, label: "Runtime", description: "Model modes & connections", icon: Server },
  { id: 2, label: "Deployment", description: "Target & infrastructure", icon: Container },
  { id: 3, label: "Frontends", description: "Optional UI services", icon: Monitor },
  { id: 4, label: "Secrets", description: "Key management strategy", icon: KeyRound },
  { id: 5, label: "Vector Store", description: "RAG configuration", icon: Database },
  { id: 6, label: "Preflight", description: "Config validation", icon: ShieldCheck },
  { id: 7, label: "Artifacts", description: "Generate config files", icon: PackageCheck },
  { id: 8, label: "Runtime Verify", description: "Run checks + docs", icon: Rocket },
  { id: 9, label: "Review", description: "Confirm & complete", icon: ClipboardCheck },
];

export const RUNTIME_WIZARD_STEP_IDS = [2, 8, 9] as const;

export const CHECK_OUTCOMES: Record<string, { status: CheckResult; message: string }> = {
  core_health_endpoint: { status: "pass", message: "API server responding on :8000" },
  postgres_reachable: { status: "pass", message: "postgres://localhost:5432 — connected" },
  pgvector_extension: { status: "pass", message: "pgvector 0.7.4 extension active" },
  openai_endpoint: { status: "pass", message: "api.openai.com/v1 — 200 OK" },
  anthropic_endpoint: { status: "pass", message: "api.anthropic.com/v1 — 200 OK" },
  custom_endpoint: { status: "warn", message: "Reachable — validate auth manually" },
  ollama_endpoint: { status: "warn", message: "ollama:11434 — no models pulled yet" },
  lmstudio_endpoint: { status: "pass", message: "LM Studio server responding" },
  local_model_endpoint: { status: "warn", message: "Local endpoint up — load a model first" },
  pinecone_endpoint: { status: "pass", message: "Pinecone index accessible" },
};

export const INITIAL_STATE: WizardState = {
  tenant_name: "",
  tenant_type: "company",
  model_modes: ["api_provider"],
  connections: [
    {
      id: "1",
      mode: "api_provider",
      provider: "openai",
      endpoint: "https://api.openai.com/v1",
      model_ref: "gpt-4o-mini",
      priority: 1,
    },
  ],
  deployment_target: "docker_local",
  container_engine: "docker",
  core_api_runtime_mode: "local_source",
  core_api_custom_image: "",
  frontend_services: [],
  execution_mode: "generate_only",
  infra_components: ["core_api"],
  secrets_mode: "template_only",
  storage_target: "env_file",
  required_keys: [],
  materialize_local_env: false,
  local_secret_values: {},
  local_env_overrides: {
    POSTGRES_HOST: "localhost",
    POSTGRES_PORT: "5432",
    POSTGRES_DB: "kairos",
    POSTGRES_USER: "kairos",
  },
  vector_store_mode: "disabled",
  vector_provider: "pgvector",
  namespace_pattern: "",
  index_strategy: "flat",
  vector_endpoint: "",
  check_status: "idle",
  check_results: [],
  runtime_check_status: "idle",
  runtime_check_results: [],
  runtime_check_error: "",
  runtime_base_url: "http://localhost:8000",
  bootstrap_session_id: "",
  ingest_now: false,
  doc_files: [],
  chunking_profile: "recursive_512",
  embedding_profile: "default",
  ingest_status: "idle",
  gen_status: "idle",
  artifacts: [],
  confirmed: false,
};

export const STEP_HEADER: Record<number, { title: string; description: string }> = {
  1: { title: "Runtime Configuration", description: "Define your tenant identity, model modes, and connection settings." },
  2: { title: "Deployment Target", description: "Choose where and how your environment will be deployed." },
  3: { title: "Frontend Services", description: "Select optional frontend services to include in generated compose." },
  4: { title: "Secrets Strategy", description: "Configure how credentials and sensitive values are managed." },
  5: { title: "Vector Store & RAG", description: "Optionally enable and configure a vector store for retrieval-augmented generation." },
  6: { title: "Preflight Validation", description: "Validate configuration consistency before generating artifacts." },
  7: { title: "Artifact Generation", description: "Generate deployment configuration files from your session." },
  8: { title: "Runtime Verify + Documents", description: "Run real runtime checks, then optionally bootstrap documents." },
  9: { title: "Review & Complete", description: "Review your configuration summary and confirm to complete setup." },
};
