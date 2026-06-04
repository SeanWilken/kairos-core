import { Checkbox, Input, Label, cn } from "@myai-tech/myui";

import { INFRA_COMPONENTS } from "../constants";
import type { DeployTarget, ExecMode, StepProps } from "../types";

export function StepDeployment({ state, update }: StepProps) {
  const toggleComp = (id: string) => {
    if (id === "core_api") return;
    let next = [...state.infra_components];
    if (next.includes(id)) {
      if (id === "postgres" && next.includes("pgvector")) next = next.filter((x) => x !== "pgvector");
      next = next.filter((x) => x !== id);
    } else {
      if (id === "pgvector" && !next.includes("postgres")) next = [...next, "postgres"];
      next = [...next, id];
    }
    update({ infra_components: next });
  };

  const targets = [
    { id: "docker_local", label: "Docker (Local)", hint: "docker-compose.yml + .env.template", badge: "MVP" },
    { id: "k8s", label: "Kubernetes", hint: "Kubernetes manifests", badge: "Soon" },
    { id: "terraform", label: "Terraform", hint: "tfvars + HCL modules", badge: "Soon" },
    { id: "github_actions", label: "GitHub Actions", hint: "CI/CD pipeline snippet", badge: "Soon" },
  ] as const;

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label>Deployment Target</Label>
        <div className="space-y-2">
          {targets.map((t) => (
            <label key={t.id} className={cn("flex items-center gap-3 p-4 border rounded-lg cursor-pointer transition-colors", state.deployment_target === t.id ? "border-zinc-900 bg-zinc-50" : "border-zinc-200 bg-white hover:border-zinc-300")}>
              <input type="radio" name="deployment_target" value={t.id} checked={state.deployment_target === t.id} onChange={() => update({ deployment_target: t.id as DeployTarget })} className="text-zinc-900" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-900">{t.label}</span>
                  <span className={cn("text-xs px-1.5 py-0.5 rounded font-medium", t.badge === "MVP" ? "bg-green-100 text-green-700" : "bg-zinc-100 text-zinc-500")}>{t.badge}</span>
                </div>
                <p className="text-xs text-zinc-500 mt-0.5">Generates: {t.hint}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label>Execution Mode</Label>
        <div className="grid grid-cols-2 gap-3">
          {([
            { id: "generate_only", label: "Generate Only", desc: "Output files — no execution" },
            { id: "attempt_automated", label: "Attempt Automated", desc: "Try to run scripts automatically" },
          ] as const).map((m) => (
            <label key={m.id} className={cn("flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors", state.execution_mode === m.id ? "border-zinc-900 bg-zinc-50" : "border-zinc-200 bg-white hover:border-zinc-300")}>
              <input type="radio" name="exec_mode" value={m.id} checked={state.execution_mode === m.id} onChange={() => update({ execution_mode: m.id as ExecMode })} className="mt-0.5" />
              <div>
                <div className="text-sm font-medium text-zinc-900">{m.label}</div>
                <p className="text-xs text-zinc-500 mt-0.5">{m.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {state.deployment_target === "docker_local" && (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Container Engine Preference</Label>
            <div className="grid grid-cols-2 gap-3">
            {([
              { id: "docker", label: "Docker", desc: "Default docker compose engine" },
              { id: "podman", label: "Podman", desc: "Use podman compose commands" },
            ] as const).map((engine) => (
              <label
                key={engine.id}
                className={cn(
                  "flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors",
                  state.container_engine === engine.id
                    ? "border-zinc-900 bg-zinc-50"
                    : "border-zinc-200 bg-white hover:border-zinc-300"
                )}
              >
                <input
                  type="radio"
                  name="container_engine"
                  value={engine.id}
                  checked={state.container_engine === engine.id}
                  onChange={() => update({ container_engine: engine.id as "docker" | "podman" })}
                  className="mt-0.5"
                />
                <div>
                  <div className="text-sm font-medium text-zinc-900">{engine.label}</div>
                  <p className="text-xs text-zinc-500 mt-0.5">{engine.desc}</p>
                </div>
              </label>
            ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Core API Runtime Source</Label>
            <div className="space-y-2">
              {([
                { id: "local_source", label: "Run from this repo", desc: "Use uvicorn in backend/ and compose for infrastructure only" },
                { id: "bundled_image", label: "Use bundled stable image", desc: "Run core_api from default stable image tag" },
                { id: "custom_image", label: "Use custom image", desc: "Provide your own image URL/tag (must be accessible by CLI auth)" },
              ] as const).map((mode) => (
                <label
                  key={mode.id}
                  className={cn(
                    "flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors",
                    state.core_api_runtime_mode === mode.id
                      ? "border-zinc-900 bg-zinc-50"
                      : "border-zinc-200 bg-white hover:border-zinc-300"
                  )}
                >
                  <input
                    type="radio"
                    name="core_api_runtime_mode"
                    value={mode.id}
                    checked={state.core_api_runtime_mode === mode.id}
                    onChange={() => update({ core_api_runtime_mode: mode.id })}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-sm font-medium text-zinc-900">{mode.label}</div>
                    <p className="text-xs text-zinc-500 mt-0.5">{mode.desc}</p>
                  </div>
                </label>
              ))}
            </div>

            {state.core_api_runtime_mode === "custom_image" && (
              <div className="space-y-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <Label>Custom Core API image</Label>
                <Input
                  value={state.core_api_custom_image}
                  onChange={(e) => update({ core_api_custom_image: e.target.value })}
                  placeholder="myaitech/myai-core-api:tag"
                  className="font-mono text-xs"
                />
                <p className="text-xs text-zinc-500">Examples: `myaitech/myai-core-api:stable`, `myaitech/myai-de-api:stable`. If private, ensure Docker/Podman CLI is already authenticated to your registry.</p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="space-y-2">
        <Label>Infrastructure Components</Label>
        <div className="space-y-2">
          {INFRA_COMPONENTS.map((comp) => (
            <div key={comp.id} className={cn("flex items-center gap-3 p-3 border rounded-lg", state.infra_components.includes(comp.id) ? "border-zinc-300 bg-zinc-50" : "border-zinc-200 bg-white", comp.required ? "opacity-70" : "cursor-pointer hover:border-zinc-300")} onClick={() => !comp.required && toggleComp(comp.id)}>
              <Checkbox checked={state.infra_components.includes(comp.id)} disabled={comp.required} onCheckedChange={() => toggleComp(comp.id)} />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium font-mono text-zinc-900">{comp.label}</span>
                  {comp.required && <span className="text-xs text-zinc-400 bg-zinc-100 px-1.5 rounded">required</span>}
                </div>
                <p className="text-xs text-zinc-500 mt-0.5">{comp.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
