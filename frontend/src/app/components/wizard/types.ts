export type ModelMode = "api_provider" | "local_model";
export type ApiProvider = "openai" | "anthropic" | "google" | "custom";
export type LocalProvider = "ollama" | "lmstudio" | "custom";
export type DeployTarget = "docker_local" | "k8s" | "terraform" | "github_actions";
export type ContainerEngine = "docker" | "podman";
export type CoreApiRuntimeMode = "local_source" | "bundled_image" | "custom_image";
export type FrontendService =
  | "myai_core_frontend"
  | "myai_studio_frontend"
  | "myai_council_frontend"
  | "myai_de_frontend"
  | "myai_knowledger_frontend";
export type ExecMode = "generate_only" | "attempt_automated";
export type SecretsMode = "template_only" | "transient_validate_only" | "pipeline_injected";
export type VectorMode = "disabled" | "enabled";
export type CheckStatus = "idle" | "running" | "done";
export type CheckResult = "pass" | "warn" | "fail" | "pending";

export interface Connection {
  id: string;
  mode: ModelMode;
  provider: ApiProvider | LocalProvider;
  endpoint: string;
  model_ref: string;
  priority: number;
}

export interface CheckItem {
  name: string;
  label: string;
  required: boolean;
  status: CheckResult;
  message: string;
}

export interface GeneratedArtifact {
  name: string;
  type: "env" | "yaml" | "json" | "sh" | "md" | "ps1" | "sql";
  content: string;
}

export interface WizardState {
  tenant_name: string;
  tenant_type: "company" | "individual";
  model_modes: ModelMode[];
  connections: Connection[];
  deployment_target: DeployTarget;
  container_engine: ContainerEngine;
  core_api_runtime_mode: CoreApiRuntimeMode;
  core_api_custom_image: string;
  frontend_services: FrontendService[];
  execution_mode: ExecMode;
  infra_components: string[];
  secrets_mode: SecretsMode;
  storage_target: string;
  required_keys: string[];
  materialize_local_env: boolean;
  local_secret_values: Record<string, string>;
  local_env_overrides: Record<string, string>;
  vector_store_mode: VectorMode;
  vector_provider: "pgvector" | "pinecone";
  namespace_pattern: string;
  index_strategy: string;
  vector_endpoint: string;
  check_status: CheckStatus;
  check_results: CheckItem[];
  runtime_check_status: CheckStatus;
  runtime_check_results: CheckItem[];
  runtime_check_error: string;
  runtime_base_url: string;
  bootstrap_session_id: string;
  ingest_now: boolean;
  doc_files: string[];
  chunking_profile: string;
  embedding_profile: string;
  ingest_status: "idle" | "done";
  gen_status: "idle" | "generating" | "done";
  artifacts: GeneratedArtifact[];
  confirmed: boolean;
}

export interface StepProps {
  state: WizardState;
  update: (partial: Partial<WizardState>) => void;
}
